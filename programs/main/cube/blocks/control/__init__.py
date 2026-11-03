"""
CATEGORY: control.

Blocks that decide when and how many times other blocks run. They do not change the world, so they have no `apply`:
the interpreter (`runtime/interpreter.py`) gives them their meaning.

To add a block to this category: write its file in this folder, add it to the union and to the table below, and teach
the interpreter what it means.
"""

from typing import TypeAlias

from programs.main.cube.blocks.block_definition import BlockDefinition
from programs.main.cube.blocks.control.forever import ForeverBlock, forever_block
from programs.main.cube.blocks.control.repeat import RepeatBlock, repeat_block
from programs.main.cube.blocks.control.wait import WaitBlock, wait_block


ControlBlock: TypeAlias = WaitBlock | RepeatBlock | ForeverBlock
"""
A block that controls the flow of a script.
"""

CONTROL_BLOCKS: dict[str, BlockDefinition] = {
    "wait": wait_block,
    "repeat": repeat_block,
    "forever": forever_block,
}
"""
The definition of each control block, by `op`.
"""
