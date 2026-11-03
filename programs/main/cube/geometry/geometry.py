"""
LAYER: geometry.

Answers one question: "if an object steps this way, where does it end up?". It knows how the five faces connect, so
nothing else has to think about edges, corners or rotations.

The cube is modeled as two surfaces:

    strip  the four sides (FRONT, RIGHT, BACK, LEFT) as one 256x64 band that wraps around
    top    the top face, 64x64, stored as seen from above with FRONT at the bottom

Every object has a Pose: a surface, a cell and a heading. The heading is the direction the object's own "up"
points. Steps (up/right/down/left) are relative to it, and crossing an edge between a side and the top rotates the
heading, so an object that keeps "going up" keeps going the same way. The full explanation, with the edge table, is
in CUBE_DESIGN.md of the web app (sections 4 and 5).

Pure logic: no state, no hardware. Everything here is a function of its inputs.
"""

from enum import IntEnum
from typing import Literal, NotRequired, TypeAlias, TypedDict

from programs.main.cube.state.cube_state import FACE_RESOLUTION, Face


class Heading(IntEnum):
    """
    Direction on a surface, as seen from outside the cube. The values are quarter turns clockwise from north, so
    adding a number rotates a direction.
    """

    NORTH = 0
    """
    Facing the top of the surface.
    """

    EAST = 1
    """
    Facing its right.
    """

    SOUTH = 2
    """
    Facing the bottom.
    """

    WEST = 3
    """
    Facing its left.
    """


HEADINGS = (Heading.NORTH, Heading.EAST, Heading.SOUTH, Heading.WEST)
"""
The headings by value, so a rotated direction is found with an index and not by building an enum member.
"""

Step: TypeAlias = Literal["up", "right", "down", "left"]
"""
A move relative to the heading of the object: "up" goes where the object's up points.
"""

STEP_TURNS: dict[str, int] = {
    "up": 0,
    "right": 1,
    "down": 2,
    "left": 3,
}
"""
Where a relative step points, in quarter turns clockwise from the heading.
"""

SIDES = (Face.FRONT, Face.RIGHT, Face.BACK, Face.LEFT)
"""
The four side faces in the order they appear going right around the cube. Together they form the strip.
"""

STRIP_WIDTH = len(SIDES) * FACE_RESOLUTION
"""
Width of the strip, in cells.
"""

Surface: TypeAlias = Literal["strip", "top"]
"""
Surface an object lives on: the wrapping strip of the four sides, or the top face.
"""


class Pose(TypedDict):
    """
    Where an object is and which way it faces.

    On the strip, x runs 0..STRIP_WIDTH-1 (wrapping) and y grows downward from the top row. On the top face the
    coordinates are the ones stored in the cube state: seen from above with the front at the bottom. Headings are
    directions on the screen of that surface.
    """

    surface: Surface
    """
    The surface the object is on.
    """

    x: int
    """
    Column on that surface.
    """

    y: int
    """
    Row on that surface.
    """

    heading: Heading
    """
    The way the object faces.
    """


class Placement(TypedDict):
    """
    Where a user puts a new object. For a side face, x and y are local to that face. For the top face they follow
    the configured top anchor (see `GeometryConfig`), and so does the heading.
    """

    face: Face
    """
    The face to place the object on.
    """

    x: int
    """
    Column on that face.
    """

    y: int
    """
    Row on that face.
    """

    heading: NotRequired[Heading | None]
    """
    The way the object faces. North when omitted.
    """


class FacePixel(TypedDict):
    """
    A pixel of the cube state.
    """

    face: Face
    """
    The face the pixel belongs to.
    """

    x: int
    """
    Column on that face.
    """

    y: int
    """
    Row on that face.
    """


Offset: TypeAlias = tuple[int, int]
"""
A step of the pixel (x, y).
"""


class Cell(TypedDict):
    """
    A pixel of the cube with the way an object's axes point on it.
    """

    pixel: FacePixel
    """
    The pixel.
    """

    right: Offset
    """
    Which way the object's right points on the face, as a step of the pixel (x, y).
    """

    down: Offset
    """
    Which way the object's down points on the face, as a step of the pixel (x, y).
    """


