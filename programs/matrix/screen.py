"""
The LED panels: how they are wired and how to draw on them.
"""

import base64
import logging
import os

from programs.common.matrix_protocol import Item


logger = logging.getLogger(__name__)
"""
Where this module reports problems.
"""

PANEL_ROWS = 64
"""
Rows of LEDs in one panel.
"""

PANEL_COLUMNS = 64
"""
Columns of LEDs in one panel.
"""

PANEL_CHAIN_LENGTH = 2
"""
Panels daisy-chained on each output.
"""

PANEL_PARALLEL = 2
"""
Chains driven in parallel. Two, because the third output of the bonnet pulls GPIO 2 and 3 to ground, which leaves
the top half of its panels without green and blue. Going back to three needs a bonnet that does not do that.
"""

BRIGHTNESS = 15
"""
Brightness percentage, kept low to stay within the power supply and thermal limits.
"""

GPIO_SLOWDOWN = 6
"""
Slows the GPIO down so the panels keep up with the Pi 4.
"""

FONT_DIR = os.environ.get("KUV_FONT_DIR", "/home/luna/rpi-rgb-led-matrix/fonts")
"""
Folder with the BDF fonts that come with the matrix library.
"""


class Screen:
    """
    Draws scenes on the panels. Tests replace it with one that only records what it was asked to draw.
    """

    def __init__(self) -> None:
        """
        Does not touch the hardware until `open`.
        """
        self._matrix = None
        """
        The opened matrix.
        """

        self._canvas = None
        """
        The off-screen canvas drawn on before it is swapped in.
        """

        self._fonts: dict[str, object] = {}
        """
        Fonts loaded so far, by name.
        """

        self._fast_images = True
        """
        Whether pictures are copied to the canvas in one call. Turned off for good if the matrix library cannot do
        it with the installed imaging library, and then they are copied pixel by pixel.
        """

    def open(self) -> None:
        """
        Opens the panels, with the settings used by the demo executable.
        """
        from rgbmatrix import RGBMatrix, RGBMatrixOptions

        options = RGBMatrixOptions()
        options.rows = PANEL_ROWS
        options.cols = PANEL_COLUMNS
        options.chain_length = PANEL_CHAIN_LENGTH
        options.parallel = PANEL_PARALLEL
        options.hardware_mapping = "regular"
        options.row_address_type = 0
        options.brightness = BRIGHTNESS
        options.gpio_slowdown = GPIO_SLOWDOWN
        # The library drops root right after opening the panels, which would leave this program unable
        # to create its socket or remove it on exit.
        options.drop_privileges = False

        self._matrix = RGBMatrix(options=options)
        self._canvas = self._matrix.CreateFrameCanvas()

    def draw(self, items: list[Item]) -> None:
        """
        Clears the panels and draws the items in order.
        """
        from rgbmatrix import graphics

        canvas = self._canvas

        canvas.Clear()

        for item in items:
            if item["type"] == "fill":
                canvas.Fill(*item["color"])

                continue

            if item["type"] == "image":
                self._draw_image(canvas, item)

                continue

            font = self._font(item["font"])

            if font is not None:
                graphics.DrawText(canvas, font, item["x"], item["y"], graphics.Color(*item["color"]), item["text"])

        self._canvas = self._matrix.SwapOnVSync(canvas)

    def _draw_image(self, canvas, item: Item) -> None:
        """
        Draws a picture on the canvas.
        """
        from PIL import Image

        picture = Image.frombytes("RGB", (item["width"], item["height"]), base64.b64decode(item["pixels"]))

        if self._fast_images:
            try:
                canvas.SetImage(picture, item["x"], item["y"])

                return

            except Exception:
                logger.warning("Fast image drawing does not work here, drawing pixel by pixel", exc_info=True)

                self._fast_images = False

        canvas.SetImage(picture, item["x"], item["y"], unsafe=False)

    def _font(self, name: str):
        """
        The font with that name, loaded once, or None when it cannot be loaded.
        """
        if name not in self._fonts:
            from rgbmatrix import graphics

            font = graphics.Font()

            try:
                font.LoadFont(os.path.join(FONT_DIR, f"{name}.bdf"))

                self._fonts[name] = font

            except Exception:
                logger.exception("Could not load font %s", name)

                self._fonts[name] = None

        return self._fonts[name]
