"""
BLOCK: pointUp (object).

Resets the heading of an object so its "up" is the up of the screen again. Nothing is touched if it already points
up.
"""

from typing import Literal, TypedDict

from programs.main.cube.blocks.block_definition import CommandDefinition
from programs.main.cube.blocks.fields import FIELD
from programs.main.cube.world.world import World


class PointUpCommand(TypedDict):
    """
    Resets the heading of an object so its "up" is the up of the screen again.
    """

    op: Literal["pointUp"]
    """
    Identifies the command.
    """

    target: str
    """
    Name of the object to turn.
    """


def apply(world: World, command: PointUpCommand) -> None:
    """
    Turns the object to face up.
    """
    cube_object = world.get(command["target"])
    pose = world.geometry.point_up(cube_object["pose"])

    if pose["heading"] != cube_object["pose"]["heading"]:
        world.update(command["target"], {"pose": pose})


point_up_block: CommandDefinition = {
    "schema": {
        "target": FIELD["text"],
    },
    "apply": apply,
}
"""
The shape of the command, its fields, and how it turns the object.
"""
