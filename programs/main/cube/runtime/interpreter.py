"""
LAYER: runtime (interpreter).

Runs the blocks of one script, in order. It is a *generator*: a function that can pause in the middle and be resumed
later from exactly the same place. That is how many scripts can share one thread and still look like they run at the
same time.

    run = run_blocks(blocks, world)
    next(run)   # runs blocks until the first pause, then stops there
    next(run)   # continues from that pause

A script pauses (yields) in two situations:

    wait   the script asked to sleep for some time
    tick   a loop finished an iteration; it gives the others a turn before the next one

The second one is the important safety rule: **a loop pauses at least once per iteration**. Without it
`forever { move }` would never give control back and would freeze the cube. If the iteration already paused by
itself (it contained a `wait`) no extra pause is added, so `forever { move; wait 0.1 }` runs every 0.1 seconds and
not a tick later.

The interpreter only handles control flow. What a command *does* lives in the commands layer, and *when* a paused
script continues is decided by the scheduler.
"""

from typing import Any, Generator, Literal, TypeAlias, TypedDict

from programs.main.cube.commands.apply_command import apply_command, is_command
from programs.main.cube.world.world import World


class TickPause(TypedDict):
    """
    The script resumes on the next tick.
    """

    kind: Literal["tick"]
    """
    Always "tick".
    """


class WaitPause(TypedDict):
    """
    The script resumes after some time.
    """

    kind: Literal["wait"]
    """
    Always "wait".
    """

    milliseconds: float
    """
    How long to wait.
    """


Pause: TypeAlias = TickPause | WaitPause
"""
Why a script paused.
"""

Run: TypeAlias = Generator[Pause, None, bool]
"""
A script being run. Each `next()` runs until the next pause. The generator finishes when the script has no blocks
left.
"""

NEXT_TICK: TickPause = {"kind": "tick"}
"""
The pause a loop uses when its iteration did not pause by itself.
"""


def run_blocks(blocks: list[Any], world: World) -> Run:
    """
    Runs a list of blocks. Returns whether it paused at least once, which loops use to decide if they still have to
    pause at the end of an iteration.
    """
    paused = False

    for block in blocks:
        if is_command(block):
            apply_command(world, block)

            continue

        if block["op"] == "wait":
            yield {"kind": "wait", "milliseconds": block["seconds"] * 1000}

            paused = True

        elif block["op"] == "repeat":
            for _ in range(block["times"]):
                if not (yield from run_blocks(block["body"], world)):
                    yield NEXT_TICK

                paused = True

        elif block["op"] == "forever":
            while True:
                if not (yield from run_blocks(block["body"], world)):
                    yield NEXT_TICK

    return paused
