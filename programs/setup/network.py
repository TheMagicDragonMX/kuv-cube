"""
WiFi control through NetworkManager (nmcli), shaped like the setup protocol's answers.
"""

import asyncio
import logging
import re
from pathlib import Path

from programs.setup.protocol import (
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


logger = logging.getLogger(__name__)
"""
Where this module reports what it does.
"""

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

        logger.info("Scan found %d networks", len(ordered))

        return {"networks": ordered}

    async def profiles(self) -> dict[str, str]:
        """
        The WiFi connections NetworkManager remembers, as profile name to SSID.

        A profile's name is not always its SSID (Raspberry Pi OS names them like
        "netplan-wlan0-Home"), so the SSID is read from the profile itself.
        """
        output = await run_nmcli("-t", "-f", "NAME,TYPE", "connection", "show")
        names = []

        for line in output.splitlines():
            name, kind = pad_fields(split_terse(line), 2)

            if kind == WIFI_CONNECTION_TYPE:
                names.append(name)

        ssids = await asyncio.gather(*(
            run_nmcli("-g", "802-11-wireless.ssid", "connection", "show", name)
            for name in names
        ))

        return {name: ssid.strip() or name for name, ssid in zip(names, ssids)}

    async def saved(self) -> list[str]:
        """
        SSIDs of the WiFi networks NetworkManager remembers.
        """
        return list(dict.fromkeys((await self.profiles()).values()))

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
            "-t", "-f", "GENERAL.STATE,IP4.ADDRESS",
            "device", "show", interface,
        )
        values: dict[str, str] = {}

        for line in output.splitlines():
            key, _, value = line.partition(":")

            values.setdefault(key.split("[")[0], value)

        if values.get("GENERAL.STATE", "").startswith("100"):
            status["state"] = WIFI_CONNECTED
            status["ip"] = values.get("IP4.ADDRESS", "").split("/")[0] or None
            status["ssid"], status["signal"] = await self._active_network(interface)

        elif self._failed:
            status["state"] = WIFI_FAILED

        return status

    async def _active_network(self, interface: str) -> tuple[str | None, int | None]:
        """
        The SSID and signal strength (0 to 100) of the network in use.
        """
        output = await run_nmcli("-t", "-f", "IN-USE,SSID,SIGNAL", "device", "wifi", "list", "ifname", interface)

        for line in output.splitlines():
            in_use, ssid, signal = pad_fields(split_terse(line), 3)

            if in_use == "*":
                return ssid or None, int(signal) if signal.isdigit() else None

        return None, None

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
            before = await self.profiles()
            saved_names = [name for name, known in before.items() if known == ssid]
            previous = (await self.wifi_status())["ssid"]

            self._connecting_ssid = ssid
            self._failed = False

            logger.info("Joining %s%s", ssid, " (saved)" if saved_names and not password else "")

            try:
                if saved_names and not password:
                    await run_nmcli(
                        "--wait", str(CONNECT_TIMEOUT), "connection", "up", saved_names[0],
                        timeout=CONNECT_TIMEOUT + 5,
                    )

                else:
                    command = ["--wait", str(CONNECT_TIMEOUT), "device", "wifi", "connect", ssid]

                    if password:
                        command += ["password", password]

                    if hidden:
                        command += ["hidden", "yes"]

                    await run_nmcli(*command, timeout=CONNECT_TIMEOUT + 5)

            except ProtocolError as error:
                self._failed = True

                logger.warning("Could not join %s: %s", ssid, error.message)

                await self._recover(before, previous)

                raise

            finally:
                self._connecting_ssid = None

        logger.info("Joined %s", ssid)

        return await self.wifi_status()

    async def _recover(self, before: dict[str, str], previous: str | None) -> None:
        """
        After a failed join: drops the profiles it left behind and goes back to the old network.

        `before` is the profiles that existed when the attempt started.
        """
        try:
            for name in (await self.profiles()):
                if name not in before:
                    await run_nmcli("connection", "delete", name)

            previous_names = [name for name, known in before.items() if known == previous]

            if previous_names:
                await run_nmcli("connection", "up", previous_names[0], timeout=CONNECT_TIMEOUT)

                logger.info("Went back to %s", previous)

        except ProtocolError:
            pass

    async def forget(self, ssid: str) -> None:
        """
        Removes a saved network, dropping the connection if it is the current one.
        """
        if not ssid:
            raise ProtocolError(ERROR_BAD_REQUEST, "ssid is required")

        names = [name for name, known in (await self.profiles()).items() if known == ssid]

        if not names:
            raise ProtocolError(ERROR_BAD_REQUEST, f"{ssid} is not a saved network")

        # `connection delete` also takes the connection down when it is active.
        for name in names:
            await run_nmcli("connection", "delete", name)

        logger.info("Forgot %s", ssid)
