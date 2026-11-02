"""
WiFi control through NetworkManager (nmcli), shaped like the setup protocol's answers.
"""

import asyncio
import re
from pathlib import Path

from setup.protocol import (
    ERROR_BAD_REQUEST,
    ERROR_BUSY,
    ERROR_INTERNAL,
    ERROR_WIFI_FAILED,
    WIFI_CONNECTED,
    WIFI_CONNECTING,
    WIFI_DISCONNECTED,
    WIFI_FAILED,
    ProtocolError,
    SystemStatus,
    WifiNetwork,
    WifiStatus,
)


CONNECT_TIMEOUT = 45
"""
Seconds a connection attempt may take before it counts as failed.
"""

SCAN_TIMEOUT = 20
"""
Seconds a scan may take.
"""

COMMAND_TIMEOUT = 10
"""
Seconds any other nmcli command may take.
"""

WIFI_CONNECTION_TYPE = "802-11-wireless"
"""
The type NetworkManager gives to saved WiFi connections.
"""

TEMPERATURE_PATH = Path("/sys/class/thermal/thermal_zone0/temp")
"""
Where the kernel exposes the CPU temperature, in millidegrees.
"""

UPTIME_PATH = Path("/proc/uptime")
"""
Where the kernel exposes the seconds since boot.
"""


def split_terse(line: str) -> list[str]:
    """
    Splits a line of `nmcli -t` output on its unescaped colons.
    """
    fields = re.split(r"(?<!\\):", line)

    return [field.replace("\\:", ":").replace("\\\\", "\\") for field in fields]


def pad_fields(fields: list[str], count: int) -> list[str]:
    """
    The first `count` fields, filling the missing ones with empty strings.
    """
    return (fields + [""] * count)[:count]


