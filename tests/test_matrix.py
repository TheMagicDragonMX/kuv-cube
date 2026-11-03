"""
Tests for the matrix program and its client, with a screen that only records what it is asked to draw.
"""

import asyncio
import os
import tempfile
import unittest

from programs.common.matrix_client import MatrixClient
from programs.common.matrix_protocol import MAIN_PRIORITY, SETUP_PRIORITY, clean_scene, fill, text
from programs.matrix.screen import Screen
from programs.matrix.server import MatrixServer


class RecordingScreen(Screen):
    """
    A screen that remembers every scene it was asked to draw.
    """

    def __init__(self) -> None:
        """
        Starts with nothing drawn.
        """
        super().__init__()

        self.drawn: list[list] = []
        """
        Every scene drawn, oldest first.
        """

    def draw(self, items: list) -> None:
        """
        Records the scene.
        """
        self.drawn.append(items)

    @property
    def current(self) -> list:
        """
        The scene on the screen now.
        """
        return self.drawn[-1] if self.drawn else []


BLUE = [fill(0, 0, 255)]
"""
What main shows in these tests.
"""


class MatrixTest(unittest.IsolatedAsyncioTestCase):
    """
    The highest-priority program with something to show is what the screen shows.
    """

    async def asyncSetUp(self) -> None:
        """
        Starts a server on a temporary socket.
        """
        self.directory = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.directory.name, "run", "matrix.sock")
        self.screen = RecordingScreen()
        self.server = MatrixServer(self.screen, self.path)
        self.clients: list[MatrixClient] = []

        await self.server.start()

    async def asyncTearDown(self) -> None:
        """
        Closes the clients and the server.
        """
        for client in self.clients:
            await client.close()

        await self.server.stop()

        self.directory.cleanup()

    def client(self, name: str, priority: int) -> MatrixClient:
        """
        A started client of the test server.
        """
        client = MatrixClient(name, priority, self.path)

        client.start()
        self.clients.append(client)

        return client

    async def settle(self) -> None:
        """
        Gives the messages time to travel.
        """
        await asyncio.sleep(0.15)

    async def test_screen_starts_blank(self) -> None:
        """
        With nobody connected the screen shows nothing.
        """
        self.assertEqual(self.screen.current, [])

    async def test_a_program_can_draw(self) -> None:
        """
        What main shows reaches the screen.
        """
        self.client("main", MAIN_PRIORITY).show(BLUE)
        await self.settle()

        self.assertEqual(self.screen.current, BLUE)

    async def test_setup_covers_main_and_main_comes_back(self) -> None:
        """
        The PIN is drawn over main, and when setup clears it main shows again, without main resending.
        """
        main = self.client("main", MAIN_PRIORITY)
        setup = self.client("setup", SETUP_PRIORITY)

        main.show(BLUE)
        await self.settle()

        pin = [text("PIN", 4, 24), text("1234", 4, 52)]

        setup.show(pin)
        await self.settle()
        self.assertEqual(self.screen.current, pin)

        setup.clear()
        await self.settle()
        self.assertEqual(self.screen.current, BLUE)

    async def test_main_drawing_while_covered_does_not_replace_the_pin(self) -> None:
        """
        A lower priority program updating its scene does not take over the screen.
        """
        main = self.client("main", MAIN_PRIORITY)
        setup = self.client("setup", SETUP_PRIORITY)
        pin = [text("1234", 4, 52)]

        setup.show(pin)
        await self.settle()

        main.show([fill(255, 0, 0)])
        await self.settle()

        self.assertEqual(self.screen.current, pin)

    async def test_disconnecting_removes_the_scene(self) -> None:
        """
        If setup dies with the PIN on screen, the PIN goes away and main shows again.
        """
        main = self.client("main", MAIN_PRIORITY)
        setup = self.client("setup", SETUP_PRIORITY)

        main.show(BLUE)
        setup.show([text("1234", 4, 52)])
        await self.settle()

        await setup.close()
        await self.settle()

        self.assertEqual(self.screen.current, BLUE)

    async def test_client_that_started_first_connects_later(self) -> None:
        """
        A client started before the server exists draws as soon as the server is up, and again after
        the server restarts.
        """
        await self.server.stop()

        client = self.client("main", MAIN_PRIORITY)

        client.show(BLUE)
        await asyncio.sleep(0.2)

        self.server = MatrixServer(self.screen, self.path)

        await self.server.start()
        await asyncio.sleep(1.4)
        self.assertEqual(self.screen.current, BLUE)

        await self.server.stop()

        self.server = MatrixServer(self.screen, self.path)
        self.screen.drawn.clear()

        await self.server.start()
        await asyncio.sleep(2.4)
        self.assertEqual(self.screen.current, BLUE)

    async def test_bad_messages_are_ignored(self) -> None:
        """
        Garbage, unknown fonts and out-of-range colors change nothing.
        """
        reader, writer = await asyncio.open_unix_connection(self.path)

        for line in (
            b"not json\n",
            b'{"op":"show","items":[{"type":"fill","color":[0,0,999]}]}\n',
            b'{"op":"show","items":[{"type":"text","text":"x","x":0,"y":0,"color":[1,2,3],"font":"../etc"}]}\n',
            b'{"op":"nope"}\n',
        ):
            writer.write(line)

        await writer.drain()
        await self.settle()

        self.assertEqual(self.screen.current, [])

        writer.close()

    def test_clean_scene(self) -> None:
        """
        Well-formed scenes pass; one bad item rejects the whole scene.
        """
        self.assertEqual(clean_scene([fill(1, 2, 3), text("hi", 0, 10)])[1]["font"], "10x20")
        self.assertIsNone(clean_scene([fill(1, 2, 3), {"type": "fill", "color": [1, 2]}]))
        self.assertIsNone(clean_scene("nope"))
