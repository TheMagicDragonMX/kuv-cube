"""
BLOCK: setBackground (background).

Switches to one of the backgrounds the user made in the Background tab, by its name: the faces it has a picture for
show it, and the others keep what they show, so backgrounds on different faces combine. The backgrounds are in the
world (the environment puts them there), so the block only carries a name.
"""

from typing import Literal, TypedDict

from programs.main.cube.blocks.block_definition import CommandDefinition
from programs.main.cube.blocks.fields import FIELD
from programs.main.cube.drawing.bitmap import draw_bitmap
from programs.main.cube.errors import EngineError
from programs.main.cube.program.names import FACE_BY_NAME
from programs.main.cube.state.cube_state import FACE_RESOLUTION
from programs.main.cube.world.world import NamedBackground, World


class SetBackgroundCommand(TypedDict):
    """
    Shows the background called `name`.
    """

    op: Literal["setBackground"]
    """
    Identifies the command.
    """

    name: str
    """
    The name of the background.
    """


def show_background(world: World, background: NamedBackground) -> None:
    """
    Paints the pictures of a background on the faces it has them for, and remembers it is the last one shown.
    """
    for name, face in FACE_BY_NAME.items():
        pixels = background["images"].get(name)

        if pixels:
            draw_bitmap(world.background, face, 0, 0, FACE_RESOLUTION, FACE_RESOLUTION, pixels)

    world.current_background = background["name"]


def apply(world: World, command: SetBackgroundCommand) -> None:
    """
    Shows the background, or fails when there is none with that name.
    """
    background = next((candidate for candidate in world.backgrounds if candidate["name"] == command["name"]), None)

    if background is None:
        raise EngineError(f'There is no background called "{command["name"]}"')

    show_background(world, background)


set_background_block: CommandDefinition = {
    "schema": {
        "name": FIELD["text"],
    },
    "apply": apply,
}
"""
The shape of the command, its fields, and how it switches the background.
"""
