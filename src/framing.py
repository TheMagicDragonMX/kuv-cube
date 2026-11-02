"""
How messages travel over the characteristics.

A Bluetooth write or notification carries only a few hundred bytes (sometimes just 20), and a
list of WiFi networks does not fit in one. So every message is sent as compact JSON plus a
newline, cut into chunks; the other side joins chunks until it sees the newline.
"""

import json
from typing import Any

from src.protocol import DEFAULT_CHUNK_SIZE, MAX_MESSAGE_SIZE


NEWLINE = b"\n"
"""
Byte that ends every message.
"""


def encode_message(message: Any, chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[bytes]:
    """
    The chunks to send for one message, in order.

    A chunk can end in the middle of a UTF-8 character; the receiver only decodes whole messages.
    """
    data = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode() + NEWLINE

    return [data[start:start + chunk_size] for start in range(0, len(data), chunk_size)]


def parse_line(line: bytes) -> Any | None:
    """
    The JSON on one line, or None when the line is empty or not JSON.
    """
    if not line.strip():
        return None

    try:
        return json.loads(line.decode())

    except ValueError:
        return None


class MessageDecoder:
    """
    Joins received chunks back into messages.
    """

    def __init__(self) -> None:
        """
        Starts with nothing received.
        """
        self._buffer = b""
        """
        Bytes received so far that do not yet end in a newline.
        """

    def push(self, chunk: bytes) -> list[Any]:
        """
        Adds a chunk and returns the messages it completed (often none, sometimes several).

        Lines that are not valid JSON are dropped.
        """
        *lines, self._buffer = (self._buffer + chunk).split(NEWLINE)

        if len(self._buffer) > MAX_MESSAGE_SIZE:
            self._buffer = b""

        messages = []

        for line in lines:
            message = parse_line(line)

            if message is not None:
                messages.append(message)

        return messages
