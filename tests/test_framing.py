"""
Tests for the message framing.
"""

import json
import unittest

from src.framing import MessageDecoder, encode_message


class FramingTest(unittest.TestCase):
    """
    Messages survive being cut into chunks and joined back.
    """

    def test_round_trip_in_small_chunks(self) -> None:
        """
        A message with non-ASCII text, cut in 7-byte chunks, comes back whole.
        """
        message = {"id": 1, "ok": True, "result": {"ssid": "Café ñandú 📶"}}
        decoder = MessageDecoder()
        received = []

        for chunk in encode_message(message, 7):
            received += decoder.push(chunk)

        self.assertEqual(received, [message])

    def test_several_messages_in_one_chunk(self) -> None:
        """
        Two messages that arrive together are both returned.
        """
        data = b'{"id":1}\n{"id":2}\n'

        self.assertEqual(MessageDecoder().push(data), [{"id": 1}, {"id": 2}])

    def test_garbage_lines_are_dropped(self) -> None:
        """
        Lines that are not JSON are skipped without losing the good ones.
        """
        data = b'nope\n\n{"id":3}\n'

        self.assertEqual(MessageDecoder().push(data), [{"id": 3}])

    def test_chunks_are_compact_json(self) -> None:
        """
        The encoded message is compact JSON plus a newline.
        """
        data = b"".join(encode_message({"a": 1}))

        self.assertEqual(data, b'{"a":1}\n')
        self.assertEqual(json.loads(data), {"a": 1})
