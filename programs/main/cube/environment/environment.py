"""
LAYER: environment.

What surrounds the objects of the sandbox and is not part of any program: the images the user puts on the faces, the
backgrounds a program can switch between, and how bright the LEDs are. A program is the code of the user; the
environment is the stage it runs on. That is why it is passed to the
engine next to the program, not inside it, and why it is still there when the program stops or is run again.

    environment --painted onto--> World.background <--read by-- renderer

It goes through the background layer. The background blocks of a program (change background image, change background
color) write to the same layer while it runs, so they can replace the pictures; the environment is where the cube
starts, and a reset brings it back. Objects always draw over the layer and never change it.

The backgrounds are a list of named sets of pictures. The environment hands them to the world, where the blocks
"change background to" and "next background" find them; `background` is the one the cube starts with, and
`startBackground` says which of the list it is.

To get the pixels of a face from a picture, see `pixelate.py`.
"""

from typing import Sequence, TypeAlias, TypedDict

from programs.main.cube.drawing.bitmap import draw_bitmap
from programs.main.cube.errors import EngineError
from programs.main.cube.program.names import FACE_BY_NAME
from programs.main.cube.program.program import FaceName
from programs.main.cube.renderer.renderer import Brightness
from programs.main.cube.state.cube_state import FACE_RESOLUTION, Color
from programs.main.cube.world.world import NamedBackground, World


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

    backgrounds: list[NamedBackground]
    """
    The backgrounds a program can switch to, in order. Their names are not repeated.
    """

    startBackground: str
    """
    Name of the background of `backgrounds` that `background` is, the one the cube starts with. The next background
    after it is the following one of the list.
    """

    brightness: Brightness
    """
    How intensely the background and the objects shine. What is missing is full intensity.
    """


FACE_PIXELS = FACE_RESOLUTION * FACE_RESOLUTION
"""
Pixels on one face.
"""


def paint_environment(world: World, environment: Environment | None = None, previous: Environment | None = None) -> None:
    """
    Paints the environment onto the background of a world.

    With `previous` (the environment that was there before) a face that had a picture and no longer does is
    blanked, so removing a picture takes it off the cube. It also gives the world the backgrounds a program can switch
    to. Raises an EngineError, before changing anything, if a picture does not have the size of a face or two
    backgrounds have the same name.
    """
    environment = environment or {}
    now = environment.get("background") or {}
    before = (previous or {}).get("background") or {}
    backgrounds = environment.get("backgrounds") or []

    check_images(now, "The picture of")

    for background in backgrounds:
        check_images(background["images"], f'The picture of the background "{background["name"]}" on')

    if len({background["name"] for background in backgrounds}) != len(backgrounds):
        raise EngineError("Two backgrounds have the same name")

    world.backgrounds = list(backgrounds)
    world.current_background = environment.get("startBackground")

    for name in before:
        if not now.get(name):
            paint(world, name, [0] * FACE_PIXELS)

    for name, pixels in now.items():
        paint(world, name, pixels)


def check_images(images: BackgroundImages, what: str) -> None:
    """
    Raises an EngineError if a picture does not have the size of a face. `what` starts the message.
    """
    for name, pixels in images.items():
        if len(pixels) != FACE_PIXELS:
            raise EngineError(f"{what} {name} must have {FACE_PIXELS} pixels, not {len(pixels)}")


def paint(world: World, name: FaceName, pixels: Sequence[Color]) -> None:
    """
    Copies the picture of one face onto the background.
    """
    draw_bitmap(world.background, FACE_BY_NAME[name], 0, 0, FACE_RESOLUTION, FACE_RESOLUTION, pixels)
