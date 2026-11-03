"""
BLOCK: wait (control).

Pauses the script for some seconds of real time. Only the shape lives here; the pause is run by the interpreter.
"""

from typing import Literal, TypedDict

from programs.main.cube.blocks.block_definition import BlockDefinition
from programs.main.cube.blocks.fields import FIELD


class WaitBlock(TypedDict):
    """
    Pauses the script for some seconds of real time.
    """

    op: Literal["wait"]
    """
    Identifies the block.
    """

    seconds: float
    """
    How long to pause, in seconds.
    """


wait_block: BlockDefinition = {
    "schema": {
        "seconds": FIELD["seconds"],
    },
}
"""
The shape of the block and its fields. What it does is handled by the interpreter.
"""
