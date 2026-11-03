"""
BLOCK: moveTo (object).

Puts an object on a cell of a face, with the given heading or north.
"""

from typing import Literal, NotRequired, TypedDict

from programs.main.cube.blocks.block_definition import CommandDefinition
from programs.main.cube.blocks.fields import FIELD, optional
from programs.main.cube.program.names import FACE_BY_NAME, HEADING_BY_NAME
from programs.main.cube.program.program import FaceName, HeadingName
from programs.main.cube.world.world import World


class MoveToCommand(TypedDict):
    """
    Puts an object on a cell of a face. The heading is reset to the given one, or north.
    """

    op: Literal["moveTo"]
    """
    Identifies the command.
    """

    target: str
    """
    Name of the object to move.
    """

    face: FaceName
    """
    The face to move it to.
    """

    x: int
    """
    Column on that face.
    """

    y: int
    """
    Row on that face.
    """

    heading: NotRequired[HeadingName]
    """
    Where the object faces afterwards. North when omitted.
    """


def apply(world: World, command: MoveToCommand) -> None:
    """
    Puts the object at the new place.
    """
    world.get(command["target"])

    heading = command.get("heading")

    world.update(
        command["target"],
        {
            "pose": world.geometry.place(
                {
                    "face": FACE_BY_NAME[command["face"]],
                    "x": command["x"],
                    "y": command["y"],
                    "heading": HEADING_BY_NAME[heading] if heading else None,
                }
            ),
        },
    )


move_to_block: CommandDefinition = {
    "schema": {
        "target": FIELD["text"],
        "face": FIELD["face"],
        "x": FIELD["integer"],
        "y": FIELD["integer"],
        "heading": optional(FIELD["heading"]),
    },
    "apply": apply,
}
"""
The shape of the command, its fields, and how it moves the object.
"""
