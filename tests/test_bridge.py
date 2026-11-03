"""
Tests for the bridge between the characteristics and the dispatcher.
"""

import asyncio
import unittest

from programs.setup.bridge import Bridge
from programs.setup.dispatcher import Dispatcher
from programs.setup.framing import MessageDecoder, encode_message


class FakeNetwork:
    """
    A network whose status can be changed by the test.
    """

    def __init__(self) -> None:
        """
        Starts disconnected.
        """
        self.state = "disconnected"
        """
        The state reported by `wifi_status`.
        """

    async def wifi_status(self) -> dict:
        """
        The status for the current state.
        """
        return {"state": self.state, "ssid": None, "ip": None, "signal": None, "saved": []}


class BridgeTest(unittest.IsolatedAsyncioTestCase):
    """
    Bytes written by a page come out as responses and events.
    """

    def setUp(self) -> None:
        """
        A bridge with PIN 1234 that records what it notifies.
        """
        self.network = FakeNetwork()
        self.chunks: list[bytes] = []
        self.decoder = MessageDecoder()
        self.messages: list = []
        self.events: list[str] = []

        def notify(chunk: bytes) -> None:
            """
            Records a chunk and decodes it like the page would.
            """
            self.chunks.append(chunk)
            self.messages += self.decoder.push(chunk)

        dispatcher = Dispatcher(self.network, "Kuv-TEST", "0.0.0", "1234")  # type: ignore[arg-type]
        self.bridge = Bridge(
            dispatcher,
            notify,
            status_interval=0.05,
            poll_interval=0.01,
            chunk_delay=0,
            on_first_connect=lambda: self.events.append("first"),
            on_last_disconnect=lambda: self.events.append("last"),
        )

    async def wait_for(self, count: int) -> None:
        """
        Waits until at least `count` messages were notified.
        """
        for _ in range(200):
            if len(self.messages) >= count:
                return

            await asyncio.sleep(0.01)

        self.fail(f"Only {len(self.messages)} messages arrived")

    def write(self, device: str, message: dict, mtu: int = 0) -> None:
        """
        Writes a request the way a page does, in 180-byte chunks.
        """
        for chunk in encode_message(message, 180):
            self.bridge.receive(device, chunk, mtu)

    async def asyncTearDown(self) -> None:
        """
        Stops the background tasks.
        """
        await self.bridge.close()

    async def test_info_round_trip_in_small_chunks(self) -> None:
        """
        With an unknown MTU the answer is cut into 20-byte chunks and still arrives whole.
        """
        self.write("dev1", {"id": 1, "op": "info"})
        await self.wait_for(1)

        self.assertEqual(self.messages[0]["id"], 1)
        self.assertEqual(self.messages[0]["result"]["name"], "Kuv-TEST")
        self.assertTrue(all(len(chunk) <= 20 for chunk in self.chunks))
        self.assertGreater(len(self.chunks), 1)

    async def test_bigger_mtu_means_bigger_chunks(self) -> None:
        """
        The chunk size follows the MTU minus the 3-byte header.
        """
        self.write("dev1", {"id": 1, "op": "info"}, mtu=185)
        await self.wait_for(1)

        self.assertEqual(len(self.chunks), 1)

    async def test_unlock_is_per_device(self) -> None:
        """
        One page unlocking does not unlock another, and a dropped page loses its unlock.
        """
        self.write("dev1", {"id": 1, "op": "auth", "params": {"pin": "1234"}})
        await self.wait_for(1)

        self.write("dev2", {"id": 2, "op": "wifi.scan"})
        await self.wait_for(2)

        self.assertEqual(self.messages[1]["error"]["code"], "unauthorized")

        self.bridge.disconnected("dev1")
        self.write("dev1", {"id": 3, "op": "status"})
        await self.wait_for(3)

        self.assertEqual(self.messages[2]["error"]["code"], "unauthorized")

    async def test_connect_hooks(self) -> None:
        """
        The first page connecting and the last one leaving are reported once each.
        """
        self.write("dev1", {"id": 1, "op": "info"})
        self.write("dev2", {"id": 2, "op": "info"})

        self.bridge.disconnected("dev1")
        self.bridge.disconnected("dev1")
        self.assertEqual(self.events, ["first"])

        self.bridge.disconnected("dev2")
        self.assertEqual(self.events, ["first", "last"])
        self.assertFalse(self.bridge.connected)

    async def test_status_events_only_after_unlock(self) -> None:
        """
        A locked page gets no status events; after `auth` it gets one, and another when WiFi changes.
        """
        self.write("dev1", {"id": 1, "op": "info"})
        await self.wait_for(1)
        await asyncio.sleep(0.15)

        self.assertEqual(len(self.messages), 1)

        self.write("dev1", {"id": 2, "op": "auth", "params": {"pin": "1234"}})
        await self.wait_for(3)

        events = [message for message in self.messages if "event" in message]
        self.assertEqual(events[0]["event"], "status")
        self.assertEqual(events[0]["data"]["wifi"]["state"], "disconnected")

        self.network.state = "connected"
        await asyncio.sleep(0.1)

        states = [m["data"]["wifi"]["state"] for m in self.messages if "event" in m]
        self.assertIn("connected", states)
