"""
BLOCK: nextBackground (background).

Switches to the background that comes after the one on the cube, in the order of the Background tab; after the last
one comes the first again. In a loop it cycles through them.
"""

from typing import Literal, TypedDict

from programs.main.cube.blocks.background.set_background import show_background
from programs.main.cube.blocks.block_definition import CommandDefinition
from programs.main.cube.errors import EngineError
from programs.main.cube.world.world import World


class NextBackgroundCommand(TypedDict):
    """
    Shows the next background.
    """

    op: Literal["nextBackground"]
    """
    Identifies the command.
    """


def apply(world: World, command: NextBackgroundCommand) -> None:
    """
    Shows the background after the current one (the first, when none of them is on the cube), or fails when there are
    no backgrounds.
    """
    backgrounds = world.backgrounds

    if not backgrounds:
        raise EngineError("There are no backgrounds to switch to. Add some in the Background tab.")

    names = [background["name"] for background in backgrounds]
    current = names.index(world.current_background) if world.current_background in names else -1

    show_background(world, backgrounds[(current + 1) % len(backgrounds)])


next_background_block: CommandDefinition = {
    "schema": {},
    "apply": apply,
}
"""
The shape of the command, and how it moves to the next background.
"""
