"""
How a program draws on the LED matrix: it asks the matrix program, which owns the panels.

    client = MatrixClient("main", MAIN_PRIORITY)
    client.start()
    client.show([fill(0, 0, 255)])

The client keeps its scene and reconnects by itself, so the matrix program may start later than
the caller or restart without anything being lost.
"""

import asyncio
import json
import logging

from programs.common.matrix_protocol import SOCKET_PATH, Item


logger = logging.getLogger(__name__)
"""
Where this module reports problems.
"""

RECONNECT_DELAY = 1.0
"""
Seconds to wait before trying to reach the matrix program again.
"""


class MatrixClient:
    """
    One program's connection to the matrix program.
    """

    def __init__(self, name: str, priority: int, socket_path: str = SOCKET_PATH) -> None:
        """
        Draws as `name`; a higher `priority` is shown over a lower one.
        """
        self._name = name
        """
        Who is drawing, for the matrix program's log.
        """

        self._priority = priority
        """
        Which scene wins when several programs draw.
        """

        self._socket_path = socket_path
        """
        Where the matrix program listens.
        """

        self._scene: list[Item] = []
        """
        What this program wants shown, resent after every reconnection.
        """

        self._writer: asyncio.StreamWriter | None = None
        """
        The open connection, or None while disconnected.
        """

        self._task: asyncio.Task | None = None
        """
        Keeps the connection open and reconnects when it drops.
        """

    def start(self) -> None:
        """
        Starts connecting in the background. Call it once, from inside the event loop.
        """
        if self._task is None:
            self._task = asyncio.get_running_loop().create_task(self._keep_connected())

    def show(self, items: list[Item]) -> None:
        """
        Sets what this program wants shown.
        """
        self._scene = items

        self._send({"op": "show", "items": items})

    def clear(self) -> None:
        """
        Shows nothing, so the next program down shows through.
        """
        self.show([])

    async def close(self) -> None:
        """
        Disconnects; the matrix program drops this program's scene.
        """
        if self._task is not None:
            self._task.cancel()

            await asyncio.gather(self._task, return_exceptions=True)

            self._task = None

        if self._writer is not None:
            self._writer.close()

            self._writer = None

    def _send(self, message: dict) -> None:
        """
        Writes one message if connected; otherwise it is resent on reconnection.
        """
        if self._writer is None:
            return

        try:
            self._writer.write(json.dumps(message, separators=(",", ":")).encode() + b"\n")

        except OSError:
            self._writer = None

    async def _keep_connected(self) -> None:
        """
        Connects, introduces itself, resends the scene, and waits for the connection to end.
        """
        while True:
            try:
                reader, writer = await asyncio.open_unix_connection(self._socket_path)

            except OSError:
                await asyncio.sleep(RECONNECT_DELAY)

                continue

            self._writer = writer

            self._send({"op": "hello", "name": self._name, "priority": self._priority})
            self._send({"op": "show", "items": self._scene})

            try:
                await reader.read()

            except OSError:
                pass

            finally:
                self._writer = None

                writer.close()

            await asyncio.sleep(RECONNECT_DELAY)
