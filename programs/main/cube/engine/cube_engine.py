"""
LAYER: engine (facade).

Puts the layers together behind a small interface, so nothing outside needs to know how they fit:

    program --validate--> World <--commands-- Scheduler --runs--> Interpreter
    environment --paints background of--> |
                            |
                            '--read by--> Renderer --writes--> state (CubeState)

The engine is **pure and clock-free**: it never reads the time and never sets timers. The caller says what time it is
(`start(now)`, `tick(now)`, in milliseconds). That makes it trivial to test, and it is the same shape the TypeScript
engine of the web app has. `CubePlayer` is the one that adds a real clock.

Typical use:

    engine = CubeEngine()
    engine.load(program)   # checks the program; raises ProgramError if it is invalid
    engine.start(0)        # begins from a clean cube
    engine.tick(33)        # let time pass: scripts run, `engine.state` is updated
    engine.tick(66)
"""

from typing import Any, Callable, Literal, TypedDict

from programs.main.cube.commands.apply_command import apply_command
from programs.main.cube.environment.environment import Environment, paint_environment
from programs.main.cube.errors import EngineError
from programs.main.cube.geometry.geometry import GeometryConfig
from programs.main.cube.program.names import FACE_BY_NAME, FACE_NAME, HEADING_BY_NAME
from programs.main.cube.program.program import FaceName, HeadingName, Program, ProgramConfig
from programs.main.cube.program.validate_program import validate_program
from programs.main.cube.renderer.renderer import Renderer
from programs.main.cube.runtime.scheduler import Scheduler, ScriptError
from programs.main.cube.state.cube_state import CubeState, Face
from programs.main.cube.world.cube_object import CubeObject
from programs.main.cube.world.world import World


class Outline(TypedDict):
    """
    A rectangle of cells on one face, corners included.
    """

    face: Face
    """
    The face the rectangle is on.
    """

    x0: int
    """
    Leftmost column.
    """

    y0: int
    """
    Top row.
    """

    x1: int
    """
    Rightmost column.
    """

    y1: int
    """
    Bottom row.
    """


class Edge(TypedDict):
    """
    One side of a cell on a face.
    """

    face: Face
    """
    The face the cell is on.
    """

    x: int
    """
    Column of the cell.
    """

    y: int
    """
    Row of the cell.
    """

    side: Literal["left", "right", "top", "bottom"]
    """
    Which side of the cell.
    """


class Frame(TypedDict):
    """
    The rectangle of an object on the cube: its part on each face, and the sides of cells that draw its outline.
    """

    boxes: list[Outline]
    """
    The part of the rectangle on each face it reaches.
    """

    edges: list[Edge]
    """
    The sides of cells that make up its outline.
    """


class Center(TypedDict):
    """
    A pixel of the cube.
    """

    face: Face
    """
    The face of the pixel.
    """

    x: int
    """
    Column on the face.
    """

    y: int
    """
    Row on the face.
    """


class Grab(TypedDict):
    """
    What a press on the cube grabs: an object, and the pixel of its center.
    """

    name: str
    """
    The object.
    """

    center: Center | None
    """
    The pixel of its center, or None if it is not on a visible cell.
    """


class Placement(TypedDict):
    """
    Where a `create` block must put an object.
    """

    face: FaceName
    """
    The face to put the object on.
    """

    x: int
    """
    Column on that face.
    """

    y: int
    """
    Row on that face.
    """


class CubeEngineOptions(TypedDict, total=False):
    """
    Settings of the engine.
    """

    defaults: ProgramConfig | None
    """
    Engine settings to use when a program does not set its own (top anchor, floor).
    """

    on_error: Callable[[ScriptError], None]
    """
    Called when a script has to stop because of a problem while running.
    """


