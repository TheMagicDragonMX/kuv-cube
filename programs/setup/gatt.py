"""
The BlueZ side: the GATT service, the advertisement and the disconnect watcher.

This is the only file that talks to the Bluetooth stack. It hands what pages write to the Bridge
and gives the Bridge a way to notify.
"""

import asyncio
import logging
import os

from bluez_peripheral.advert import Advertisement
from bluez_peripheral.agent import NoIoAgent
from bluez_peripheral.gatt.characteristic import (
    CharacteristicFlags,
    CharacteristicReadOptions,
    CharacteristicWriteOptions,
    characteristic,
)
from bluez_peripheral.gatt.service import Service, ServiceCollection
from bluez_peripheral.util import Adapter, get_message_bus
from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus
from dbus_next.errors import DBusError

from programs.setup.bridge import Bridge
from programs.setup.protocol import RX_CHARACTERISTIC_UUID, SERVICE_UUID, TX_CHARACTERISTIC_UUID


logger = logging.getLogger(__name__)
"""
Where this module reports what it does.
"""

REQUIRE_PAIRING = os.environ.get("KUV_SETUP_PAIRING") == "1"
"""
When true, writing requires the phone to pair with the cube first, which encrypts the link and
protects the WiFi password. Off by default: the OS asks the user to pair, which not every setup wants.
"""

UNSET_APPEARANCE = 0xFFFF
"""
BlueZ leaves the appearance out of the advertisement when it has this value, saving 4 bytes of the
31 an advertisement has.
"""

UNKNOWN_DEVICE = "unknown"
"""
Stands in for the device path when BlueZ does not tell which device wrote.
"""

POWER_ON_ATTEMPTS = 10
"""
Times the adapter's power is checked before giving up.
"""

POWER_ON_DELAY = 0.5
"""
Seconds between those checks.
"""

BLUEZ_SERVICE = "org.bluez"
"""
The bus name BlueZ answers on.
"""

BLUEZ_ROOT_PATH = "/org/bluez"
"""
The object under which BlueZ exposes its adapters.
"""

ADAPTER_INTERFACE = "org.bluez.Adapter1"
"""
The interface that marks an object as a Bluetooth adapter.
"""

BLUEZ_PROPERTIES_RULE = (
    "type='signal',sender='org.bluez',"
    "interface='org.freedesktop.DBus.Properties',member='PropertiesChanged'"
)
"""
Match rule that delivers BlueZ's property changes, used to notice a page disconnecting.
"""


async def unblock_bluetooth() -> None:
    """
    Lifts the rfkill soft block on Bluetooth, which BlueZ cannot power the adapter through.

    Best effort: without rfkill, or when it fails, powering the adapter reports the real problem.
    """
    try:
        process = await asyncio.create_subprocess_exec("rfkill", "unblock", "bluetooth")

        await process.wait()

    except OSError:
        pass


async def find_adapter(bus: MessageBus) -> Adapter:
    """
    The first Bluetooth adapter BlueZ exposes.

    `Adapter.get_first` treats every node under /org/bluez as an adapter and fails when BlueZ also
    exposes something else there (a `test` node shows up on the cube), so look for the interface.
    """
    root = await bus.introspect(BLUEZ_SERVICE, BLUEZ_ROOT_PATH)

    for node in root.nodes:
        path = f"{BLUEZ_ROOT_PATH}/{node.name}"
        introspection = await bus.introspect(BLUEZ_SERVICE, path)

        if any(interface.name == ADAPTER_INTERFACE for interface in introspection.interfaces):
            return Adapter(bus.get_proxy_object(BLUEZ_SERVICE, path, introspection))

    raise RuntimeError("No Bluetooth adapter found")


async def power_on(adapter: Adapter) -> None:
    """
    Makes sure the adapter is powered.

    Right after the rfkill unblock BlueZ powers the adapter on by itself, and asking it again at
    that moment fails, so give it a moment first and only then ask.
    """
    for attempt in range(POWER_ON_ATTEMPTS):
        if await adapter.get_powered():
            return

        await asyncio.sleep(POWER_ON_DELAY)

        if attempt == POWER_ON_ATTEMPTS // 2:
            try:
                await adapter.set_powered(True)

            except DBusError:
                pass

    if not await adapter.get_powered():
        raise RuntimeError("The Bluetooth adapter would not power on")


