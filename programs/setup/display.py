"""
Shows the PIN on the LED matrix while a page is connected, so only someone next to the cube sees it.

It draws through the matrix program, over whatever main is showing, and takes the PIN off again
when the page leaves. If the matrix program is not running the PIN is still in the log.
"""

import logging

from programs.common.matrix_client import MatrixClient
from programs.common.matrix_protocol import text


logger = logging.getLogger(__name__)
"""
Where this module reports problems.
"""

TEXT_LEFT = 4
"""
Pixels between the left edge of the matrix and the text.
"""

LABEL_BASELINE = 24
"""
Pixel row of the baseline of the "PIN" label.
"""

PIN_BASELINE = 52
"""
Pixel row of the baseline of the PIN digits.
"""


class PinDisplay:
    """
    Draws the PIN on the matrix and takes it off again.
    """

    def __init__(self, matrix: MatrixClient, pin: str | None) -> None:
        """
        Prepares to show `pin` through `matrix`.
        """
        self._matrix = matrix
        """
        The connection to the matrix program.
        """

        self._pin = pin
        """
        The PIN to show, or None when no PIN is needed.
        """

    def show(self) -> None:
        """
        Draws the PIN.
        """
        if self._pin is None:
            return

        logger.info("PIN: %s", self._pin)

        self._matrix.show([
            text("PIN", TEXT_LEFT, LABEL_BASELINE),
            text(self._pin, TEXT_LEFT, PIN_BASELINE),
        ])

    def clear(self) -> None:
        """
        Takes the PIN off the matrix.
        """
        self._matrix.clear()
