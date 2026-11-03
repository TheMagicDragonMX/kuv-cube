"""
Starts the setup service: `sudo python -m programs.setup`.

It advertises the cube over Bluetooth, shows the PIN on the matrix (through the matrix program)
while a page is connected, and
lets that page choose the WiFi network. When the cube ends up online and the page leaves, it hands
over to `main`: it starts the unit named in KUV_SETUP_HANDOFF, which makes systemd stop this one
(see deploy/). Without that setting it simply exits.

Settings come from the environment:
  KUV_SETUP_PIN    use this PIN instead of the generated one; empty turns the PIN off
  KUV_STATE_DIR    where the PIN is remembered (default /var/lib/kuv)
  KUV_SETUP_STAY   set to 1 to keep running even after the cube is online
  KUV_SETUP_HANDOFF  systemd unit to start when setup is done, e.g. kuv-cube.service
"""

import asyncio
import logging
import os
import signal
from pathlib import Path

from programs.common.matrix_client import MatrixClient
from programs.common.matrix_protocol import SETUP_PRIORITY
from programs.setup.bridge import Bridge
from programs.setup.dispatcher import Dispatcher
from programs.setup.display import PinDisplay
from programs.setup.gatt import GattServer
from programs.setup.identity import cube_name, load_pin, software_version
from programs.setup.network import Network
from programs.setup.protocol import WIFI_CONNECTED


logger = logging.getLogger("programs.setup")
"""
Where the service reports what it does.
"""

REPO_DIR = Path(__file__).resolve().parents[2]
"""
The folder this repository is checked out in.
"""

DEFAULT_STATE_DIR = "/var/lib/kuv"
"""
Where the PIN is remembered when KUV_STATE_DIR is not set.
"""


async def run() -> None:
    """
    Runs the setup service until it is done or interrupted.
    """
    name = cube_name()
    pin = load_pin(Path(os.environ.get("KUV_STATE_DIR", DEFAULT_STATE_DIR)), os.environ.get("KUV_SETUP_PIN"))
    stay = os.environ.get("KUV_SETUP_STAY") == "1"
    handoff = os.environ.get("KUV_SETUP_HANDOFF")

    network = Network()
    dispatcher = Dispatcher(network, name, software_version(REPO_DIR), pin)
    matrix = MatrixClient("setup", SETUP_PRIORITY)
    display = PinDisplay(matrix, pin)
    server = GattServer(name)
    finished = asyncio.Event()

    def on_last_disconnect() -> None:
        """
        A page left: clear the PIN, and finish if the cube is now online.
        """
        display.clear()

        if not stay:
            asyncio.get_running_loop().create_task(finish_if_online())

    async def finish_if_online() -> None:
        """
        Hands over to the next unit (or ends) when the cube has a WiFi connection.
        """
        try:
            if (await network.wifi_status())["state"] != WIFI_CONNECTED:
                return

            if handoff is None:
                finished.set()

                return

            logger.info("Online, handing over to %s", handoff)

            process = await asyncio.create_subprocess_exec("systemctl", "start", "--no-block", handoff)

            await process.wait()

        except Exception:
            logger.exception("Could not check the WiFi after the page left")

    bridge = Bridge(
        dispatcher,
        server.service.notify,
        on_first_connect=display.show,
        on_last_disconnect=on_last_disconnect,
    )

    loop = asyncio.get_running_loop()

    for signal_number in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_number, finished.set)

    matrix.start()

    await server.start(bridge)

    logger.info("Advertising as %s (%s)", name, "PIN needed" if pin else "no PIN")

    try:
        await finished.wait()

    finally:
        await bridge.close()
        await server.stop()
        await matrix.close()


def main() -> None:
    """
    Sets up logging and runs the service.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(run())


if __name__ == "__main__":
    main()
