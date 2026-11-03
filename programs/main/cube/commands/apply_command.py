"""
LAYER: commands (dispatch).

The single entry point for "do this block now". It looks up the definition of the command in the blocks registry and
runs its `apply`. It contains no logic of its own, and it does not change when a block is added: what each block does
lives in its own file in `blocks/`.

    interpreter --apply_command--> blocks/<category>/<block>.py --> World

Control blocks (wait, repeat, forever) are not commands: they decide *when* other blocks run, which is the
interpreter's job.
"""

from typing import Any

from programs.main.cube.blocks import COMMAND_BLOCKS
from programs.main.cube.errors import EngineError
from programs.main.cube.world.world import World


def is_command(block: dict[str, Any]) -> bool:
    """
    Tells whether a block is a command (takes effect at once) and not a control block.
    """
    return block["op"] in COMMAND_BLOCKS


def apply_command(world: World, command: Any) -> None:
    """
    Performs one command on the world.
    """
    definition = COMMAND_BLOCKS.get(command["op"])

    if definition is None:
        raise EngineError(f"Unknown command {command!r}")

    definition["apply"](world, command)
