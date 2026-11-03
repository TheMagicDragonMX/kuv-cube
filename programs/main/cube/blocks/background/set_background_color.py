"""
BLOCK: setBackgroundColor (background).

Paints some faces one color, replacing any picture they had behind the objects.
"""

from typing import Literal, TypedDict

from programs.main.cube.blocks.block_definition import CommandDefinition
from programs.main.cube.blocks.fields import FIELD
from programs.main.cube.drawing.shapes import fill_rect
from programs.main.cube.program.names import FACE_BY_NAME, parse_color
from programs.main.cube.program.program import ColorValue, FaceName
from programs.main.cube.state.cube_state import FACE_RESOLUTION
from programs.main.cube.world.world import World


class SetBackgroundColorCommand(TypedDict):
    """
    Paints the background of each face in `faces` one color.
    """

    op: Literal["setBackgroundColor"]
    """
    Identifies the command.
    """

    faces: list[FaceName]
    """
    The faces to paint.
    """

    color: ColorValue
    """
    The color.
    """


def apply(world: World, command: SetBackgroundColorCommand) -> None:
    """
    Paints the background of each face.
    """
    color = parse_color(command["color"])

    for name in command["faces"]:
        fill_rect(world.background, FACE_BY_NAME[name], 0, 0, FACE_RESOLUTION, FACE_RESOLUTION, color)


set_background_color_block: CommandDefinition = {
    "schema": {
        "faces": FIELD["faces"],
        "color": FIELD["color"],
    },
    "apply": apply,
}
"""
The shape of the command, its fields, and how it paints the faces.
"""
