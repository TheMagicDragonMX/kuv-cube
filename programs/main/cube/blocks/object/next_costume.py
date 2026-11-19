"""
BLOCK: nextCostume (object).

Changes the look of an object to the costume after the one it wears; after the last one comes the first again. In a
loop with a wait it plays the costumes as an animation. An object with a single look does not change.
"""

from typing import Literal, TypedDict

from programs.main.cube.blocks.block_definition import CommandDefinition
from programs.main.cube.blocks.fields import FIELD
from programs.main.cube.blocks.object.set_costume import wear_costume
from programs.main.cube.world.world import World


class NextCostumeCommand(TypedDict):
    """
    Makes `target` wear its next costume.
    """

    op: Literal["nextCostume"]
    """
    Identifies the command.
    """

    target: str
    """
    Name of the object.
    """


def apply(world: World, command: NextCostumeCommand) -> None:
    """
    Puts the next costume on the object. Fails if there is no such object.
    """
    cube_object = world.get(command["target"])
    costumes = cube_object.get("costumes", ())

    if len(costumes) < 2:
        return

    names = [costume["name"] for costume in costumes]
    current = names.index(cube_object["costume"]) if cube_object.get("costume") in names else -1

    wear_costume(world, command["target"], costumes[(current + 1) % len(costumes)])


next_costume_block: CommandDefinition = {
    "schema": {
        "target": FIELD["text"],
    },
    "apply": apply,
}
"""
The shape of the command, its fields, and how it moves to the next costume.
"""
