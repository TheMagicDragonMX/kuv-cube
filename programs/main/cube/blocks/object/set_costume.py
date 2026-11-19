"""
BLOCK: setCostume (object).

Changes the look of an object to one of its costumes, by name: it takes the costume's shape and color and keeps its
place. Switching costumes one after another, with waits between them, animates a single object.
"""

from typing import Literal, TypedDict

from programs.main.cube.blocks.block_definition import CommandDefinition
from programs.main.cube.blocks.fields import FIELD
from programs.main.cube.errors import EngineError
from programs.main.cube.world.cube_object import Costume
from programs.main.cube.world.world import World


class SetCostumeCommand(TypedDict):
    """
    Makes `target` wear the costume called `name`.
    """

    op: Literal["setCostume"]
    """
    Identifies the command.
    """

    target: str
    """
    Name of the object.
    """

    name: str
    """
    Name of the costume.
    """


def wear_costume(world: World, target: str, costume: Costume) -> None:
    """
    Makes an object wear a costume.
    """
    world.update(target, {"shape": costume["shape"], "color": costume["color"], "costume": costume["name"]})


def apply(world: World, command: SetCostumeCommand) -> None:
    """
    Puts the costume on the object, or fails when the object has no costume with that name.
    """
    costumes = world.get(command["target"]).get("costumes", ())
    costume = next((candidate for candidate in costumes if candidate["name"] == command["name"]), None)

    if costume is None:
        raise EngineError(f'The object "{command["target"]}" has no costume called "{command["name"]}"')

    wear_costume(world, command["target"], costume)


set_costume_block: CommandDefinition = {
    "schema": {
        "target": FIELD["text"],
        "name": FIELD["text"],
    },
    "apply": apply,
}
"""
The shape of the command, its fields, and how it changes the costume.
"""
