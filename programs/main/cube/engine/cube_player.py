"""
LAYER: engine (player).

The engine plus a real clock: "give it a program and it runs". This is what the main program uses.

    player = CubePlayer({"on_frame": show_on_the_panels})
    player.play(program)       # runs on its own, ticking in the background
    player.state               # what the cube shows
    player.stop()              # stop the scripts, keep the picture
    player.reset()             # stop and clear the cube (only the environment stays)
    player.dispose()           # when finished with it

It starts its timer on `play` and stops it by itself when the program is over (no script is left running), so a
finished program costs nothing. It needs the asyncio event loop: call `play` from inside it.

Whatever shows the cube hears about it through `on_frame`, which is called with the state each time the picture
changed.
"""

from typing import Any, Callable, TypedDict

from programs.main.cube.blocks import CreateCommand
from programs.main.cube.engine.cube_engine import CubeEngine, CubeEngineOptions, Frame, Grab, Placement
from programs.main.cube.engine.run_loop import DEFAULT_TICK_RATE, RunLoop
from programs.main.cube.environment.environment import Environment
from programs.main.cube.program.program import FaceName, HeadingName, ProgramConfig
from programs.main.cube.state.cube_state import CubeState, Face


class CubePlayerOptions(CubeEngineOptions, total=False):
    """
    Settings of the player: those of the engine, plus timing and two callbacks.
    """

    tick_rate: float
    """
    Ticks per second.
    """

    clock: Callable[[], float]
    """
    Source of the current time in milliseconds. Defaults to a monotonic clock.
    """

    on_running_change: Callable[[bool], None]
    """
    Called whenever the program starts or stops running.
    """

    on_frame: Callable[[CubeState], None]
    """
    Called with the state of the cube each time the picture changed.
    """


class CubePlayer:
    """
    Runs a program in real time: an engine driven by a run loop, which reports when it starts and stops and when the
    picture changes.
    """

    def __init__(self, options: CubePlayerOptions | None = None) -> None:
        """
        Builds the player with the given options.
        """
        self._options: CubePlayerOptions = options or {}
        """
        Engine settings plus the tick rate and the callbacks of the player.
        """

        self._engine = CubeEngine(self._options)
        """
        The engine that runs the program.
        """

        self._loop = RunLoop(self._options.get("tick_rate", DEFAULT_TICK_RATE), **self._clock_argument())
        """
        The timer that ticks the engine.
        """

        self._reported_running = False
        """
        Last value sent to `on_running_change`.
        """

        self._presented_version = -1
        """
        Version of the state last sent to `on_frame`.
        """

    @property
    def state(self) -> CubeState:
        """
        What the cube shows.
        """
        return self._engine.state

    @property
    def running(self) -> bool:
        """
        True while the program is running.
        """
        return self._engine.running

    def set_defaults(self, defaults: ProgramConfig | None) -> None:
        """
        Changes the engine settings used by programs that do not set their own. They apply from the next `play` or
        `reset`.
        """
        self._engine.set_defaults(defaults)

    def set_environment(self, environment: Environment | None) -> None:
        """
        Changes the images on the faces and shows them at once, without disturbing what runs. They stay through
        every run and reset. Raises an EngineError if a picture is invalid.
        """
        self._engine.set_environment(environment)
        self._present()

    def play(self, program: Any) -> None:
        """
        Checks the program and runs it from a clean cube. Raises a ProgramError, leaving everything as it was, if
        the program is invalid.
        """
        self._engine.load(program)
        self._engine.start(self._loop.now())
        self._loop.start(self._tick)
        self._sync()
        self._present()

    def move_object(self, name: str, face: FaceName, x: int, y: int, heading: HeadingName | None = None) -> None:
        """
        Puts an object on a cell right away. See `CubeEngine.move_object`.
        """
        self._engine.move_object(name, face, x, y, heading)
        self._present()

    def set_hidden(self, names: list[str]) -> None:
        """
        Keeps some objects out of sight (a hidden layer). See `CubeEngine.set_hidden`.
        """
        self._engine.set_hidden(names)
        self._present()

    def frame_of(self, name: str, padding: int = 0) -> Frame:
        """
        The rectangle of an object on the cube, grown by `padding` cells. See `CubeEngine.frame_of`.
        """
        return self._engine.frame_of(name, padding)

    def grab_at(self, face: Face, x: int, y: int, padding: int, preferred: str | None = None) -> Grab | None:
        """
        The object a press on a pixel grabs. See `CubeEngine.grab_at`.
        """
        return self._engine.grab_at(face, x, y, padding, preferred)

    def placement_at(self, face: Face, x: int, y: int) -> Placement | None:
        """
        Where a `create` block must put an object so its center lands on a pixel, or None when objects cannot be
        placed there.
        """
        return self._engine.placement_at(face, x, y)

    def preview(self, objects: list[CreateCommand]) -> None:
        """
        Shows objects on the cube without running anything: a program with no scripts, so the objects sit where
        they start. Does nothing while a program is running. Raises a ProgramError if the objects are invalid.
        """
        if self._engine.running:
            return

        self._engine.load({"version": 1, "objects": objects, "scripts": []})
        self._present()

    def stop(self) -> None:
        """
        Stops the scripts. The cube keeps what it shows.
        """
        self._engine.stop()
        self._sync()

    def reset(self) -> None:
        """
        Stops the scripts and clears the cube back to the environment.
        """
        self._engine.reset()
        self._sync()
        self._present()

    def dispose(self) -> None:
        """
        Stops everything for good. The player cannot be used afterwards.
        """
        self._loop.stop()

    def _clock_argument(self) -> dict[str, Callable[[], float]]:
        """
        The clock to give the run loop, if the options bring one.
        """
        clock = self._options.get("clock")

        return {} if clock is None else {"clock": clock}

    def _tick(self, now: float) -> None:
        """
        One tick of the timer: lets the engine run, and shows what changed.
        """
        self._engine.tick(now)
        self._sync()
        self._present()

    def _sync(self) -> None:
        """
        Stops the timer when nothing is running any more, and reports changes of status.
        """
        running = self._engine.running

        if not running:
            self._loop.stop()

        if running != self._reported_running:
            self._reported_running = running

            on_running_change = self._options.get("on_running_change")

            if on_running_change is not None:
                on_running_change(running)

    def _present(self) -> None:
        """
        Hands the state to `on_frame` when it changed since the last time.
        """
        on_frame = self._options.get("on_frame")
        version = self.state.version

        if on_frame is None or version == self._presented_version:
            return

        self._presented_version = version

        on_frame(self.state)
