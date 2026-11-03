"""
Starts the matrix program: `sudo python -m programs.matrix`.

It opens the LED panels and lets setup and main draw on them. It runs from boot, whether or not the
cube has WiFi, so neither of the other two programs ever has to give the panels up.
"""

import asyncio
import logging
import signal

from programs.common.logs import configure_logging
from programs.matrix.screen import Screen
from programs.matrix.server import MatrixServer


logger = logging.getLogger(__name__)
"""
Where this program reports what it does.
"""


async def run() -> None:
    """
    Opens the panels and serves until interrupted.
    """
    screen = Screen()

    screen.open()

    logger.info("Panels opened")

    server = MatrixServer(screen)
    finished = asyncio.Event()

    for signal_number in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(signal_number, finished.set)

    await server.start()

    logger.info("Listening for programs to draw")

    try:
        await finished.wait()

    finally:
        logger.info("Stopping")

        await server.stop()


def main() -> None:
    """
    Sets up logging and runs the program.
    """
    configure_logging()
    asyncio.run(run())


if __name__ == "__main__":
    main()
