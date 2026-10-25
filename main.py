#!/usr/bin/env python3
"""Display continuously rotating RGB lights on four chained LED panels."""

import math
import time

from rgbmatrix import RGBMatrix, RGBMatrixOptions


PANEL_ROWS = 64
PANEL_COLUMNS = 64
PANEL_CHAIN_LENGTH = 4
BRIGHTNESS = 5
GPIO_SLOWDOWN = 6
FRAME_RATE = 30


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


def draw_rotating_lights(canvas, angle: float) -> None:
    """Draw a rotating set of soft RGB lights over the complete chained canvas."""
    width = PANEL_COLUMNS * PANEL_CHAIN_LENGTH
    height = PANEL_ROWS
    center_x = (width - 1) / 2
    center_y = (height - 1) / 2

    for y in range(height):
        for x in range(width):
            dx = x - center_x
            dy = y - center_y
            distance = math.hypot(dx, dy)
            pixel_angle = math.atan2(dy, dx)

            red = max(0.0, math.cos(pixel_angle - angle) * 0.5 + 0.5)
            green = max(0.0, math.cos(pixel_angle - angle - 2.0 * math.pi / 3) * 0.5 + 0.5)
            blue = max(0.0, math.cos(pixel_angle - angle - 4.0 * math.pi / 3) * 0.5 + 0.5)

            glow = max(0.0, 1.0 - distance / (width * 0.55))
            pulse = 0.65 + 0.35 * math.sin(angle * 2.0 - distance * 0.08)
            brightness = glow * pulse

            canvas.SetPixel(
                x,
                y,
                int(red * brightness * 255),
                int(green * brightness * 255),
                int(blue * brightness * 255),
            )


def main() -> None:
    matrix = create_matrix()
    canvas = matrix.CreateFrameCanvas()
    angle = 0.0
    frame_delay = 1.0 / FRAME_RATE

    try:
        while True:
            frame_started = time.monotonic()
            draw_rotating_lights(canvas, angle)
            canvas = matrix.SwapOnVSync(canvas)
            angle = (angle + 0.08) % (2.0 * math.pi)

            elapsed = time.monotonic() - frame_started
            if elapsed < frame_delay:
                time.sleep(frame_delay - elapsed)
    except KeyboardInterrupt:
        pass
    finally:
        canvas.Clear()
        matrix.Clear()


if __name__ == "__main__":
    main()
