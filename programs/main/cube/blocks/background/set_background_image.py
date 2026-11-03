"""
BLOCK: setBackgroundImage (background).

Puts a picture on some faces, replacing what they show behind the objects. The picture travels inside the block,
already shrunk to the pixels of a face (see `environment/pixelate.py`), so the program is all the Raspberry Pi needs.
"""

from typing import Literal, TypedDict

from programs.main.cube.blocks.block_definition import CommandDefinition
from programs.main.cube.blocks.fields import FIELD
from programs.main.cube.drawing.bitmap import draw_bitmap
from programs.main.cube.program.names import FACE_BY_NAME, parse_color
from programs.main.cube.program.program import ColorValue, FaceName
from programs.main.cube.state.cube_state import FACE_RESOLUTION
from programs.main.cube.world.world import World


class SetBackgroundImageCommand(TypedDict):
    """
    Puts a picture on the background of each face in `faces`. `pixels` has `FACE_RESOLUTION * FACE_RESOLUTION`
    colors, row after row.
    """

    op: Literal["setBackgroundImage"]
    """
    Identifies the command.
    """

    faces: list[FaceName]
    """
    The faces to put the picture on.
    """

    pixels: list[ColorValue]
    """
    The picture, row after row.
    """


def apply(world: World, command: SetBackgroundImageCommand) -> None:
    """
    Draws the picture on the background of each face.
    """
    pixels = [parse_color(pixel) for pixel in command["pixels"]]

    for name in command["faces"]:
        draw_bitmap(world.background, FACE_BY_NAME[name], 0, 0, FACE_RESOLUTION, FACE_RESOLUTION, pixels)


set_background_image_block: CommandDefinition = {
    "schema": {
        "faces": FIELD["faces"],
        "pixels": FIELD["image"],
    },
    "apply": apply,
}
"""
The shape of the command, its fields, and how it draws the picture.
"""
