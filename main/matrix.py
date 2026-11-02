"""
The LED matrix: how the panels are wired and how to open them.

Shared with the setup service, which uses the matrix to show the PIN while the cube is offline.
"""

from rgbmatrix import RGBMatrix, RGBMatrixOptions


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

PANEL_PARALLEL = 3
"""
Chains driven in parallel.
"""

BRIGHTNESS = 15
"""
Brightness percentage, kept low to stay within the power supply and thermal limits.
"""

GPIO_SLOWDOWN = 6
"""
Slows the GPIO down so the panels keep up with the Pi 4.
"""


def create_matrix() -> RGBMatrix:
    """
    Creates a matrix matching the settings used by the demo executable.
    """
    options = RGBMatrixOptions()
    options.rows = PANEL_ROWS
    options.cols = PANEL_COLUMNS
    options.chain_length = PANEL_CHAIN_LENGTH
    options.parallel = PANEL_PARALLEL
    options.hardware_mapping = "regular"
    options.row_address_type = 0
    options.brightness = BRIGHTNESS
    options.gpio_slowdown = GPIO_SLOWDOWN

    return RGBMatrix(options=options)
