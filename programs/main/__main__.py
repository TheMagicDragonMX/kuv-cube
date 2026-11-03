"""
Runs the cube once it is online: `python -m programs.main`.

For now it turns all the LED panels blue, through the matrix program.
"""

import asyncio
import signal

from programs.common.matrix_client import MatrixClient
from programs.common.matrix_protocol import MAIN_PRIORITY, fill


async def run() -> None:
    """
    Paints the panels blue and waits until interrupted.
    """
    matrix = MatrixClient("main", MAIN_PRIORITY)
    finished = asyncio.Event()

    for signal_number in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(signal_number, finished.set)

    matrix.start()
    matrix.show([fill(0, 0, 255)])

    try:
        await finished.wait()

    finally:
        await matrix.close()


def main() -> None:
    """
    Runs the program.
    """
    asyncio.run(run())


if __name__ == "__main__":
    main()
