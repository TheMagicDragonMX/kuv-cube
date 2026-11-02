"""
Answers the setup requests: PIN, lockout and the routing of each operation.

It knows nothing about Bluetooth: it takes a decoded request and returns the response to send
back, so it can be tested without a radio.
"""

import asyncio
import hmac
import socket
import time
from collections.abc import Awaitable, Callable
from typing import Any

from src.network import Network, system_status
from src.protocol import (
    ERROR_BAD_REQUEST,
    ERROR_INTERNAL,
    ERROR_LOCKED,
    ERROR_UNAUTHORIZED,
    ERROR_UNKNOWN_OP,
    PROTOCOL_VERSION,
    CubeInfo,
    CubeStatus,
    ProtocolError,
)


MAX_PIN_ATTEMPTS = 5
"""
Wrong PINs in a row before `auth` is refused.
"""

LOCK_SECONDS = 60
"""
How long `auth` is refused after too many wrong PINs.
"""

REBOOT_DELAY = 1
"""
Seconds between answering `system.reboot` and rebooting, so the answer reaches the page.
"""

OPEN_OPERATIONS = ("info", "auth")
"""
Operations allowed before `auth` succeeds.
"""


async def reboot_system() -> None:
    """
    Reboots the Raspberry Pi.
    """
    process = await asyncio.create_subprocess_exec("systemctl", "reboot")

    await process.wait()


class Session:
    """
    One Bluetooth connection. The PIN unlock lasts until it drops.
    """

    def __init__(self) -> None:
        """
        Starts locked.
        """
        self.authenticated = False
        """
        Whether `auth` has succeeded on this connection.
        """


