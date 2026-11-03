"""
Tests for the request dispatcher.
"""

import asyncio
import unittest
from typing import Any

from programs.setup.dispatcher import Dispatcher, Session
from programs.setup.protocol import ERROR_WIFI_FAILED, ProtocolError


class FakeNetwork:
    """
    A network that answers without touching NetworkManager.
    """

    def __init__(self) -> None:
        """
        Starts disconnected with no saved networks.
        """
        self.connected_to: str | None = None
        """
        The SSID of the last successful connect.
        """

    async def scan(self) -> dict:
        """
        One network.
        """
        return {"networks": [{"ssid": "Casa", "signal": 80, "secure": True}]}

    async def wifi_status(self) -> dict:
        """
        The status for the last connect.
        """
        return {"state": "connected", "ssid": self.connected_to, "ip": None, "signal": None, "saved": []}

    async def connect(self, ssid: str, password: str | None, hidden: bool) -> dict:
        """
        Fails for the wrong password, otherwise remembers the SSID.
        """
        if password == "wrong":
            raise ProtocolError(ERROR_WIFI_FAILED, "Secrets were required")

        self.connected_to = ssid

        return await self.wifi_status()

    async def forget(self, ssid: str) -> None:
        """
        Does nothing.
        """


class DispatcherTest(unittest.IsolatedAsyncioTestCase):
    """
    Requests turn into the right responses.
    """

    def setUp(self) -> None:
        """
        A dispatcher with PIN 1234, a fake network and a recorded reboot.
        """
        self.rebooted = asyncio.Event()
        self.network = FakeNetwork()
        self.session = Session()

        async def reboot() -> None:
            self.rebooted.set()

        self.dispatcher = Dispatcher(
            self.network,  # type: ignore[arg-type]
            "Kuv-TEST",
            "0.0.0",
            "1234",
            reboot=reboot,
        )

    async def ask(self, operation: str, params: Any = None, request_id: int = 1) -> dict:
        """
        Sends a request and returns the response.
        """
        request = {"id": request_id, "op": operation}

        if params is not None:
            request["params"] = params

        response = await self.dispatcher.handle(self.session, request)

        assert response is not None

        return response

    async def test_info_is_open(self) -> None:
        """
        `info` works before `auth` and says a PIN is needed.
        """
        response = await self.ask("info")

        self.assertTrue(response["ok"])
        self.assertTrue(response["result"]["authRequired"])
        self.assertEqual(response["result"]["name"], "Kuv-TEST")

    async def test_locked_until_auth(self) -> None:
        """
        Other operations are refused until the PIN is sent.
        """
        refused = await self.ask("wifi.scan")

        self.assertEqual(refused["error"]["code"], "unauthorized")

        await self.ask("auth", {"pin": "1234"})
        allowed = await self.ask("wifi.scan")

        self.assertTrue(allowed["ok"])

    async def test_wrong_pins_can_be_retried_forever(self) -> None:
        """
        Any number of wrong PINs is refused one by one, and the right one still works afterwards.
        """
        for _ in range(50):
            response = await self.ask("auth", {"pin": "0000"})

            self.assertEqual(response["error"]["code"], "unauthorized")

        self.assertTrue((await self.ask("auth", {"pin": "1234"}))["ok"])

    async def test_connect_validates_params(self) -> None:
        """
        `wifi.connect` needs an ssid.
        """
        await self.ask("auth", {"pin": "1234"})
        response = await self.ask("wifi.connect", {"password": "x"})

        self.assertEqual(response["error"]["code"], "bad_request")

    async def test_connect_failure_is_reported(self) -> None:
        """
        A failed join comes back as `wifi_failed` with the id of the request.
        """
        await self.ask("auth", {"pin": "1234"})
        response = await self.ask("wifi.connect", {"ssid": "Casa", "password": "wrong"}, request_id=9)

        self.assertEqual(response["id"], 9)
        self.assertEqual(response["error"]["code"], "wifi_failed")

    async def test_logs_never_hold_secrets(self) -> None:
        """
        The log says what was asked and how it went, but never the PIN or a WiFi password.
        """
        with self.assertLogs("programs.setup.dispatcher", level="DEBUG") as logged:
            await self.ask("auth", {"pin": "0000"})
            await self.ask("auth", {"pin": "1234"})
            await self.ask("wifi.connect", {"ssid": "Casa", "password": "hunter2hunter2"})
            await self.ask("wifi.connect", {"ssid": "Casa", "password": "wrong"})

        text = "\n".join(logged.output)

        self.assertNotIn("hunter2", text)
        self.assertNotIn("1234", text)
        self.assertNotIn("0000", text)
        self.assertIn("auth refused: unauthorized", text)
        self.assertIn("auth ok", text)
        self.assertIn("wifi.connect refused: wifi_failed", text)

    async def test_unknown_op(self) -> None:
        """
        An operation the cube does not know is answered with `unknown_op`.
        """
        response = await self.ask("nope")

        self.assertEqual(response["error"]["code"], "unknown_op")

    async def test_non_requests_are_ignored(self) -> None:
        """
        A message without a numeric id gets no response.
        """
        self.assertIsNone(await self.dispatcher.handle(self.session, {"op": "info"}))
        self.assertIsNone(await self.dispatcher.handle(self.session, "hello"))

    async def test_reboot_answers_then_reboots(self) -> None:
        """
        The answer comes back first; the reboot happens afterwards.
        """
        await self.ask("auth", {"pin": "1234"})
        response = await self.ask("system.reboot")

        self.assertTrue(response["ok"])
        self.assertFalse(self.rebooted.is_set())

        await asyncio.wait_for(self.rebooted.wait(), 3)