class CubeEngine:
    """
    Loads a program, runs it on a world and keeps `state` up to date with what the cube shows.
    """

    def __init__(self, options: CubeEngineOptions | None = None) -> None:
        """
        Builds the engine with the given options.
        """
        self._options: CubeEngineOptions = options or {}
        """
        Settings and callbacks the engine runs with.
        """

        self.state = CubeState()
        """
        What the cube shows. The same object for the whole life of the engine, so a view can hold on to it. Updated
        by `tick`.
        """

        self._program: Program = {"version": 1, "scripts": []}
        """
        The loaded program. Empty until `load` is called.
        """

        self._defaults = self._options.get("defaults")
        """
        Engine settings used when the program does not set its own.
        """

        self._environment: Environment | None = None
        """
        The stage the program runs on (images on the faces). It outlives programs: every start and reset paints it
        again.
        """

        self._hidden: set[str] = set()
        """
        Objects kept out of sight by the user (see `set_hidden`).
        """

        self._world: World
        """
        The objects and background the program acts on.
        """

        self._renderer: Renderer
        """
        Paints the world onto `state`.
        """

        self._scheduler: Scheduler
        """
        Runs the program's scripts over time.
        """

        self._build()

    @property
    def running(self) -> bool:
        """
        True while a script is still running or may run again (an "every" script).
        """
        return self._scheduler.active

    def set_defaults(self, defaults: ProgramConfig | None) -> None:
        """
        Changes the settings used when a program does not set its own. They apply from the next `start` or `reset`;
        what is running is not disturbed.
        """
        self._defaults = defaults

    def set_environment(self, environment: Environment | None) -> None:
        """
        Changes the environment and shows it right away, even if nothing is running. A program that is running is
        not restarted: the new pictures are painted on its background, and a face whose picture was removed goes
        black. Raises an EngineError, leaving everything as it was, if a picture is not the size of a face.
        """
        paint_environment(self._world, environment, self._environment)

        self._environment = environment
        self._renderer.render()

    def move_object(self, name: str, face: FaceName, x: int, y: int, heading: HeadingName | None = None) -> None:
        """
        Puts an object on a cell right away, without loading the program again. Raises an EngineError if there is
        no such object, and a ValueError if the cell is outside the cube.
        """
        self._world.update(
            name,
            {
                "pose": self._world.geometry.place(
                    {"face": FACE_BY_NAME[face], "x": x, "y": y, "heading": HEADING_BY_NAME[heading] if heading else None}
                ),
            },
        )
        self._renderer.render()

    def set_hidden(self, names: list[str]) -> None:
        """
        Chooses the objects that are kept out of sight, like a hidden layer: they still exist and move, they are
        just not drawn. It applies at once, and again on every start and reset. Names with no object are ignored.
        """
        previous = self._hidden

        self._hidden = set(names)

        for name in previous:
            if name not in self._hidden:
                self._set_visible(name, True)

        self._apply_hidden()
        self._renderer.render()

    def frame_of(self, name: str, padding: int = 0) -> Frame:
        """
        The frame of an object: its rectangle (the cells of its shape grown by `padding` cells on every side) as it
        lies on the cube. The rectangle is one thing in the frame of the object, so where it goes over an edge it
        continues on the next face: `boxes` are the parts on each face, and `edges` are the sides of cells that make
        up its outline, which does not run along the edges of the cube. Empty if the object is hidden or does not
        exist.
        """
        frame: Frame = {"boxes": [], "edges": []}

        try:
            cube_object = self._world.get(name)

        except EngineError:
            return frame

        if not cube_object["visible"]:
            return frame

        columns = [part["dx"] for part in cube_object["shape"]]
        rows = [part["dy"] for part in cube_object["shape"]]
        left, right = min(columns) - padding, max(columns) + padding
        top, bottom = min(rows) - padding, max(rows) + padding
        boxes: dict[Face, Outline] = {}

        for dy in range(top, bottom + 1):
            for dx in range(left, right + 1):
                cell = self._world.geometry.cell_at(cube_object["pose"], dx, dy)

                if cell is None:
                    continue

                pixel = cell["pixel"]
                box = boxes.get(pixel["face"])

                if box is not None:
                    box["x0"] = min(box["x0"], pixel["x"])
                    box["y0"] = min(box["y0"], pixel["y"])
                    box["x1"] = max(box["x1"], pixel["x"])
                    box["y1"] = max(box["y1"], pixel["y"])

                else:
                    boxes[pixel["face"]] = {
                        "face": pixel["face"],
                        "x0": pixel["x"],
                        "y0": pixel["y"],
                        "x1": pixel["x"],
                        "y1": pixel["y"],
                    }

                # Each side of the rectangle, in the direction it points on this face.
                sides = [
                    (dx == left, -cell["right"][0], -cell["right"][1]),
                    (dx == right, cell["right"][0], cell["right"][1]),
                    (dy == top, -cell["down"][0], -cell["down"][1]),
                    (dy == bottom, cell["down"][0], cell["down"][1]),
                ]

                for on_side, side_x, side_y in sides:
                    if not on_side:
                        continue

                    if side_x < 0:
                        side = "left"

                    elif side_x > 0:
                        side = "right"

                    elif side_y < 0:
                        side = "top"

                    else:
                        side = "bottom"

                    frame["edges"].append({"face": pixel["face"], "x": pixel["x"], "y": pixel["y"], "side": side})

        frame["boxes"] = list(boxes.values())

        return frame

    def grab_at(self, face: Face, x: int, y: int, padding: int, preferred: str | None = None) -> Grab | None:
        """
        The object a press on a pixel of the cube grabs. The target of an object is its rectangle grown by
        `padding` cells, so small objects are easy to hit. Among the objects whose target contains the pixel, the
        frontmost layer wins; if `preferred` is one of them it wins instead, which is how an object covered by
        others can still be reached. Also gives the pixel of the center of the object (None if it is not on a
        visible cell).
        """

        def contains(name: str) -> bool:
            """
            Whether the target of the object holds the pixel.
            """
            return any(
                box["face"] == face and box["x0"] <= x <= box["x1"] and box["y0"] <= y <= box["y1"]
                for box in self.frame_of(name, padding)["boxes"]
            )

        found: CubeObject | None = None

        for cube_object in self._world.all():
            if not (found is not None and found["name"] == preferred) and contains(cube_object["name"]):
                found = cube_object

        if found is None:
            return None

        return {"name": found["name"], "center": self._world.geometry.to_pixel(found["pose"])}

    def placement_at(self, face: Face, x: int, y: int) -> Placement | None:
        """
        The placement (face, x, y as in a `create` block) for a pixel of the cube, or None when objects cannot be
        placed there.
        """
        placement = self._world.geometry.placement_of({"face": face, "x": x, "y": y})

        if placement is None:
            return None

        return {"face": FACE_NAME[placement["face"]], "x": placement["x"], "y": placement["y"]}

    def load(self, program: Any) -> None:
        """
        Checks a program and keeps it, ready to start. Stops whatever was running and blanks the cube. If the
        program is invalid it raises a ProgramError and the engine is left as it was.
        """
        self._program = validate_program(program)

        self._build()

    def start(self, now: float) -> None:
        """
        Starts the loaded program from a clean cube. Starting again restarts from scratch. `now` is the current
        time in milliseconds.
        """
        self._build()
        self._scheduler.start(now)
        self.tick(now)

    def tick(self, now: float) -> None:
        """
        Lets time pass: scripts that are ready run, then the cube is redrawn if anything changed. `now` is the
        current time in milliseconds and must not go backwards.
        """
        self._scheduler.tick(now)
        self._renderer.render()

    def stop(self) -> None:
        """
        Stops the scripts. What is on the cube stays.
        """
        self._scheduler.stop()

    def reset(self) -> None:
        """
        Stops the scripts and blanks the cube.
        """
        self._build()

    def _apply_hidden(self) -> None:
        """
        Hides the objects chosen with `set_hidden` that exist in the current world.
        """
        for name in self._hidden:
            self._set_visible(name, False)

    def _set_visible(self, name: str, visible: bool) -> None:
        """
        Shows or hides one object, ignoring names with no object.
        """
        try:
            self._world.update(name, {"visible": visible})

        except EngineError:
            # No object with that name (yet): nothing to change.
            pass

    def _build(self) -> None:
        """
        Creates a fresh world, renderer and scheduler for the loaded program and draws the result: the environment
        and the objects the program starts with, because no script has run yet. Everything that changes while a
        program runs lives in those three, so replacing them is what gives every run a clean start.
        """
        self._world = World(self._geometry_config())
        self._renderer = Renderer(self._world, self.state)
        self._scheduler = Scheduler(self._world, self._program["scripts"], self._report)

        paint_environment(self._world, self._environment)

        for cube_object in self._program.get("objects", []):
            apply_command(self._world, cube_object)

        self._apply_hidden()
        self.state.fill(0)
        self._renderer.render()

    def _report(self, error: ScriptError) -> None:
        """
        Passes a script error on to whoever asked to hear about them.
        """
        on_error = self._options.get("on_error")

        if on_error is not None:
            on_error(error)

    def _geometry_config(self) -> GeometryConfig:
        """
        Geometry settings: what the program says, falling back to the engine defaults.
        """
        config = self._program.get("config") or {}
        defaults = self._defaults or {}
        top_anchor = config.get("topAnchor") or defaults.get("topAnchor")

        return {
            "top_anchor": FACE_BY_NAME[top_anchor] if top_anchor else None,
            "floor": config.get("floor", defaults.get("floor")),
        }