class Dispatcher:
    """
    Turns requests into responses.
    """

    def __init__(
        self,
        network: Network,
        name: str,
        version: str,
        pin: str | None,
        reboot: Callable[[], Awaitable[None]] = reboot_system,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        Sets up a cube called `name`; without a `pin` no operation needs `auth`.
        """
        self._network = network
        """
        The cube's WiFi.
        """

        self._name = name
        """
        The advertised name, e.g. "Kuv-A3F2".
        """

        self._version = version
        """
        Version of the software running on the cube.
        """

        self._pin = pin
        """
        The PIN `auth` checks, or None when no PIN is needed.
        """

        self._reboot = reboot
        """
        Reboots the Pi; replaced in tests.
        """

        self._clock = clock
        """
        Seconds on a steady clock; replaced in tests.
        """

        self._failed_attempts = 0
        """
        Wrong PINs since the last good one.
        """

        self._locked_until = 0.0
        """
        When the lockout ends, on the clock's scale.
        """

        self._reboot_task: asyncio.Task | None = None
        """
        Keeps the pending reboot from being garbage collected.
        """

    async def handle(self, session: Session, request: Any) -> dict[str, Any] | None:
        """
        The response to a request, or None when the message is not a request at all.

        Never raises: every failure becomes an error response.
        """
        if not isinstance(request, dict) or not isinstance(request.get("id"), int):
            return None

        request_id = request["id"]

        try:
            result = await self._run(session, request)

            return {"id": request_id, "ok": True, "result": result}

        except ProtocolError as error:
            return self._error(request_id, error.code, error.message)

        except Exception as error:
            return self._error(request_id, ERROR_INTERNAL, str(error) or type(error).__name__)

    async def status(self) -> CubeStatus:
        """
        The WiFi and system status, as sent in `status` answers and events.
        """
        return {"wifi": await self._network.wifi_status(), "system": system_status()}

    def info(self) -> CubeInfo:
        """
        What the cube says about itself.
        """
        return {
            "name": self._name,
            "version": self._version,
            "hostname": socket.gethostname(),
            "protocol": PROTOCOL_VERSION,
            "authRequired": self._pin is not None,
        }

    async def _run(self, session: Session, request: dict[str, Any]) -> Any:
        """
        Checks the session may run the operation, then runs it.
        """
        operation = request.get("op")
        params = request.get("params")

        if not isinstance(operation, str):
            raise ProtocolError(ERROR_BAD_REQUEST, "op is required")

        if params is not None and not isinstance(params, dict):
            raise ProtocolError(ERROR_BAD_REQUEST, "params must be an object")

        params = params or {}

        handlers = {
            "info": self._info,
            "auth": self._auth,
            "status": self._status,
            "wifi.scan": self._scan,
            "wifi.connect": self._connect,
            "wifi.forget": self._forget,
            "system.reboot": self._system_reboot,
        }

        handler = handlers.get(operation)

        if handler is None:
            raise ProtocolError(ERROR_UNKNOWN_OP, f"Unknown operation: {operation}")

        if self._pin is not None and not session.authenticated and operation not in OPEN_OPERATIONS:
            raise ProtocolError(ERROR_UNAUTHORIZED, "Send the PIN with `auth` first")

        return await handler(session, params)

    async def _info(self, session: Session, params: dict[str, Any]) -> CubeInfo:
        """
        Operation `info`: describes the cube.
        """
        return self.info()

    async def _auth(self, session: Session, params: dict[str, Any]) -> None:
        """
        Operation `auth`: unlocks the session when the PIN matches.
        """
        pin = params.get("pin")

        if not isinstance(pin, str):
            raise ProtocolError(ERROR_BAD_REQUEST, "pin is required")

        if self._pin is None:
            session.authenticated = True

            return None

        if self._clock() < self._locked_until:
            raise ProtocolError(ERROR_LOCKED, "Too many wrong PINs, try again later")

        if hmac.compare_digest(pin.encode(), self._pin.encode()):
            self._failed_attempts = 0
            session.authenticated = True

            return None

        self._failed_attempts += 1

        if self._failed_attempts >= MAX_PIN_ATTEMPTS:
            self._failed_attempts = 0
            self._locked_until = self._clock() + LOCK_SECONDS

            raise ProtocolError(ERROR_LOCKED, "Too many wrong PINs, try again later")

        raise ProtocolError(ERROR_UNAUTHORIZED, "Wrong PIN")

    async def _status(self, session: Session, params: dict[str, Any]) -> CubeStatus:
        """
        Operation `status`: the WiFi and system status.
        """
        return await self.status()

    async def _scan(self, session: Session, params: dict[str, Any]) -> Any:
        """
        Operation `wifi.scan`: the networks around the cube.
        """
        return await self._network.scan()

    async def _connect(self, session: Session, params: dict[str, Any]) -> Any:
        """
        Operation `wifi.connect`: joins a network.
        """
        ssid = params.get("ssid")
        password = params.get("password")
        hidden = params.get("hidden", False)

        if not isinstance(ssid, str) or not ssid:
            raise ProtocolError(ERROR_BAD_REQUEST, "ssid is required")

        if password is not None and not isinstance(password, str):
            raise ProtocolError(ERROR_BAD_REQUEST, "password must be a string")

        if not isinstance(hidden, bool):
            raise ProtocolError(ERROR_BAD_REQUEST, "hidden must be a boolean")

        return await self._network.connect(ssid, password or None, hidden)

    async def _forget(self, session: Session, params: dict[str, Any]) -> None:
        """
        Operation `wifi.forget`: removes a saved network.
        """
        ssid = params.get("ssid")

        if not isinstance(ssid, str) or not ssid:
            raise ProtocolError(ERROR_BAD_REQUEST, "ssid is required")

        await self._network.forget(ssid)

        return None

    async def _system_reboot(self, session: Session, params: dict[str, Any]) -> None:
        """
        Operation `system.reboot`: answers first, then reboots.
        """
        self._reboot_task = asyncio.create_task(self._reboot_later())

        return None

    async def _reboot_later(self) -> None:
        """
        Waits a moment so the answer reaches the page, then reboots.
        """
        await asyncio.sleep(REBOOT_DELAY)
        await self._reboot()

    def _error(self, request_id: int, code: str, message: str) -> dict[str, Any]:
        """
        An error response.
        """
        return {"id": request_id, "ok": False, "error": {"code": code, "message": message}}
