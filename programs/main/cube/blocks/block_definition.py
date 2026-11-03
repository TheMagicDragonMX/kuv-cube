"""
LAYER: blocks (definitions).

What every block file in this folder has to provide. A block is described by one dict:

    schema    which fields the block has and what kind of value each takes
    apply     (commands only) what the block does to the world

Control blocks (wait, repeat, forever) have no `apply`: they decide *when* other blocks run, which is the
interpreter's job.
"""

from typing import Any, Callable, TypedDict

from programs.main.cube.blocks.fields import BlockSchema
from programs.main.cube.world.world import World


class BlockDefinition(TypedDict):
    """
    Everything the engine needs to know about a block, except what it does.
    """

    schema: BlockSchema
    """
    Which fields the block has and what kind of value each takes. It must have exactly the fields of the block's
    type, except `op` (the tests check it).
    """


class CommandDefinition(BlockDefinition):
    """
    A block that takes effect immediately.
    """

    apply: Callable[[World, Any], None]
    """
    What the block does to the world when it runs.
    """
