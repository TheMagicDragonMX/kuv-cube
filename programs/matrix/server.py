"""
Decides what the panels show: the scene of the highest-priority program that has one.
"""

import asyncio
import json
import logging
import os
from itertools import count

from programs.common.matrix_protocol import SOCKET_PATH, Item, clean_scene
from programs.matrix.screen import Screen


logger = logging.getLogger(__name__)
"""
Where this module reports problems.
"""

MAX_LINE_SIZE = 64 * 1024
"""
A line longer than this is garbage and ends the connection.
"""

SOCKET_MODE = 0o660
"""
Who may talk to the matrix: root and its group.
"""


class Program:
    """
    A connected program and what it wants shown.
    """

    def __init__(self, order: int) -> None:
        """
        Starts unnamed, at the lowest priority, with nothing to show.
        """
        self.order = order
        """
        When it connected, to break ties between equal priorities (the newer one wins).
        """

        self.name = "unknown"
        """
        Who it says it is, for the log.
        """

        self.priority = 0
        """
        Higher wins.
        """

        self.scene: list[Item] = []
        """
        What it wants shown.
        """


class MatrixServer:
    """
    Listens for programs and keeps the panels showing the right scene.
    """

    def __init__(self, screen: Screen, socket_path: str = SOCKET_PATH) -> None:
        """
        Draws on `screen` and listens on `socket_path`.
        """
        self._screen = screen
        """
        The panels.
        """

        self._socket_path = socket_path
        """
        Where to listen.
        """

        self._programs: set[Program] = set()
        """
        The connected programs.
        """

        self._order = count()
        """
        Numbers the connections.
        """

        self._writers: set[asyncio.StreamWriter] = set()
        """
        The open connections, closed when the server stops.
        """

        self._shown: list[Item] | None = None
        """
        The scene on the panels now, so identical redraws are skipped.
        """

        self._server: asyncio.Server | None = None
        """
        The listening socket.
        """

    async def start(self) -> None:
        """
        Starts listening, and shows a blank scene.
        """
        os.makedirs(os.path.dirname(self._socket_path), exist_ok=True)

        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)

        self._server = await asyncio.start_unix_server(self._serve, path=self._socket_path, limit=MAX_LINE_SIZE)

        os.chmod(self._socket_path, SOCKET_MODE)

        self._render()

    async def stop(self) -> None:
        """
        Stops listening and removes the socket.
        """
        if self._server is not None:
            self._server.close()

        for writer in [*self._writers]:
            writer.close()

        if self._server is not None:
            await self._server.wait_closed()

        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """
        Handles one connected program until it disconnects.
        """
        program = Program(next(self._order))

        self._programs.add(program)
        self._writers.add(writer)

        try:
            while line := await reader.readline():
                self._handle(program, line)

        except (OSError, ValueError, asyncio.LimitOverrunError):
            pass

        finally:
            self._programs.discard(program)
            self._writers.discard(writer)

            writer.close()

            logger.info("%s disconnected", program.name)

            self._render()

    def _handle(self, program: Program, line: bytes) -> None:
        """
        Applies one message from a program; malformed ones are ignored.
        """
        try:
            message = json.loads(line)

        except ValueError:
            return

        if not isinstance(message, dict):
            return

        if message.get("op") == "hello":
            name, priority = message.get("name"), message.get("priority")

            if isinstance(name, str) and isinstance(priority, int) and not isinstance(priority, bool):
                program.name, program.priority = name[:32], priority

                logger.info("%s connected (priority %d)", program.name, program.priority)

        elif message.get("op") == "show":
            scene = clean_scene(message.get("items"))

            if scene is not None:
                program.scene = scene
                program.order = next(self._order)

        self._render()

    def _render(self) -> None:
        """
        Draws the winning scene, unless it is already showing.
        """
        candidates = [program for program in self._programs if program.scene]
        winner = max(candidates, key=lambda program: (program.priority, program.order), default=None)
        scene = winner.scene if winner is not None else []

        if scene == self._shown:
            return

        self._shown = scene

        logger.info("Showing %s", f"{winner.name}'s scene" if winner is not None else "nothing")

        try:
            self._screen.draw(scene)

        except Exception:
            logger.exception("Could not draw")
