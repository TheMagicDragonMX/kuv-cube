"""
The connection to the server. It keeps the WebSocket open (reconnecting by itself, so the server may be down or the WiFi
may drop), hands every command that arrives to the router and sends back the events it answers with.
"""

import asyncio
import json
import logging

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import WebSocketException

from programs.main.link.commands import CommandRouter, error_event
from programs.main.link.protocol import ERROR_FAILED, Message
from programs.main.link.settings import LinkSettings


logger = logging.getLogger(__name__)
"""
Where this module reports problems.
"""

RECONNECT_MIN = 1.0
"""
Seconds to wait before the first try to reconnect.
"""

RECONNECT_MAX = 30.0
"""
Longest wait between tries; the wait doubles from RECONNECT_MIN up to this.
"""

PING_INTERVAL = 20.0
"""
Seconds between the pings that notice a dead connection (WiFi drops do not close sockets by themselves).
"""


class CubeLink:
    """
    The cube's side of the socket.
    """

    def __init__(self, settings: LinkSettings, router: CommandRouter) -> None:
        """
        Links to the server in `settings`, doing the commands with `router`.
        """
        self._settings = settings
        """
        Where to connect and how to introduce this cube.
        """

        self._router = router
        """
        Does each command that arrives.
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

    async def close(self) -> None:
        """
        Closes the connection and stops reconnecting.
        """
        if self._task is None:
            return

        self._task.cancel()

        try:
            await self._task

        except asyncio.CancelledError:
            pass

        self._task = None

    async def _keep_connected(self) -> None:
        """
        Connects, serves the connection until it drops and connects again, waiting longer after each failure.
        """
        delay = RECONNECT_MIN

        while True:
            try:
                async with connect(
                    self._settings["url"],
                    additional_headers={"Authorization": f"Bearer {self._settings['secret']}"},
                    ping_interval=PING_INTERVAL,
                ) as socket:
                    logger.info("Linked to the server as cube %s", self._settings["cube_id"])

                    delay = RECONNECT_MIN

                    await self._serve(socket)

                logger.info("The server closed the link")

            except (OSError, TimeoutError, WebSocketException) as error:
                logger.warning("Link to the server failed: %s", error)

            await asyncio.sleep(delay)

            delay = min(delay * 2, RECONNECT_MAX)

    async def _serve(self, socket: ClientConnection) -> None:
        """
        Does every command that arrives until the connection ends.
        """
        async for frame in socket:
            message = parse(frame)

            if message is None:
                logger.warning("Ignored a frame that is not a message")

                continue

            await self._answer(socket, message)

    async def _answer(self, socket: ClientConnection, command: Message) -> None:
        """
        Does a command and sends its events, each one marked as the answer to the command.
        """
        try:
            events = await self._router.handle(command)

        except Exception:
            # A bug in a command must not take the link down with it.
            logger.exception("Command %s failed", command["name"])

            events = [error_event(ERROR_FAILED, "The cube failed while doing the command.")]

        for event in events:
            if "id" in command:
                event["replyTo"] = command["id"]

            await socket.send(json.dumps(event))


def parse(frame: str | bytes) -> Message | None:
    """
    The message in a frame, or None when it is not a JSON object with a name.
    """
    try:
        message = json.loads(frame)

    except ValueError:
        return None

    if not isinstance(message, dict) or not isinstance(message.get("name"), str):
        return None

    return message  # type: ignore[return-value]