async def run_nmcli(*args: str, timeout: float = COMMAND_TIMEOUT) -> str:
    """
    Runs nmcli and returns its stdout, or raises ProtocolError(wifi_failed) with its message.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "nmcli", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    except FileNotFoundError:
        raise ProtocolError(ERROR_INTERNAL, "nmcli is not installed")

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)

    except asyncio.TimeoutError:
        process.kill()
        await process.wait()

        raise ProtocolError(ERROR_WIFI_FAILED, "Timed out")

    if process.returncode != 0:
        message = stderr.decode().strip() or stdout.decode().strip() or "nmcli failed"

        raise ProtocolError(ERROR_WIFI_FAILED, message)

    return stdout.decode()


def system_status() -> SystemStatus:
    """
    Seconds since boot and the CPU temperature in °C (None when unreadable).
    """
    try:
        uptime = int(float(UPTIME_PATH.read_text().split()[0]))

    except (OSError, ValueError, IndexError):
        uptime = 0

    try:
        temperature = round(int(TEMPERATURE_PATH.read_text().strip()) / 1000, 1)

    except (OSError, ValueError):
        temperature = None

    return {"uptime": uptime, "temperature": temperature}


class Network:
    """
    The cube's WiFi: scan, connect, forget and report status.
    """

    def __init__(self, interface: str | None = None) -> None:
        """
        Uses the given WiFi device, or finds it on first use.
        """
        self._interface = interface
        """
        The WiFi device name (wlan0 on a Pi).
        """

        self._lock = asyncio.Lock()
        """
        Held while a scan or a connection runs, so a second one is answered with `busy`.
        """

        self._connecting_ssid: str | None = None
        """
        The network being joined right now, if any.
        """

        self._failed = False
        """
        Whether the last attempt to join a network failed.
        """

    async def wifi_interface(self) -> str:
        """
        The WiFi device name, found once.
        """
        if self._interface is None:
            output = await run_nmcli("-t", "-f", "DEVICE,TYPE", "device")

            for line in output.splitlines():
                device, kind = pad_fields(split_terse(line), 2)

                if kind == "wifi":
                    self._interface = device
                    break

            else:
                raise ProtocolError(ERROR_INTERNAL, "No WiFi device found")

        return self._interface

    async def scan(self) -> dict[str, list[WifiNetwork]]:
        """
        The networks around the cube, one per SSID (the strongest), best signal first.
        """
        if self._lock.locked():
            raise ProtocolError(ERROR_BUSY, "Another WiFi operation is running")

        async with self._lock:
            output = await run_nmcli(
                "-t", "-f", "SSID,SIGNAL,SECURITY",
                "device", "wifi", "list", "--rescan", "yes",
                timeout=SCAN_TIMEOUT,
            )

        networks: dict[str, WifiNetwork] = {}

        for line in output.splitlines():
            ssid, signal, security = pad_fields(split_terse(line), 3)

            if not ssid:
                continue

            network: WifiNetwork = {
                "ssid": ssid,
                "signal": int(signal) if signal.isdigit() else 0,
                "secure": security not in ("", "--"),
            }

            if ssid not in networks or networks[ssid]["signal"] < network["signal"]:
                networks[ssid] = network

        ordered = sorted(networks.values(), key=lambda network: -network["signal"])

        return {"networks": ordered}

    async def saved(self) -> list[str]:
        """
        Names of the WiFi connections NetworkManager remembers.
        """
        output = await run_nmcli("-t", "-f", "NAME,TYPE", "connection", "show")
        saved = []

        for line in output.splitlines():
            name, kind = pad_fields(split_terse(line), 2)

            if kind == WIFI_CONNECTION_TYPE:
                saved.append(name)

        return saved

    async def wifi_status(self) -> WifiStatus:
        """
        Where the WiFi connection stands.
        """
        interface = await self.wifi_interface()

        status: WifiStatus = {
            "state": WIFI_DISCONNECTED,
            "ssid": None,
            "ip": None,
            "signal": None,
            "saved": await self.saved(),
        }

        if self._connecting_ssid is not None:
            status["state"] = WIFI_CONNECTING
            status["ssid"] = self._connecting_ssid

            return status

        output = await run_nmcli(
            "-t", "-f", "GENERAL.STATE,GENERAL.CONNECTION,IP4.ADDRESS",
            "device", "show", interface,
        )
        values: dict[str, str] = {}

        for line in output.splitlines():
            key, _, value = line.partition(":")

            values.setdefault(key.split("[")[0], value)

        if values.get("GENERAL.STATE", "").startswith("100"):
            status["state"] = WIFI_CONNECTED
            status["ssid"] = values.get("GENERAL.CONNECTION") or None
            status["ip"] = values.get("IP4.ADDRESS", "").split("/")[0] or None
            status["signal"] = await self._signal(interface)

        elif self._failed:
            status["state"] = WIFI_FAILED

        return status

    async def _signal(self, interface: str) -> int | None:
        """
        Signal strength of the network in use, 0 to 100.
        """
        output = await run_nmcli("-t", "-f", "IN-USE,SIGNAL", "device", "wifi", "list", "ifname", interface)

        for line in output.splitlines():
            in_use, signal = pad_fields(split_terse(line), 2)

            if in_use == "*" and signal.isdigit():
                return int(signal)

        return None

    async def connect(self, ssid: str, password: str | None = None, hidden: bool = False) -> WifiStatus:
        """
        Joins a network and returns the new status; keeps the previous network if it fails.

        Without a password this joins a saved or open network.
        """
        if not ssid:
            raise ProtocolError(ERROR_BAD_REQUEST, "ssid is required")

        if self._lock.locked():
            raise ProtocolError(ERROR_BUSY, "Another WiFi operation is running")

        async with self._lock:
            known = await self.saved()
            previous = (await self.wifi_status())["ssid"]

            self._connecting_ssid = ssid
            self._failed = False

            try:
                if ssid in known and not password:
                    await run_nmcli(
                        "--wait", str(CONNECT_TIMEOUT), "connection", "up", ssid,
                        timeout=CONNECT_TIMEOUT + 5,
                    )

                else:
                    command = ["--wait", str(CONNECT_TIMEOUT), "device", "wifi", "connect", ssid]

                    if password:
                        command += ["password", password]

                    if hidden:
                        command += ["hidden", "yes"]

                    await run_nmcli(*command, timeout=CONNECT_TIMEOUT + 5)

            except ProtocolError:
                self._failed = True

                await self._recover(ssid, ssid in known, previous)

                raise

            finally:
                self._connecting_ssid = None

        return await self.wifi_status()

    async def _recover(self, ssid: str, was_saved: bool, previous: str | None) -> None:
        """
        After a failed join: drops the half-made profile and goes back to the old network.
        """
        try:
            if not was_saved:
                await run_nmcli("connection", "delete", ssid)

            if previous and previous != ssid:
                await run_nmcli("connection", "up", previous, timeout=CONNECT_TIMEOUT)

        except ProtocolError:
            pass

    async def forget(self, ssid: str) -> None:
        """
        Removes a saved network, dropping the connection if it is the current one.
        """
        if not ssid:
            raise ProtocolError(ERROR_BAD_REQUEST, "ssid is required")

        # `connection delete` also takes the connection down when it is active.
        await run_nmcli("connection", "delete", ssid)
