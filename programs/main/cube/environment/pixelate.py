"""
LAYER: environment (pixelate).

Turns a picture of any size into the 64x64 pixels of one face, the way the Raspberry Pi would.
`rpi-rgb-led-matrix`'s image viewer shrinks pictures with ImageMagick's `scale`, which averages the area of the
original that each pixel of the result covers (a box filter, on the colors as they are written, with no gamma
conversion). This does the same, so what the virtual cube shows is what the physical cube shows.

Transparent parts become black, because black is a LED that is off.

Plain Python, no imaging library: the caller gets the RGBA bytes from wherever it loaded the picture and passes them
in.
"""

from math import ceil, floor
from typing import Sequence, TypedDict

from programs.main.cube.errors import EngineError
from programs.main.cube.state.cube_state import FACE_RESOLUTION, Color


class RawImage(TypedDict):
    """
    A picture as raw bytes: `data` has 4 bytes (red, green, blue, alpha) per pixel, row after row.
    """

    width: int
    """
    Width in pixels.
    """

    height: int
    """
    Height in pixels.
    """

    data: Sequence[int]
    """
    The bytes: red, green, blue and alpha for each pixel.
    """


def pixelate(image: RawImage, size: int = FACE_RESOLUTION) -> list[Color]:
    """
    Shrinks (or stretches) a picture to `size` x `size` pixels. Crop it to a square first, or it is squashed.
    Returns `size * size` colors, row after row, ready to paint on a face.
    """
    width, height, data = image["width"], image["height"], image["data"]

    if width <= 0 or height <= 0 or len(data) != width * height * 4:
        raise EngineError("The picture is empty or its bytes do not match its size")

    cell_width = width / size
    cell_height = height / size

    return [
        average(image, x * cell_width, y * cell_height, cell_width, cell_height)
        for y in range(size)
        for x in range(size)
    ]


def average(image: RawImage, left: float, top: float, cell_width: float, cell_height: float) -> Color:
    """
    Average color of the rectangle of the picture that starts at (left, top) and is `cell_width` x `cell_height`
    big. Pixels cut by the border of the rectangle count for the part that is inside, which is what keeps the result
    smooth when the sizes do not divide.
    """
    width, height, data = image["width"], image["height"], image["data"]
    right = left + cell_width
    bottom = top + cell_height
    red = green = blue = area = 0.0

    for y in range(floor(top), min(ceil(bottom), height)):
        row_weight = min(y + 1, bottom) - max(y, top)

        for x in range(floor(left), min(ceil(right), width)):
            weight = row_weight * (min(x + 1, right) - max(x, left))
            index = (y * width + x) * 4

            # A transparent pixel adds black: its color counts for as much as it is opaque.
            opacity = data[index + 3] / 255

            red += data[index] * opacity * weight
            green += data[index + 1] * opacity * weight
            blue += data[index + 2] * opacity * weight
            area += weight

    return (round_half_up(red / area) << 16) | (round_half_up(green / area) << 8) | round_half_up(blue / area)


def round_half_up(value: float) -> int:
    """
    Rounds like a browser does (halves go up), not to the even number like Python's `round`.
    """
    return floor(value + 0.5)
