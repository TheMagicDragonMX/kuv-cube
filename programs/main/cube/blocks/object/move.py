"""
BLOCK: move (object).

Moves an object relative to its heading. If the move changes nothing (zero cells, or the object is already against
the floor) the world is left untouched, so nothing is redrawn.
"""

from typing import Literal, NotRequired, TypedDict

from programs.main.cube.blocks.block_definition import CommandDefinition
from programs.main.cube.blocks.fields import FIELD, optional
from programs.main.cube.geometry.geometry import Step
from programs.main.cube.world.world import World


class MoveCommand(TypedDict):
    """
    Moves an object some cells in a direction relative to its own heading. Defaults to one cell.
    """

    op: Literal["move"]
    """
    Identifies the command.
    """

    target: str
    """
    Name of the object to move.
    """

    step: Step
    """
    The direction to move in, relative to the object's heading.
    """

    count: NotRequired[int]
    """
    How many cells to move. Defaults to one.
    """


def apply(world: World, command: MoveCommand) -> None:
    """
    Moves the object, doing nothing when the move changes nothing.
    """
    cube_object = world.get(command["target"])
    pose = world.geometry.move(cube_object["pose"], command["step"], command.get("count", 1))

    if pose is not cube_object["pose"]:
        world.update(command["target"], {"pose": pose})


move_block: CommandDefinition = {
    "schema": {
        "target": FIELD["text"],
        "step": FIELD["step"],
        "count": optional(FIELD["count"]),
    },
    "apply": apply,
}
"""
The shape of the command, its fields, and how it moves the object.
"""
