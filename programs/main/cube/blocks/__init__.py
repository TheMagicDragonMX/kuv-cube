"""
LAYER: blocks (registry).

Every block a user can put in a script, organized by category, one file per block:

    object/       change the objects of the world       create, move, moveTo, setColor, ...
    background/   change what is behind the objects     setBackgroundImage, setBackgroundColor
    control/      decide when other blocks run          wait, repeat, forever

This file joins the categories. The rest of the engine asks it for the types (`Block`, `Command`) and for the
definition of a block by its `op`; it never imports a single block.
"""

from typing import TypeAlias

from programs.main.cube.blocks.background import BACKGROUND_BLOCKS, BackgroundCommand
from programs.main.cube.blocks.block_definition import BlockDefinition, CommandDefinition
from programs.main.cube.blocks.control import CONTROL_BLOCKS, ControlBlock
from programs.main.cube.blocks.object import OBJECT_BLOCKS, ObjectCommand
from programs.main.cube.blocks.object.create import CreateCommand


__all__ = [
    "BlockDefinition",
    "CommandDefinition",
    "BackgroundCommand",
    "ControlBlock",
    "ObjectCommand",
    "CreateCommand",
    "Command",
    "Block",
    "COMMAND_BLOCKS",
    "get_block_definition",
]
"""
What other folders may import from here.
"""

Command: TypeAlias = ObjectCommand | BackgroundCommand
"""
A block that takes effect immediately. The commands layer knows how to apply these.
"""

Block: TypeAlias = Command | ControlBlock
"""
Any block a script can contain.
"""

COMMAND_BLOCKS: dict[str, CommandDefinition] = {
    **OBJECT_BLOCKS,
    **BACKGROUND_BLOCKS,
}
"""
The definition of each command, by `op`.
"""

DEFINITIONS: dict[str, BlockDefinition] = {
    **COMMAND_BLOCKS,
    **CONTROL_BLOCKS,
}
"""
The definition of every block, by its `op`.
"""


def get_block_definition(op: str) -> BlockDefinition | None:
    """
    The definition of the block with this `op`, or None if there is no such block.
    """
    return DEFINITIONS.get(op)
