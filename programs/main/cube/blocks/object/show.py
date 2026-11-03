"""
BLOCK: show (object).

Makes a hidden object visible. Nothing is touched if it already is.
"""

from typing import Literal, TypedDict

from programs.main.cube.blocks.block_definition import CommandDefinition
from programs.main.cube.blocks.fields import FIELD
from programs.main.cube.world.world import World


class ShowCommand(TypedDict):
    """
    Makes an object visible.
    """

    op: Literal["show"]
    """
    Identifies the command.
    """

    target: str
    """
    Name of the object to show.
    """


def apply(world: World, command: ShowCommand) -> None:
    """
    Shows the object.
    """
    if not world.get(command["target"])["visible"]:
        world.update(command["target"], {"visible": True})


show_block: CommandDefinition = {
    "schema": {
        "target": FIELD["text"],
    },
    "apply": apply,
}
"""
The shape of the command, its fields, and how it shows the object.
"""
