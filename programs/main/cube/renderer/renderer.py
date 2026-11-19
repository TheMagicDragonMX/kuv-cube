"""
LAYER: renderer.

Turns the world into pixels. This is the only place where "an object at this pose" becomes "this pixel has this
color".

    World --read by--> Renderer --writes--> CubeState (output)

Each frame is built the same way:

    1. start from the background layer (one bulk copy)
    2. find the faces that have an object on them, and dim the background of those faces
    3. draw every visible object on top, in the order they were created, pixel by pixel, at the intensity of the
       objects

A face with objects shows its background softer than a face without, so the objects can be told apart from the
picture behind them. Everything starts at full intensity (nothing is dimmed) until `set_brightness` is called.

Nothing is erased pixel by pixel: because every frame starts from the background, an object that moved simply is not
drawn where it used to be.

The renderer remembers the world version it last drew and does nothing if it has not changed, so a cube with nothing
moving costs nothing per tick.
"""

from typing import Any, TypedDict

from programs.main.cube.state.cube_state import FACE_COUNT, CubeState, scale_color
from programs.main.cube.world.world import World


class Brightness(TypedDict, total=False):
    """
    How intense the LEDs shine, as a share of their color: 1 is the color as it is, 0 is off. A missing one is full.
    """

    background: float
    """
    Intensity of the background on a face that has no objects.
    """

    behindObjects: float
    """
    Intensity of the background on a face that has objects on it.
    """

    objects: float
    """
    Intensity of the objects.
    """


FULL_BRIGHTNESS: Brightness = {"background": 1, "behindObjects": 1, "objects": 1}
"""
Nothing dimmed: what the renderer uses until it is told otherwise.
"""

DEFAULT_BRIGHTNESS: Brightness = {"background": 1, "behindObjects": 0.4, "objects": 1}
"""
What the editor starts with: the background at full intensity until objects are on a face, then softer (40%), so the
edge between them is easy to see.
"""


def level(value: Any) -> float:
    """
    Keeps an intensity between 0 and 1. A missing one (or one that is not a number) is full.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return 1

    return min(1, max(0, value))


class Renderer:
    """
    Draws the world onto the cube state, only when the world changed since the last draw.
    """

    def __init__(self, world: World, output: CubeState) -> None:
        """
        Draws `world` onto `output`, which the view reads.
        """
        self._world = world
        """
        What to draw.
        """

        self.output = output
        """
        Where to draw it.
        """

        self._rendered_version = -1
        """
        World version the output currently shows. -1 means nothing has been drawn yet.
        """

        self._brightness: Brightness = dict(FULL_BRIGHTNESS)
        """
        Intensity of the background and of the objects.
        """

    def set_brightness(self, brightness: Brightness | None) -> None:
        """
        Changes the intensities (a missing one is full). The next `render` draws everything again with it.
        """
        brightness = brightness or {}

        self._brightness = {
            "background": level(brightness.get("background")),
            "behindObjects": level(brightness.get("behindObjects")),
            "objects": level(brightness.get("objects")),
        }
        self._rendered_version = -1

    def render(self) -> bool:
        """
        Redraws the output if the world changed since the last call. Returns whether anything was drawn.
        """
        if self._rendered_version == self._world.version:
            return False

        self.output.copy_from(self._world.background)

        geometry = self._world.geometry
        objects_level = self._brightness["objects"]

        # Where every pixel of the visible objects lands, in drawing order, and which faces they land on. The
        # geometry finds each pixel across edges too; pixels below the last visible row have no cell, so they are
        # simply not drawn.
        drawn: list[tuple[int, int, int, int]] = []
        covered: set[int] = set()

        for cube_object in self._world.all():
            if not cube_object["visible"]:
                continue

            for part in cube_object["shape"]:
                pixel = geometry.pixel_at(cube_object["pose"], part["dx"], part["dy"])

                if pixel is not None:
                    color = part.get("color")
                    color = cube_object["color"] if color is None else color

                    drawn.append((pixel["face"], pixel["x"], pixel["y"], scale_color(color, objects_level)))
                    covered.add(pixel["face"])

        for face in range(FACE_COUNT):
            self.output.dim_face(face, self._brightness["behindObjects" if face in covered else "background"])

        for face, x, y, color in drawn:
            self.output.set(face, x, y, color)

        self._rendered_version = self._world.version

        return True