class GeometryConfig(TypedDict, total=False):
    """
    Settings of the geometry. Both are optional.
    """

    floor: int | None
    """
    Last row objects can reach on the sides. Rows below the last visible one exist but are not drawn. Defaults to
    the last visible row.
    """

    top_anchor: Face | None
    """
    Side that is at the bottom of the top face when placing objects on it, and whose opposite is where a
    north-facing object on the top face heads to. It only decides how the top face is addressed and never changes
    how objects move. Defaults to FRONT.
    """


OFFSETS: tuple[Offset, ...] = (
    (0, -1),
    (1, 0),
    (0, 1),
    (-1, 0),
)
"""
Screen offset of one cell in each direction, indexed by Heading.
"""

SIDE_DIRECTION_ON_TOP: dict[Face, Heading] = {
    Face.FRONT: Heading.SOUTH,
    Face.RIGHT: Heading.EAST,
    Face.BACK: Heading.NORTH,
    Face.LEFT: Heading.WEST,
}
"""
Direction, on the top face as stored, in which each side lies.
"""


def turn(heading: int, quarter_turns: int) -> Heading:
    """
    Rotates a direction by quarter turns clockwise. Keeping the last two bits is the same as a positive modulo 4,
    negative turns included, and it is cheap enough for the renderer to call for every pixel.
    """
    return HEADINGS[(heading + quarter_turns) & 3]


def _is_integer(value: object) -> bool:
    """
    True for whole numbers. A boolean is not one.
    """
    return isinstance(value, int) and not isinstance(value, bool)


def rotate_cell(x: int, y: int, quarter_turns: int) -> Offset:
    """
    Rotates a cell of the top face by quarter turns clockwise around the face center.
    """
    rotated_x, rotated_y = x, y

    for _ in range(quarter_turns % 4):
        rotated_x, rotated_y = FACE_RESOLUTION - 1 - rotated_y, rotated_x

    return rotated_x, rotated_y


def straight_offset(pose: Pose, dx: int, dy: int) -> Offset:
    """
    Where the cell `dx` right and `dy` down from a pose would be if the surface had no edges: plain arithmetic in
    the frame of the pose, as [x, y] on the pose's surface, without wrapping. While the walk stays on its surface
    (the strip below its top row, or inside the top face) this is the right answer, because the heading only
    changes when an edge is crossed. The sideways and the vertical part of the walk are perpendicular, so if the end
    is still on the surface, every cell on the way was too.
    """

    # Left is minus right and up is minus down, so a negative dx or dy needs no case of its own.
    right_x, right_y = OFFSETS[turn(pose["heading"], STEP_TURNS["right"])]
    down_x, down_y = OFFSETS[turn(pose["heading"], STEP_TURNS["down"])]

    return pose["x"] + right_x * dx + down_x * dy, pose["y"] + right_y * dx + down_y * dy


