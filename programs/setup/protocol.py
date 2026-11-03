"""
The setup protocol the cube speaks over Bluetooth.

Mirror of kuv-client/src/app/setup/protocol.ts: keep both in sync, and bump PROTOCOL_VERSION
when a change would break a page (or a cube) that speaks the previous version.
"""

from typing import Any, Literal, NotRequired, TypeAlias, TypedDict


PROTOCOL_VERSION = 1
"""
The version of the protocol the cube speaks.
"""

DEVICE_NAME_PREFIX = "Kuv"
"""
Cubes advertise a name that starts with this, e.g. "Kuv-A3F2".
"""

SERVICE_UUID = "6b750001-c0be-4f2a-9e1d-5b3a7c2e9d10"
"""
The GATT service the cube exposes for setup.
"""

RX_CHARACTERISTIC_UUID = "6b750002-c0be-4f2a-9e1d-5b3a7c2e9d10"
"""
Page to cube: the page writes requests here, in chunks.
"""

TX_CHARACTERISTIC_UUID = "6b750003-c0be-4f2a-9e1d-5b3a7c2e9d10"
"""
Cube to page: the cube notifies responses and events here, in chunks.
"""

DEFAULT_CHUNK_SIZE = 20
"""
Bytes per notification when the MTU is unknown (the default ATT payload of 23 minus 3 of header).
"""

MAX_MESSAGE_SIZE = 64 * 1024
"""
A message that grows past this without a newline is garbage; the buffer is dropped.
"""

STATUS_EVENT_INTERVAL = 5
"""
Seconds between the status events sent while a page is connected.
"""

WIFI_DISCONNECTED = "disconnected"
"""
The cube is not connected to any network.
"""

WIFI_CONNECTING = "connecting"
"""
The cube is joining a network.
"""

WIFI_CONNECTED = "connected"
"""
The cube is connected to a network.
"""

WIFI_FAILED = "failed"
"""
The last attempt to join a network failed.
"""

ERROR_UNAUTHORIZED = "unauthorized"
"""
The operation needs `auth` first, or the PIN was wrong.
"""

ERROR_LOCKED = "locked"
"""
Too many wrong PINs: `auth` is refused for a minute.
"""

ERROR_BAD_REQUEST = "bad_request"
"""
Missing or wrong params.
"""

ERROR_UNKNOWN_OP = "unknown_op"
"""
An operation the cube does not know.
"""

ERROR_WIFI_FAILED = "wifi_failed"
"""
The cube could not join the network (wrong password, out of range...).
"""

ERROR_BUSY = "busy"
"""
Another long operation (a scan, a connection) is still running.
"""

ERROR_INTERNAL = "internal"
"""
Anything else.
"""

WifiState: TypeAlias = Literal["disconnected", "connecting", "connected", "failed"]
"""
Where the cube's WiFi connection stands.
"""


class CubeInfo(TypedDict):
    """
    What a cube says about itself before anything else, even before `auth`.
    """

    name: str
    """
    The advertised name, e.g. "Kuv-A3F2".
    """

    version: str
    """
    Version of the software running on the cube.
    """

    hostname: str
    """
    The cube's network hostname.
    """

    protocol: int
    """
    The PROTOCOL_VERSION the cube speaks.
    """

    authRequired: bool
    """
    When true, every operation except `info` and `auth` is refused until `auth` succeeds.
    """


class WifiStatus(TypedDict):
    """
    The cube's WiFi connection, as reported by `status` and by status events.
    """

    state: WifiState
    """
    Where the connection stands.
    """

    ssid: str | None
    """
    The network it is connected (or connecting) to.
    """

    ip: str | None
    """
    The IP address the cube got on that network, once connected.
    """

    signal: int | None
    """
    Signal strength, 0 to 100.
    """

    saved: list[str]
    """
    SSIDs the cube remembers and joins on its own.
    """


class SystemStatus(TypedDict):
    """
    How the Raspberry Pi itself is doing.
    """

    uptime: int
    """
    Seconds since the cube booted.
    """

    temperature: float | None
    """
    CPU temperature in °C, when the cube can read it.
    """


class CubeStatus(TypedDict):
    """
    Everything the cube reports in a `status` answer or event.
    """

    wifi: WifiStatus
    """
    The WiFi connection.
    """

    system: SystemStatus
    """
    The Pi's health.
    """


class WifiNetwork(TypedDict):
    """
    A network the cube sees when scanning.
    """

    ssid: str
    """
    The network name.
    """

    signal: int
    """
    Signal strength, 0 to 100.
    """

    secure: bool
    """
    Needs a password.
    """


class Request(TypedDict):
    """
    A message from the page to the cube.
    """

    id: int
    """
    Chosen by the page; the response carries the same id.
    """

    op: str
    """
    Which operation to run.
    """

    params: NotRequired[Any]
    """
    The operation's params, when it takes any.
    """


class ProtocolError(Exception):
    """
    An error that is sent back to the page as `{"ok": false, "error": {code, message}}`.
    """

    def __init__(self, code: str, message: str) -> None:
        """
        Remembers the error code and the human-readable message.
        """
        super().__init__(message)

        self.code = code
        """
        One of the ERROR_* codes.
        """

        self.message = message
        """
        What went wrong, for a person.
        """
