"""
LAYER: runtime (scheduler).

Decides *when* each script gets to run. The interpreter knows how to run a script until it pauses; the scheduler
keeps every script of the program, remembers when each one wants to continue, and gives each a turn on every tick.

    tick(now):
      1. for every "every N seconds" script that is due, start a new run (unless the previous run is still going)
      2. for every running script whose wake-up time has come, resume it once; it runs until its next pause

Properties worth knowing:

  - Time is real time in milliseconds, passed in by the caller (`now`). The scheduler never reads a clock itself, so
    tests can drive it with made-up times.
  - A script is resumed **at most once per tick**, so a script can never run away inside one tick, however many
    loops it has.
  - `wait` counts from the moment the script was *supposed* to wake up, not from the tick that happened to run it.
    Otherwise every wait would last up to one tick too long, and a loop with `wait 0.1` would drift. The correction
    is capped (MAX_CATCH_UP) so that after a long freeze scripts do not rush to catch up.
  - A script that fails (for example it moves an object that does not exist) is stopped and reported. The other
    scripts keep running.
"""

from typing import Any, Callable, NotRequired, TypedDict

from programs.main.cube.program.program import Script
from programs.main.cube.runtime.interpreter import Run, run_blocks
from programs.main.cube.world.world import World


MAX_CATCH_UP = 100
"""
Most a script is allowed to run "in the past" to make up for a late tick, in milliseconds.
"""


class ScriptError(TypedDict):
    """
    A problem that stopped one script.
    """

    script: int
    """
    Index of the script in the program.
    """

    message: str
    """
    What went wrong, in words a user can read.
    """


class Task(TypedDict):
    """
    One running script.
    """

    script: int
    """
    Index of the script in the program.
    """

    run: Run
    """
    Where the script is in its blocks.
    """

    wake_at: float
    """
    Time from which the task can be resumed.
    """

    scheduled_at: NotRequired[float | None]
    """
    Moment the task was meant to continue, when it paused with a `wait`. None when it paused with a tick: then it
    continues "from now".
    """


class IntervalTimer(TypedDict):
    """
    Starts a script again every so often.
    """

    script: int
    """
    Index of the script in the program.
    """

    milliseconds: float
    """
    Time between starts.
    """

    next_at: float
    """
    When the script starts next.
    """


class Scheduler:
    """
    Runs the scripts of a program over time: starts them on their trigger, resumes the ones that paused, and reports
    the ones that fail.
    """

    def __init__(self, world: World, scripts: list[Script], on_error: Callable[[ScriptError], None]) -> None:
        """
        Builds the scheduler for a program's scripts, which act on `world`. `on_error` is called when a script
        stops because of an error.
        """
        self._world = world
        """
        The world the scripts act on.
        """

        self._scripts = scripts
        """
        The scripts of the program.
        """

        self._on_error = on_error
        """
        Called when a script stops because of an error.
        """

        self._tasks: list[Task] = []
        """
        The scripts running or paused right now.
        """

        self._timers: list[IntervalTimer] = []
        """
        The timers that will start scripts again.
        """

    @property
    def active(self) -> bool:
        """
        True while there is anything left to run: a script mid-way, or a timer that will start one.
        """
        return bool(self._tasks) or bool(self._timers)

    def start(self, now: float) -> None:
        """
        Starts the program: scripts triggered by `start` begin, and interval timers are set. Nothing runs until the
        next `tick`.
        """
        self.stop()

        for index, script in enumerate(self._scripts):
            trigger: Any = script["trigger"]

            if trigger["type"] == "start":
                self._spawn(index, now)

            else:
                milliseconds = trigger["seconds"] * 1000

                self._timers.append({"script": index, "milliseconds": milliseconds, "next_at": now + milliseconds})

    def tick(self, now: float) -> None:
        """
        Gives every script that is ready one turn.
        """
        self._fire_timers(now)

        for task in [*self._tasks]:
            if now >= task["wake_at"]:
                self._resume(task, now)

    def stop(self) -> None:
        """
        Forgets every script and timer. What they already did to the world stays.
        """
        self._tasks = []
        self._timers = []

    def _spawn(self, script: int, now: float) -> None:
        """
        Starts a run of a script, to be resumed on the next tick.
        """
        self._tasks.append({"script": script, "run": run_blocks(self._scripts[script]["blocks"], self._world), "wake_at": now})

    def _fire_timers(self, now: float) -> None:
        """
        Starts the runs of the interval scripts that are due.
        """
        for timer in self._timers:
            if now < timer["next_at"]:
                continue

            if not any(task["script"] == timer["script"] for task in self._tasks):
                self._spawn(timer["script"], now)

            # Skip any whole intervals that were missed instead of firing them all at once.
            while timer["next_at"] <= now:
                timer["next_at"] += timer["milliseconds"]

    def _resume(self, task: Task, now: float) -> None:
        """
        Runs a task until its next pause, and files it until it is due again.
        """
        scheduled_at = task.get("scheduled_at")

        if scheduled_at is None:
            resumed_at = now

        else:
            resumed_at = min(now, max(scheduled_at, now - MAX_CATCH_UP))

        try:
            pause = next(task["run"])

        except StopIteration:
            self._tasks = [other for other in self._tasks if other is not task]

            return

        except Exception as error:
            self._tasks = [other for other in self._tasks if other is not task]
            self._on_error({"script": task["script"], "message": str(error)})

            return

        if pause["kind"] == "wait":
            task["scheduled_at"] = resumed_at + pause["milliseconds"]
            task["wake_at"] = task["scheduled_at"]

        else:
            task["scheduled_at"] = None
            task["wake_at"] = now
