"""
BLOCK: setColor (object).

Changes the color of an object. Nothing is touched if it already has that color.
"""

from typing import Literal, TypedDict

from programs.main.cube.blocks.block_definition import CommandDefinition
from programs.main.cube.blocks.fields import FIELD
from programs.main.cube.program.names import parse_color
from programs.main.cube.program.program import ColorValue
from programs.main.cube.world.world import World


class SetColorCommand(TypedDict):
    """
    Changes the color of an object.
    """

    op: Literal["setColor"]
    """
    Identifies the command.
    """

    target: str
    """
    Name of the object to recolor.
    """

    color: ColorValue
    """
    The new color.
    """


def apply(world: World, command: SetColorCommand) -> None:
    """
    Recolors the object.
    """
    color = parse_color(command["color"])

    if world.get(command["target"])["color"] != color:
        world.update(command["target"], {"color": color})


set_color_block: CommandDefinition = {
    "schema": {
        "target": FIELD["text"],
        "color": FIELD["color"],
    },
    "apply": apply,
}
"""
The shape of the command, its fields, and how it recolors the object.
"""
