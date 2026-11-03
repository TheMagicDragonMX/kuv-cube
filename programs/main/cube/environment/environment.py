"""
LAYER: environment.

What surrounds the objects of the sandbox and is not part of any program: for now, the images the user puts on the
faces. A program is the code of the user; the environment is the stage it runs on. That is why it is passed to the
engine next to the program, not inside it, and why it is still there when the program stops or is run again.

    environment --painted onto--> World.background <--read by-- renderer

It goes through the background layer. The background blocks of a program (change background image, change background
color) write to the same layer while it runs, so they can replace the pictures; the environment is where the cube
starts, and a reset brings it back. Objects always draw over the layer and never change it.

To get the pixels of a face from a picture, see `pixelate.py`.
"""

from typing import Sequence, TypeAlias, TypedDict

from programs.main.cube.drawing.bitmap import draw_bitmap
from programs.main.cube.errors import EngineError
from programs.main.cube.program.names import FACE_BY_NAME
from programs.main.cube.program.program import FaceName
from programs.main.cube.state.cube_state import FACE_RESOLUTION, Color
from programs.main.cube.world.world import World


BackgroundImages: TypeAlias = dict[FaceName, Sequence[Color]]
"""
The picture of each face that has one: `FACE_RESOLUTION * FACE_RESOLUTION` colors, row after row. A face that is not
in it keeps the plain background.
"""


class Environment(TypedDict, total=False):
    """
    The settings of the stage.
    """

    background: BackgroundImages
    """
    Pictures behind the objects, by face.
    """


FACE_PIXELS = FACE_RESOLUTION * FACE_RESOLUTION
"""
Pixels on one face.
"""


def paint_environment(world: World, environment: Environment | None = None, previous: Environment | None = None) -> None:
    """
    Paints the environment onto the background of a world.

    With `previous` (the environment that was there before) a face that had a picture and no longer does is
    blanked, so removing a picture takes it off the cube. Raises an EngineError, before painting anything, if a
    picture does not have the size of a face.
    """
    images = ((environment or {}).get("background") or {}).items()
    before = (previous or {}).get("background") or {}
    now = (environment or {}).get("background") or {}

    for name, pixels in images:
        if len(pixels) != FACE_PIXELS:
            raise EngineError(f"The picture of {name} must have {FACE_PIXELS} pixels, not {len(pixels)}")

    for name in before:
        if not now.get(name):
            paint(world, name, [0] * FACE_PIXELS)

    for name, pixels in images:
        paint(world, name, pixels)


def paint(world: World, name: FaceName, pixels: Sequence[Color]) -> None:
    """
    Copies the picture of one face onto the background.
    """
    draw_bitmap(world.background, FACE_BY_NAME[name], 0, 0, FACE_RESOLUTION, FACE_RESOLUTION, pixels)
