"""
Runs the cube once it is online: `python -m programs.main`.

For now it turns all the LED panels blue, through the matrix program.
"""

import asyncio
import logging
import signal

from programs.common.logs import configure_logging
from programs.common.matrix_client import MatrixClient
from programs.common.matrix_protocol import MAIN_PRIORITY, fill


logger = logging.getLogger(__name__)
"""
Where this program reports what it does.
"""


async def run() -> None:
    """
    Paints the panels blue and waits until interrupted.
    """
    matrix = MatrixClient("main", MAIN_PRIORITY)
    finished = asyncio.Event()

    for signal_number in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(signal_number, finished.set)

    logger.info("Started, painting the panels blue")

    matrix.start()
    matrix.show([fill(0, 0, 255)])

    try:
        await finished.wait()

    finally:
        logger.info("Stopping")

        await matrix.close()


def main() -> None:
    """
    Runs the program.
    """
    configure_logging()
    asyncio.run(run())


if __name__ == "__main__":
    main()
