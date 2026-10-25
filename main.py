#!/usr/bin/env python3
"""Turn all chained LED panels red. Run with sudo."""

import time

from rgbmatrix import RGBMatrix, RGBMatrixOptions


PANEL_ROWS = 64
PANEL_COLUMNS = 64
PANEL_CHAIN_LENGTH = 4
BRIGHTNESS = 15
GPIO_SLOWDOWN = 6


def create_matrix() -> RGBMatrix:
    """Create a matrix matching the settings used by the demo executable."""
    options = RGBMatrixOptions()
    options.rows = PANEL_ROWS
    options.cols = PANEL_COLUMNS
    options.chain_length = PANEL_CHAIN_LENGTH
    options.parallel = 1
    options.hardware_mapping = "regular"
    options.row_address_type = 0
    options.brightness = BRIGHTNESS
    options.gpio_slowdown = GPIO_SLOWDOWN

    return RGBMatrix(options=options)


def main() -> None:
    matrix = create_matrix()
    matrix.Fill(255, 0, 0)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        matrix.Clear()


if __name__ == "__main__":
    main()
