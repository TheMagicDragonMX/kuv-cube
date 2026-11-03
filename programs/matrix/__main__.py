"""
Starts the matrix program: `sudo python -m programs.matrix`.

It opens the LED panels and lets setup and main draw on them. It runs from boot, whether or not the
cube has WiFi, so neither of the other two programs ever has to give the panels up.
"""

import asyncio
import logging
import signal

from programs.matrix.screen import Screen
from programs.matrix.server import MatrixServer


async def run() -> None:
    """
    Opens the panels and serves until interrupted.
    """
    screen = Screen()

    screen.open()

    server = MatrixServer(screen)
    finished = asyncio.Event()

    for signal_number in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(signal_number, finished.set)

    await server.start()

    try:
        await finished.wait()

    finally:
        await server.stop()


def main() -> None:
    """
    Sets up logging and runs the program.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(run())


if __name__ == "__main__":
    main()
