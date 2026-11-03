"""
Connects the Bluetooth characteristics to the dispatcher.

It keeps one state per connected page, turns written chunks into requests, sends responses back as
notification chunks, and pushes `status` events. It does not know BlueZ: bytes come in through
`receive` and go out through the `notify` callback, so it can be tested without a radio.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from programs.setup.dispatcher import Dispatcher, Session
from programs.setup.framing import MessageDecoder, encode_message
from programs.setup.protocol import DEFAULT_CHUNK_SIZE, STATUS_EVENT_INTERVAL


logger = logging.getLogger(__name__)
"""
Where this module reports problems.
"""

STATUS_POLL_INTERVAL = 2.0
"""
Seconds between checks for a change in the status, while a page is connected.
"""

CHUNK_DELAY = 0.02
"""
Seconds between notification chunks, so BlueZ is not flooded.
"""

ATT_HEADER_SIZE = 3
"""
Bytes of every notification taken by the ATT header, out of the MTU.
"""


class Link:
    """
    One connected page.
    """

    def __init__(self) -> None:
        """
        Starts locked, with nothing received and the default MTU.
        """
        self.session = Session()
        """
        The PIN unlock of this connection.
        """

        self.decoder = MessageDecoder()
        """
        Joins the chunks this page writes.
        """

        self.mtu = 0
        """
        The MTU negotiated with this page, or 0 when unknown.
        """

    @property
    def chunk_size(self) -> int:
        """
        Bytes per notification: the MTU minus the header, or the default when the MTU is unknown.
        """
        if self.mtu <= DEFAULT_CHUNK_SIZE + ATT_HEADER_SIZE:
            return DEFAULT_CHUNK_SIZE

        return self.mtu - ATT_HEADER_SIZE


class Bridge:
    """
    Moves messages between the connected pages and the dispatcher.
    """

    def __init__(
        self,
        dispatcher: Dispatcher,
        notify: Callable[[bytes], None],
        status_interval: float = STATUS_EVENT_INTERVAL,
        poll_interval: float = STATUS_POLL_INTERVAL,
        chunk_delay: float = CHUNK_DELAY,
        on_first_connect: Callable[[], None] | None = None,
        on_last_disconnect: Callable[[], None] | None = None,
    ) -> None:
        """
        Sends notifications through `notify`, one chunk per call.
        """
        self._dispatcher = dispatcher
        """
        Answers the requests.
        """

        self._notify = notify
        """
        Sends one chunk to the subscribed pages.
        """

        self._status_interval = status_interval
        """
        Seconds after which a status event is sent even if nothing changed.
        """

        self._poll_interval = poll_interval
        """
        Seconds between checks for a change in the status.
        """

        self._chunk_delay = chunk_delay
        """
        Seconds between notification chunks.
        """

        self._on_first_connect = on_first_connect
        """
        Called when a page connects and none was connected before.
        """

        self._on_last_disconnect = on_last_disconnect
        """
        Called when the last connected page drops.
        """

        self._links: dict[str, Link] = {}
        """
        The connected pages, by the Bluetooth address path BlueZ gives them.
        """

        self._send_lock = asyncio.Lock()
        """
        Keeps the chunks of two messages from interleaving.
        """

        self._tasks: set[asyncio.Task] = set()
        """
        Requests being answered, kept so they are not garbage collected.
        """

        self._status_task: asyncio.Task | None = None
        """
        The loop that sends status events, running while a page is connected.
        """

    def receive(self, device: str, data: bytes, mtu: int = 0) -> None:
        """
        Handles a chunk a page wrote.
        """
        link = self._links.get(device)

        if link is None:
            link = self._links[device] = Link()

            logger.info("Page connected (%d now)", len(self._links))

            if len(self._links) == 1 and self._on_first_connect is not None:
                self._on_first_connect()

        if mtu:
            link.mtu = mtu

        for message in link.decoder.push(bytes(data)):
            task = asyncio.get_running_loop().create_task(self._answer(link, message))

            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        if self._status_task is None or self._status_task.done():
            self._status_task = asyncio.get_running_loop().create_task(self._send_status_events())

    def disconnected(self, device: str) -> None:
        """
        Forgets a page that dropped; its PIN unlock ends with it.
        """
        if self._links.pop(device, None) is None:
            return

        logger.info("Page disconnected (%d left)", len(self._links))

        if not self._links and self._on_last_disconnect is not None:
            self._on_last_disconnect()

    @property
    def connected(self) -> bool:
        """
        Whether any page is connected.
        """
        return bool(self._links)

    async def close(self) -> None:
        """
        Stops the status events and the requests still running.
        """
        tasks = [*self._tasks]

        if self._status_task is not None:
            tasks.append(self._status_task)

        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _answer(self, link: Link, message: Any) -> None:
        """
        Runs one request and sends its response.
        """
        response = await self._dispatcher.handle(link.session, message)

        if response is not None:
            await self._send(link, response)

    async def _send(self, link: Link, message: Any) -> None:
        """
        Notifies one message, cut into chunks that fit the page's MTU.
        """
        async with self._send_lock:
            for chunk in encode_message(message, link.chunk_size):
                self._notify(chunk)

                await asyncio.sleep(self._chunk_delay)

    def _may_see_status(self) -> bool:
        """
        Whether every connected page may see the status.

        Notifications go to every subscriber, so an event is only sent when none of them is locked.
        """
        if not self._dispatcher.auth_required:
            return True

        return all(link.session.authenticated for link in self._links.values())

    async def _send_status_events(self) -> None:
        """
        While a page is connected, sends a `status` event when the WiFi changes and every
        `status_interval` seconds (the uptime and temperature ride along).
        """
        last_wifi = None
        last_sent = 0.0

        while self._links:
            await asyncio.sleep(self._poll_interval)

            if not self._links or not self._may_see_status():
                continue

            try:
                status = await self._dispatcher.status()

            except Exception:
                logger.exception("Could not read the status")

                continue

            now = time.monotonic()

            if status["wifi"] != last_wifi or now - last_sent >= self._status_interval:
                last_wifi = status["wifi"]
                last_sent = now

                link = next(iter(self._links.values()), None)

                if link is not None:
                    await self._send(link, {"event": "status", "data": status})
