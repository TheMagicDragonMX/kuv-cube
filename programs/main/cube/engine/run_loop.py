"""
LAYER: engine (run loop).

A timer that calls a function at a steady rate, handing it the current time in milliseconds. That is all it does. It
is separate from the engine so the engine never has to know about clocks or timers.

It runs on the asyncio event loop, so it never blocks and must be started from inside it.
"""

import asyncio
import logging
import time
from typing import Callable


logger = logging.getLogger(__name__)
"""
Where this module reports problems.
"""

DEFAULT_TICK_RATE = 30
"""
Default number of ticks per second.
"""


def monotonic_milliseconds() -> float:
    """
    The time of a clock that never goes back, in milliseconds.
    """
    return time.monotonic() * 1000


class RunLoop:
    """
    Calls a function at a steady rate until stopped.
    """

    def __init__(self, tick_rate: float = DEFAULT_TICK_RATE, clock: Callable[[], float] = monotonic_milliseconds) -> None:
        """
        Ticks `tick_rate` times per second. The clock is replaceable for tests.
        """
        self._tick_rate = tick_rate
        """
        Ticks per second.
        """

        self._clock = clock
        """
        Source of the current time in milliseconds.
        """

        self._task: asyncio.Task | None = None
        """
        The task that drives the ticks, while running.
        """

    @property
    def running(self) -> bool:
        """
        True between `start` and `stop`.
        """
        return self._task is not None

    def now(self) -> float:
        """
        Current time, as this loop sees it.
        """
        return self._clock()

    def start(self, on_tick: Callable[[float], None]) -> None:
        """
        Calls `on_tick` at the tick rate until stopped. Starting again replaces the callback. Call it from inside
        the event loop.
        """
        self.stop()

        self._task = asyncio.get_running_loop().create_task(self._run(on_tick))

    def stop(self) -> None:
        """
        Stops calling.
        """
        if self._task is not None:
            self._task.cancel()

            self._task = None

    async def _run(self, on_tick: Callable[[float], None]) -> None:
        """
        Sleeps until each tick is due, so a slow tick does not make the following ones drift.
        """
        loop = asyncio.get_running_loop()
        interval = 1 / self._tick_rate
        due = loop.time() + interval

        while True:
            await asyncio.sleep(max(0, due - loop.time()))

            try:
                on_tick(self._clock())

            except Exception:
                logger.exception("A tick failed")

            due += interval

            # After a long stall, start over from now instead of firing every missed tick at once.
            if due < loop.time():
                due = loop.time() + interval
