"""
BLOCK: repeat (control).

Runs its body a fixed number of times. Only the shape lives here; the loop itself is run by the interpreter.
"""

from typing import TYPE_CHECKING, Literal, TypedDict

from programs.main.cube.blocks.block_definition import BlockDefinition
from programs.main.cube.blocks.fields import FIELD

if TYPE_CHECKING:
    from programs.main.cube.blocks import Block


class RepeatBlock(TypedDict):
    """
    Runs its body a fixed number of times.
    """

    op: Literal["repeat"]
    """
    Identifies the block.
    """

    times: int
    """
    How many times to run the body.
    """

    body: "list[Block]"
    """
    The blocks to repeat.
    """


repeat_block: BlockDefinition = {
    "schema": {
        "times": FIELD["count"],
        "body": FIELD["blocks"],
    },
}
"""
The shape of the block and its fields. What it does is handled by the interpreter.
"""