class CubeGeometry:
    """
    Knows how the surfaces of the cube connect: moves objects across the edges of the strip and the top face,
    keeping their sense of "up", and maps them to cube state pixels.
    """

    def __init__(self, config: GeometryConfig | None = None) -> None:
        """
        Builds the geometry from the settings, using defaults for what is missing.
        """
        config = config or {}

        floor = config.get("floor")
        top_anchor = config.get("top_anchor")

        if floor is None:
            floor = FACE_RESOLUTION - 1

        if top_anchor is None:
            top_anchor = Face.FRONT

        if not _is_integer(floor) or floor < 0:
            raise ValueError(f"The floor must be a row number, got {floor}")

        if top_anchor not in SIDES:
            raise ValueError("The top anchor must be a side face")

        self.floor = floor
        """
        Last row objects can reach on the sides.
        """

        self.top_anchor = top_anchor
        """
        Side at the bottom of the top face when addressing it.
        """

        self._anchor_turns = turn(SIDE_DIRECTION_ON_TOP[top_anchor], -Heading.SOUTH)
        """
        Quarter turns clockwise from the addressed top face to the stored one.
        """

    def place(self, placement: Placement) -> Pose:
        """
        Turns a placement into a pose. The heading defaults to north.
        """
        face, x, y = placement["face"], placement["x"], placement["y"]
        heading = placement.get("heading")

        if heading is None:
            heading = Heading.NORTH

        is_cell = _is_integer(x) and _is_integer(y) and 0 <= x < FACE_RESOLUTION and 0 <= y

        if face == Face.TOP:
            if not is_cell or y >= FACE_RESOLUTION:
                raise ValueError(f"Cell ({x}, {y}) is outside the top face")

            stored_x, stored_y = rotate_cell(x, y, self._anchor_turns)

            return {
                "surface": "top",
                "x": stored_x,
                "y": stored_y,
                "heading": turn(heading, self._anchor_turns),
            }

        if face not in SIDES:
            raise ValueError(f"Unknown face {face}")

        if not is_cell or y > self.floor:
            raise ValueError(f"Cell ({x}, {y}) is outside the side face")

        return {"surface": "strip", "x": SIDES.index(face) * FACE_RESOLUTION + x, "y": y, "heading": heading}

    def placement_of(self, pixel: FacePixel) -> Placement | None:
        """
        The placement that puts an object on a pixel of the cube state, or None if objects cannot be placed there
        (below the floor of the sides). It is the inverse of `place` for the position; the top face is addressed
        through the top anchor.
        """
        if pixel["face"] == Face.TOP:
            x, y = rotate_cell(pixel["x"], pixel["y"], -self._anchor_turns)

            return {"face": Face.TOP, "x": x, "y": y}

        if pixel["face"] in SIDES and pixel["y"] <= self.floor:
            return {"face": pixel["face"], "x": pixel["x"], "y": pixel["y"]}

        return None

    def move(self, pose: Pose, step: Step, count: int = 1) -> Pose:
        """
        Moves a pose a number of cells in a direction relative to its heading, one cell at a time. Crossing an edge
        keeps the object facing the way it was going, so the heading changes with respect to the screen. The move
        stops early at the floor.
        """
        if not _is_integer(count) or count < 0:
            raise ValueError(f"The number of cells must be a non-negative integer, got {count}")

        turns = STEP_TURNS[step]
        current = pose

        for _ in range(count):
            following = self._advance(current, turn(current["heading"], turns))

            if following is None:
                break

            current = following

        return current

    def offset(self, pose: Pose, dx: int, dy: int) -> Pose | None:
        """
        Finds the pose of the cell `dx` cells to the right and `dy` cells down from a pose, in the frame of the
        pose: a negative `dx` is to the left and a negative `dy` is up. The walk goes sideways first and then
        vertically, crossing edges like `move` does, so the result is the cell a shape pixel at that offset covers.
        Returns None if the walk is blocked by the floor.
        """
        if not _is_integer(dx) or not _is_integer(dy):
            raise ValueError(f"The offset must be whole numbers, got ({dx}, {dy})")

        # The walk only needs to follow the edges when it leaves the surface it started on: over the top of the
        # strip, or off the top face. Anywhere else the answer is plain arithmetic on the cell.
        x, y = straight_offset(pose, dx, dy)

        if pose["surface"] == "strip":
            if y > self.floor:
                return None

            if y >= 0:
                return {**pose, "x": x % STRIP_WIDTH, "y": y}

        elif 0 <= x < FACE_RESOLUTION and 0 <= y < FACE_RESOLUTION:
            return {**pose, "x": x, "y": y}

        sideways = self._walk(pose, "right" if dx > 0 else "left", abs(dx))

        return sideways and self._walk(sideways, "down" if dy > 0 else "up", abs(dy))

    def cell_at(self, pose: Pose, dx: int, dy: int) -> Cell | None:
        """
        Like `pixel_at`, and also says which way the object's right and down point on the face at that cell, as
        steps of the pixel (x, y). They differ from (1, 0) and (0, 1) after the object has turned around an edge,
        so they tell how a shape that wraps over an edge is laid out on each face.
        """
        cell = self.offset(pose, dx, dy)
        pixel = cell and self.to_pixel(cell)

        if not cell or not pixel:
            return None

        return {
            "pixel": pixel,
            "right": OFFSETS[turn(cell["heading"], STEP_TURNS["right"])],
            "down": OFFSETS[turn(cell["heading"], STEP_TURNS["down"])],
        }

    def pixel_at(self, pose: Pose, dx: int, dy: int) -> FacePixel | None:
        """
        Finds the cube state pixel that the cell `dx` right and `dy` down from a pose is drawn on, or None if there
        is none. It is `to_pixel(offset(pose, dx, dy))` without making the pose in between, because the renderer
        asks this for every pixel of every shape.
        """

        # The same arithmetic as `straight_offset`, written out because this runs for every pixel of every shape.
        heading = pose["heading"]
        right = OFFSETS[(heading + STEP_TURNS["right"]) & 3]
        down = OFFSETS[(heading + STEP_TURNS["down"]) & 3]
        x = pose["x"] + right[0] * dx + down[0] * dy
        y = pose["y"] + right[1] * dx + down[1] * dy

        if pose["surface"] == "strip":
            if 0 <= y < FACE_RESOLUTION and y <= self.floor:
                column = x % STRIP_WIDTH

                return {"face": SIDES[column // FACE_RESOLUTION], "x": column % FACE_RESOLUTION, "y": y}

        elif 0 <= x < FACE_RESOLUTION and 0 <= y < FACE_RESOLUTION:
            return {"face": Face.TOP, "x": x, "y": y}

        moved = self.offset(pose, dx, dy)

        return moved and self.to_pixel(moved)

    def point_up(self, pose: Pose) -> Pose:
        """
        Resets the heading of a pose to "up" as the user sees it. On the strip that is north. On the top face it is
        north of the addressed top face, which depends on the top anchor.
        """
        heading = turn(Heading.NORTH, self._anchor_turns) if pose["surface"] == "top" else Heading.NORTH

        return {**pose, "heading": heading}

    def to_pixel(self, pose: Pose) -> FacePixel | None:
        """
        Finds the cube state pixel a pose is drawn on, or None if it is below the visible rows.
        """
        if pose["surface"] == "top":
            return {"face": Face.TOP, "x": pose["x"], "y": pose["y"]}

        if pose["y"] >= FACE_RESOLUTION:
            return None

        return {
            "face": SIDES[pose["x"] // FACE_RESOLUTION],
            "x": pose["x"] % FACE_RESOLUTION,
            "y": pose["y"],
        }

    def _walk(self, pose: Pose, step: Step, count: int) -> Pose | None:
        """
        Like `move`, but returns None instead of stopping early when the floor is in the way.
        """
        current: Pose | None = pose

        for _ in range(count):
            if current is None:
                break

            current = self._advance(current, turn(current["heading"], STEP_TURNS[step]))

        return current

    def _advance(self, pose: Pose, direction: int) -> Pose | None:
        """
        Moves a pose one cell towards a direction of the screen, or returns None if blocked.
        """
        dx, dy = OFFSETS[direction]
        x = pose["x"] + dx
        y = pose["y"] + dy

        if pose["surface"] == "strip":
            if y > self.floor:
                return None

            if y < 0:
                return self._enter_top(pose, direction)

            return {**pose, "x": x % STRIP_WIDTH, "y": y}

        if x < 0 or x >= FACE_RESOLUTION or y < 0 or y >= FACE_RESOLUTION:
            return self._leave_top(pose, direction)

        return {**pose, "x": x, "y": y}

    def _enter_top(self, pose: Pose, direction: int) -> Pose:
        """
        Crosses from the top row of a side onto the top face, going north.
        """
        last = FACE_RESOLUTION - 1
        side = SIDES[pose["x"] // FACE_RESOLUTION]
        column = pose["x"] % FACE_RESOLUTION

        if side == Face.FRONT:
            cell, arriving = (column, last), Heading.NORTH

        elif side == Face.RIGHT:
            cell, arriving = (last, last - column), Heading.WEST

        elif side == Face.BACK:
            cell, arriving = (last - column, 0), Heading.SOUTH

        else:
            cell, arriving = (0, column), Heading.EAST

        return {
            "surface": "top",
            "x": cell[0],
            "y": cell[1],
            "heading": turn(pose["heading"], arriving - direction),
        }

    def _leave_top(self, pose: Pose, direction: int) -> Pose:
        """
        Crosses from an edge of the top face down onto the side that lies there, going south.
        """
        last = FACE_RESOLUTION - 1

        if direction == Heading.NORTH:
            strip_x = SIDES.index(Face.BACK) * FACE_RESOLUTION + last - pose["x"]

        elif direction == Heading.EAST:
            strip_x = SIDES.index(Face.RIGHT) * FACE_RESOLUTION + last - pose["y"]

        elif direction == Heading.SOUTH:
            strip_x = SIDES.index(Face.FRONT) * FACE_RESOLUTION + pose["x"]

        else:
            strip_x = SIDES.index(Face.LEFT) * FACE_RESOLUTION + pose["y"]

        return {
            "surface": "strip",
            "x": strip_x,
            "y": 0,
            "heading": turn(pose["heading"], Heading.SOUTH - direction),
        }
