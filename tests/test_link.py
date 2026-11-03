"""
Tests for the live link: the commands, and the connection against a fake server.
"""

import asyncio
import json
import os
import unittest
from unittest import mock

from websockets.asyncio.server import serve

from programs.main.link import CubeLink, default_commands, load_settings
from programs.main.link.commands import CommandRouter


class CommandRouterTest(unittest.IsolatedAsyncioTestCase):
    """
    What the router answers.
    """

    async def test_message_gets_a_reply(self) -> None:
        """
        A text is answered with a reply that repeats it.
        """
        events = await default_commands().handle({"name": "message", "payload": {"text": " hola "}})

        self.assertEqual(events[0]["name"], "reply")
        self.assertIn("hola", events[0]["payload"]["text"])

    async def test_message_without_text_is_an_error(self) -> None:
        """
        A message with no text is answered with an invalid_payload error.
        """
        events = await default_commands().handle({"name": "message", "payload": {}})

        self.assertEqual(events[0]["payload"]["code"], "invalid_payload")

    async def test_unknown_command_is_an_error(self) -> None:
        """
        A command nobody registered is answered with an unknown_command error.
        """
        events = await CommandRouter().handle({"name": "dance"})

        self.assertEqual(events[0]["payload"]["code"], "unknown_command")


class SettingsTest(unittest.TestCase):
    """
    How the environment becomes settings.
    """

    def test_link_is_off_without_server(self) -> None:
        """
        Without a server address there are no settings.
        """
        with mock.patch.dict(os.environ, {"KUV_CUBE_SECRET": "s", "KUV_CUBE_ID": "c"}, clear=True):
            self.assertIsNone(load_settings())

    def test_url_has_the_cube_id(self) -> None:
        """
        The address points at the cube endpoint with the id in the query.
        """
        env = {"KUV_SERVER_URL": "ws://host:5038/", "KUV_CUBE_SECRET": "s", "KUV_CUBE_ID": "a b"}

        with mock.patch.dict(os.environ, env, clear=True):
            settings = load_settings()

        self.assertEqual(settings["url"], "ws://host:5038/ws/cube?cubeId=a%20b")


class CubeLinkTest(unittest.IsolatedAsyncioTestCase):
    """
    The link against a fake server.
    """

    async def test_answers_a_command_marked_as_reply(self) -> None:
        """
        The cube authenticates, receives a command and answers with an event that points at the command.
        """
        answers: asyncio.Future = asyncio.get_running_loop().create_future()
        headers: dict = {}

        async def server(socket) -> None:
            headers["Authorization"] = socket.request.headers.get("Authorization")

            await socket.send(json.dumps({"name": "message", "id": "42", "payload": {"text": "hi"}}))
            answers.set_result(json.loads(await socket.recv()))

        async with serve(server, "127.0.0.1", 0) as running:
            port = running.sockets[0].getsockname()[1]
            link = CubeLink({"url": f"ws://127.0.0.1:{port}/ws/cube?cubeId=c", "secret": "s", "cube_id": "c"}, default_commands())

            link.start()

            try:
                answer = await asyncio.wait_for(answers, 5)

            finally:
                await link.close()

        self.assertEqual(headers["Authorization"], "Bearer s")
        self.assertEqual(answer["name"], "reply")
        self.assertEqual(answer["replyTo"], "42")


if __name__ == "__main__":
    unittest.main()
