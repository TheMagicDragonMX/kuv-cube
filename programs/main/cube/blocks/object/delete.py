"""
BLOCK: delete (object).

Removes an object for good.
"""

from typing import Literal, TypedDict

from programs.main.cube.blocks.block_definition import CommandDefinition
from programs.main.cube.blocks.fields import FIELD
from programs.main.cube.world.world import World


class DeleteCommand(TypedDict):
    """
    Removes an object.
    """

    op: Literal["delete"]
    """
    Identifies the command.
    """

    target: str
    """
    Name of the object to remove.
    """


def apply(world: World, command: DeleteCommand) -> None:
    """
    Removes the object.
    """
    world.remove(command["target"])


delete_block: CommandDefinition = {
    "schema": {
        "target": FIELD["text"],
    },
    "apply": apply,
}
"""
The shape of the command, its fields, and how it removes the object.
"""
