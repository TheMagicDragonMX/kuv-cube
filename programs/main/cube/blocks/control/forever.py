"""
BLOCK: forever (control).

Runs its body again and again until the program is stopped. Only the shape lives here; the loop itself is run by the
interpreter, which makes sure it pauses once per iteration.
"""

from typing import TYPE_CHECKING, Literal, TypedDict

from programs.main.cube.blocks.block_definition import BlockDefinition
from programs.main.cube.blocks.fields import FIELD

if TYPE_CHECKING:
    from programs.main.cube.blocks import Block


class ForeverBlock(TypedDict):
    """
    Runs its body again and again until the program is stopped.
    """

    op: Literal["forever"]
    """
    Identifies the block.
    """

    body: "list[Block]"
    """
    The blocks to repeat.
    """


forever_block: BlockDefinition = {
    "schema": {
        "body": FIELD["blocks"],
    },
}
"""
The shape of the block and its fields. What it does is handled by the interpreter.
"""