class SetupService(Service):
    """
    The GATT service with the RX (write) and TX (notify) characteristics.
    """

    def __init__(self) -> None:
        """
        Creates the service; the bridge is attached with `attach` before pages can write.
        """
        self._bridge: Bridge | None = None
        """
        Receives what pages write.
        """

        super().__init__(SERVICE_UUID, True)

    def attach(self, bridge: Bridge) -> None:
        """
        Sets the bridge that receives writes.
        """
        self._bridge = bridge

    def notify(self, chunk: bytes) -> None:
        """
        Notifies one chunk to the subscribed pages.
        """
        self.tx.changed(chunk)

    @characteristic(
        RX_CHARACTERISTIC_UUID,
        CharacteristicFlags.ENCRYPT_WRITE if REQUIRE_PAIRING else CharacteristicFlags.WRITE,
    )
    def rx(self, options: CharacteristicReadOptions) -> bytes:
        """
        Page to cube. Write-only: reading gives nothing.
        """
        return b""

    @rx.setter
    def rx(self, value: bytes, options: CharacteristicWriteOptions) -> None:
        """
        A page wrote a chunk of a request.
        """
        if self._bridge is not None:
            self._bridge.receive(options.device or UNKNOWN_DEVICE, bytes(value), options.mtu or 0)

    @characteristic(TX_CHARACTERISTIC_UUID, CharacteristicFlags.NOTIFY)
    def tx(self, options: CharacteristicReadOptions) -> bytes:
        """
        Cube to page. Responses and events are pushed as notifications.
        """
        return b""


class GattServer:
    """
    Registers the service and the advertisement, and keeps them running.
    """

    def __init__(self, name: str) -> None:
        """
        Advertises as `name`, e.g. "Kuv-A3F2".
        """
        self._name = name
        """
        The advertised name.
        """

        self.service = SetupService()
        """
        The GATT service.
        """

        self._bus: MessageBus | None = None
        """
        The system bus connection.
        """

        self._services: ServiceCollection | None = None
        """
        The registered services.
        """

        self._advert: Advertisement | None = None
        """
        The registered advertisement.
        """

        self._agent: NoIoAgent | None = None
        """
        Accepts pairing without asking anything, when pairing is required.
        """

    async def start(self, bridge: Bridge) -> None:
        """
        Powers the adapter, registers the service and starts advertising.
        """
        self.service.attach(bridge)

        await unblock_bluetooth()

        self._bus = await get_message_bus()
        adapter = await find_adapter(self._bus)

        await power_on(adapter)

        logger.info("Bluetooth adapter is on")

        if REQUIRE_PAIRING:
            self._agent = NoIoAgent()

            await self._agent.register(self._bus)

        self._services = ServiceCollection([self.service])

        await self._services.register(self._bus, adapter=adapter)

        self._advert = Advertisement(
            self._name,
            [SERVICE_UUID],
            UNSET_APPEARANCE,
            0,
        )

        await self._advert.register(self._bus, adapter)

        await self._watch_disconnections(bridge)

        logger.info("Bluetooth service registered%s", " (pairing required)" if REQUIRE_PAIRING else "")

    async def stop(self) -> None:
        """
        Unregisters everything and closes the bus.
        """
        if self._services is not None:
            await self._services.unregister()

        if self._agent is not None and self._bus is not None:
            await self._agent.unregister(self._bus)

        if self._bus is not None:
            self._bus.disconnect()

    async def _watch_disconnections(self, bridge: Bridge) -> None:
        """
        Tells the bridge when a device's `Connected` property turns false.
        """
        assert self._bus is not None

        def on_message(message: Message) -> None:
            """
            Looks at one bus message and reports a page that disconnected.
            """
            if message.message_type != MessageType.SIGNAL or message.member != "PropertiesChanged":
                return

            if message.body[0] != "org.bluez.Device1" or message.path is None:
                return

            connected = message.body[1].get("Connected")

            if connected is not None and connected.value is False:
                bridge.disconnected(message.path)

        self._bus.add_message_handler(on_message)

        await self._bus.call(Message(
            destination="org.freedesktop.DBus",
            path="/org/freedesktop/DBus",
            interface="org.freedesktop.DBus",
            member="AddMatch",
            signature="s",
            body=[BLUEZ_PROPERTIES_RULE],
        ))
