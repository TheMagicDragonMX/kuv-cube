"""
Tests for the NetworkManager wrapper, against a scripted nmcli that answers like the cube's.
"""

import unittest
from unittest import mock

from setup.network import Network, split_terse
from setup.protocol import ERROR_WIFI_FAILED, ProtocolError


class FakeNmcli:
    """
    Answers nmcli commands from a small in-memory model and records the ones that change things.
    """

    def __init__(self) -> None:
        """
        The cube starts connected to "Home", stored as the profile "netplan-wlan0-Home".
        """
        self.profiles = {"netplan-wlan0-Home": "Home"}
        """
        Saved WiFi profiles, name to SSID.
        """

        self.active = "Home"
        """
        The SSID in use, or None.
        """

        self.password_ok = {"Cafe": "secret"}
        """
        The password each unsaved network accepts.
        """

        self.commands: list[tuple[str, ...]] = []
        """
        Every command that changes something, in order.
        """

    async def __call__(self, *args: str, timeout: float = 0) -> str:
        """
        Runs one fake nmcli command.
        """
        args = tuple(arg for arg in args if arg not in ("--wait",) and not arg.isdigit())

        if args[:4] == ("-t", "-f", "DEVICE,TYPE", "device"):
            return "eth0:ethernet\nwlan0:wifi\n"

        if args[:4] == ("-t", "-f", "NAME,TYPE", "connection"):
            return "".join(f"{name}:802-11-wireless\n" for name in self.profiles) + "lo:loopback\n"

        if args[:3] == ("-g", "802-11-wireless.ssid", "connection"):
            return self.profiles[args[4]] + "\n"

        if args[:3] == ("-t", "-f", "GENERAL.STATE,IP4.ADDRESS"):
            if self.active is None:
                return "GENERAL.STATE:30 (disconnected)\n"

            return "GENERAL.STATE:100 (connected)\nIP4.ADDRESS[1]:192.168.0.9/24\n"

        if args[:3] == ("-t", "-f", "IN-USE,SSID,SIGNAL"):
            return f"*:{self.active}:61\n :Other:30\n"

        self.commands.append(args)

        if args[:2] == ("connection", "up"):
            self.active = self.profiles[args[2]]

        elif args[:2] == ("connection", "delete"):
            del self.profiles[args[2]]

        elif args[:3] == ("device", "wifi", "connect"):
            ssid = args[3]
            password = args[5] if args[4:5] == ("password",) else None

            if self.password_ok.get(ssid) != password:
                raise ProtocolError(ERROR_WIFI_FAILED, "Secrets were required")

            self.profiles[ssid] = ssid
            self.active = ssid

        return ""


class NetworkTest(unittest.IsolatedAsyncioTestCase):
    """
    The wrapper reports SSIDs (not profile names) and survives failed joins.
    """

    def setUp(self) -> None:
        """
        Patches nmcli with the fake.
        """
        self.nmcli = FakeNmcli()
        patcher = mock.patch("setup.network.run_nmcli", self.nmcli)

        patcher.start()
        self.addCleanup(patcher.stop)

        self.network = Network()

    def test_split_terse(self) -> None:
        """
        Escaped colons stay inside the field.
        """
        self.assertEqual(split_terse(r"My\:Net:77:WPA2"), ["My:Net", "77", "WPA2"])

    async def test_status_reports_ssid_not_profile_name(self) -> None:
        """
        A profile called "netplan-wlan0-Home" shows up as "Home".
        """
        status = await self.network.wifi_status()

        self.assertEqual(status["state"], "connected")
        self.assertEqual(status["ssid"], "Home")
        self.assertEqual(status["ip"], "192.168.0.9")
        self.assertEqual(status["signal"], 61)
        self.assertEqual(status["saved"], ["Home"])

    async def test_connect_new_network(self) -> None:
        """
        Joining an unsaved network with its password saves and uses it.
        """
        status = await self.network.connect("Cafe", "secret")

        self.assertEqual(status["ssid"], "Cafe")
        self.assertEqual(sorted(status["saved"]), ["Cafe", "Home"])

    async def test_failed_connect_keeps_the_old_network(self) -> None:
        """
        A wrong password leaves nothing behind and puts the cube back on "Home".
        """
        with self.assertRaises(ProtocolError):
            await self.network.connect("Cafe", "wrong")

        self.assertEqual(list(self.nmcli.profiles.values()), ["Home"])
        self.assertEqual((await self.network.wifi_status())["ssid"], "Home")

    async def test_connect_saved_network_uses_its_profile(self) -> None:
        """
        Joining a saved network without a password brings its profile up by name.
        """
        self.nmcli.active = None
        await self.network.connect("Home")

        self.assertIn(("connection", "up", "netplan-wlan0-Home"), self.nmcli.commands)

    async def test_forget_by_ssid(self) -> None:
        """
        Forgetting "Home" deletes the profile whose SSID is "Home".
        """
        await self.network.forget("Home")

        self.assertEqual(self.nmcli.profiles, {})

    async def test_forget_unknown_network(self) -> None:
        """
        Forgetting a network that is not saved is a bad request.
        """
        with self.assertRaises(ProtocolError) as raised:
            await self.network.forget("Nowhere")

        self.assertEqual(raised.exception.code, "bad_request")
