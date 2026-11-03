"""
Runs the cube once it is online: `python -m programs.main [program.json | -]`.

With a program (a JSON file, or `-` for the standard input) it runs it and shows it on the LED panels through the
matrix program, until interrupted. Without one it turns all the LED panels blue.
"""

import asyncio
import json
import logging
import signal
import sys
from typing import Any

from programs.common.matrix_client import MatrixClient
from programs.common.matrix_protocol import MAIN_PRIORITY, fill
from programs.main.cube import CubePlayer, EngineError, ProgramError, ScriptError, scene_of, validate_program


logger = logging.getLogger(__name__)
"""
Where this module reports problems.
"""


def load_program(source: str) -> Any:
    """
    Reads and checks a program from a JSON file, or from the standard input when the source is `-`. Raises a
    ProgramError, with the reason, if it cannot be read or is not a program.
    """
    try:
        if source == "-":
            program = json.load(sys.stdin)

        else:
            with open(source, encoding="utf-8") as file:
                program = json.load(file)

    except (OSError, ValueError) as error:
        raise ProgramError(f"Could not read the program from {source}: {error}") from error

    return validate_program(program)


def report(error: ScriptError) -> None:
    """
    Logs a script that had to stop.
    """
    logger.error("Script %d stopped: %s", error["script"], error["message"])


async def run(program: Any) -> None:
    """
    Shows the program on the panels, or paints them blue when there is none, and waits until interrupted.
    """
    matrix = MatrixClient("main", MAIN_PRIORITY)
    finished = asyncio.Event()

    for signal_number in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(signal_number, finished.set)

    matrix.start()

    player = CubePlayer({"on_frame": lambda state: matrix.show(scene_of(state)), "on_error": report})

    try:
        if program is None:
            matrix.show([fill(0, 0, 255)])

        else:
            player.play(program)

        await finished.wait()

    finally:
        player.dispose()

        await matrix.close()


def main() -> None:
    """
    Runs the program.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        program = load_program(sys.argv[1]) if len(sys.argv) > 1 else None

    except ProgramError as error:
        sys.exit(f"Invalid program: {error}")

    try:
        asyncio.run(run(program))

    except (EngineError, ValueError) as error:
        sys.exit(f"The program could not start: {error}")


if __name__ == "__main__":
    main()
