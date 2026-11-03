"""
Shows the PIN on the LED matrix while a page is connected, so only someone next to the cube sees it.

Best effort: without the matrix library, or when the matrix cannot be opened, the PIN is only
logged and setup carries on.
"""

import logging
import os


logger = logging.getLogger(__name__)
"""
Where this module reports problems.
"""

FONT_PATH = os.environ.get("KUV_FONT", "/home/luna/rpi-rgb-led-matrix/fonts/10x20.bdf")
"""
BDF font used to draw the PIN.
"""

ENABLED = os.environ.get("KUV_SETUP_DISPLAY") != "0"
"""
Set KUV_SETUP_DISPLAY=0 to keep setup away from the matrix, e.g. while testing next to a running cube.
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
    Draws the PIN on the matrix and clears it again.
    """

    def __init__(self, pin: str | None) -> None:
        """
        Prepares to show `pin`; the matrix is opened on first use.
        """
        self._pin = pin
        """
        The PIN to show, or None when no PIN is needed.
        """

        self._matrix = None
        """
        The opened matrix, once there is one.
        """

        self._unavailable = False
        """
        Set after a failure to open the matrix, so it is not retried on every connection.
        """

    def show(self) -> None:
        """
        Draws the PIN.
        """
        if self._pin is None:
            return

        matrix = self._open() if ENABLED else None

        if matrix is None:
            logger.info("PIN: %s (no matrix to show it on)", self._pin)

            return

        try:
            from rgbmatrix import graphics

            font = graphics.Font()
            font.LoadFont(FONT_PATH)

            canvas = matrix.CreateFrameCanvas()
            color = graphics.Color(255, 255, 255)

            graphics.DrawText(canvas, font, TEXT_LEFT, LABEL_BASELINE, color, "PIN")
            graphics.DrawText(canvas, font, TEXT_LEFT, PIN_BASELINE, color, self._pin)
            matrix.SwapOnVSync(canvas)

        except Exception:
            logger.exception("Could not draw the PIN")

    def clear(self) -> None:
        """
        Blanks the matrix.
        """
        if self._matrix is not None:
            self._matrix.Clear()

    def _open(self):
        """
        The matrix, opened on first use, or None when it is not available.
        """
        if self._matrix is None and not self._unavailable:
            try:
                from programs.common.matrix import create_matrix

                self._matrix = create_matrix()

            except Exception:
                logger.exception("Could not open the LED matrix")

                self._unavailable = True

        return self._matrix
