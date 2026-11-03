"""
BLOCK: hide (object).

Hides an object without removing it: it still exists and keeps moving, but is not drawn. Nothing is touched if it
already is hidden.
"""

from typing import Literal, TypedDict

from programs.main.cube.blocks.block_definition import CommandDefinition
from programs.main.cube.blocks.fields import FIELD
from programs.main.cube.world.world import World


class HideCommand(TypedDict):
    """
    Hides an object without removing it.
    """

    op: Literal["hide"]
    """
    Identifies the command.
    """

    target: str
    """
    Name of the object to hide.
    """


def apply(world: World, command: HideCommand) -> None:
    """
    Hides the object.
    """
    if world.get(command["target"])["visible"]:
        world.update(command["target"], {"visible": False})


hide_block: CommandDefinition = {
    "schema": {
        "target": FIELD["text"],
    },
    "apply": apply,
}
"""
The shape of the command, its fields, and how it hides the object.
"""
