"""
Tests for the request dispatcher.
"""

import asyncio
import unittest
from typing import Any

from setup.dispatcher import MAX_PIN_ATTEMPTS, Dispatcher, Session
from setup.protocol import ERROR_WIFI_FAILED, ProtocolError


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
        A dispatcher with PIN 1234, a fake network, a fake clock and a recorded reboot.
        """
        self.now = 0.0
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
            clock=lambda: self.now,
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

    async def test_wrong_pin_then_lockout(self) -> None:
        """
        Too many wrong PINs lock `auth`, even for the right one, until the lockout ends.
        """
        for _ in range(MAX_PIN_ATTEMPTS - 1):
            response = await self.ask("auth", {"pin": "0000"})

            self.assertEqual(response["error"]["code"], "unauthorized")

        locking = await self.ask("auth", {"pin": "0000"})
        self.assertEqual(locking["error"]["code"], "locked")

        still_locked = await self.ask("auth", {"pin": "1234"})
        self.assertEqual(still_locked["error"]["code"], "locked")

        self.now += 61
        unlocked = await self.ask("auth", {"pin": "1234"})
        self.assertTrue(unlocked["ok"])

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
