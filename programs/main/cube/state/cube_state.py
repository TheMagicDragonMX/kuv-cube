"""
LAYER: pixel buffer.

The lowest layer of the cube: just a grid of colors, one 64x64 surface per face. It is the meeting point between
the engine and whatever shows the result:

    engine (renderer) --writes--> CubeState --is read by--> the LED panels (view/)

It knows nothing about objects, programs, panels or GPIO.
"""

from array import array
from enum import IntEnum
from typing import TypeAlias


class Face(IntEnum):
    """
    Faces of the cube. The numeric values are the order in which the renderer builds its faces, so they double as
    indexes into the pixel buffer.
    """

    FRONT = 0
    """
    The face in front of the viewer.
    """

    RIGHT = 1
    """
    The face on the right.
    """

    LEFT = 2
    """
    The face on the left.
    """

    BACK = 3
    """
    The face behind.
    """

    TOP = 4
    """
    The face on top.
    """


FACE_COUNT = 5
"""
Number of faces in the cube.
"""

FACE_RESOLUTION = 64
"""
Pixels per side on every face.
"""

Color: TypeAlias = int
"""
A color packed as 0xRRGGBB. Black (0x000000) means the LED is off.
"""

def scale_color(color: Color, level: float) -> Color:
    """
    The color dimmed to a share of its intensity: 1 leaves it as it is, 0 turns it off. Each of the three channels is
    scaled, so the hue stays.
    """
    if level >= 1:
        return color

    red = int(((color >> 16) & 0xFF) * level + 0.5)
    green = int(((color >> 8) & 0xFF) * level + 0.5)
    blue = int((color & 0xFF) * level + 0.5)

    return (red << 16) | (green << 8) | blue


PIXEL_TYPE_CODE = "I"
"""
Type code of the array that holds the pixels: unsigned 32-bit integers.
"""

assert array(PIXEL_TYPE_CODE).itemsize == 4, "The pixel buffer needs 32-bit unsigned integers"


class CubeState:
    """
    Hardware-independent pixel buffer of the cube: one 64x64 surface per face. Commands write into it and the
    view reads from it. It knows nothing about panels or GPIO.

    Coordinates are per face: x grows to the right and y grows downward as seen from outside the cube, with (0, 0)
    at the top-left corner.
    """

    def __init__(self) -> None:
        """
        Starts with every LED off.
        """
        self._pixels = array(PIXEL_TYPE_CODE, [0]) * (FACE_COUNT * FACE_RESOLUTION * FACE_RESOLUTION)
        """
        Pixel colors of all faces, stored face after face and row after row.
        """

        self.version = 0
        """
        Increases on every write so readers can tell cheaply whether they need to redraw.
        """

    def in_bounds(self, face: int, x: int, y: int) -> bool:
        """
        Tells whether a face/x/y triple points at a real pixel.
        """
        return 0 <= face < FACE_COUNT and 0 <= x < FACE_RESOLUTION and 0 <= y < FACE_RESOLUTION

    def set(self, face: int, x: int, y: int, color: Color) -> None:
        """
        Sets one pixel. Writes outside the face are ignored, so shapes can safely overflow.
        """
        if not self.in_bounds(face, x, y):
            return

        self._pixels[self._index_of(face, x, y)] = color
        self.version += 1

    def get(self, face: int, x: int, y: int) -> Color:
        """
        Returns the color of one pixel, or black if the coordinates are outside the face.
        """
        if not self.in_bounds(face, x, y):
            return 0

        return self._pixels[self._index_of(face, x, y)]

    def fill(self, color: Color) -> None:
        """
        Sets every pixel of every face to one color.
        """
        self._pixels[:] = array(PIXEL_TYPE_CODE, [color]) * len(self._pixels)
        self.version += 1

    def copy_from(self, other: "CubeState") -> None:
        """
        Copies every pixel of another state into this one. This is a single bulk copy, so it is the cheap way to
        start a frame from a saved image (the renderer does it with the background).
        """
        self._pixels[:] = other._pixels
        self.version += 1

    def dim_face(self, face: int, level: float) -> None:
        """
        Dims every pixel of one face to a share of its intensity (see `scale_color`).
        """
        if level >= 1:
            return

        # Every byte of a pixel is one channel (the fourth one is always 0), so one table that scales a byte does the
        # whole face in a single pass, without a Python loop over its pixels.
        table = bytes(int(value * level + 0.5) for value in range(256))
        size = FACE_RESOLUTION * FACE_RESOLUTION
        start, end = face * size * 4, (face + 1) * size * 4
        raw = memoryview(self._pixels).cast("B")

        raw[start:end] = raw[start:end].tobytes().translate(table)
        self.version += 1

    def face_pixels(self, face: int) -> memoryview:
        """
        The pixels of one face, row after row (index `y * FACE_RESOLUTION + x`), as a view into the buffer, not a
        copy. It is meant for readers that copy a whole face at once, so they skip the bounds check `get` does for
        every pixel. Only read it: writing through it would not bump `version`, so nobody would redraw.
        """
        size = FACE_RESOLUTION * FACE_RESOLUTION

        return memoryview(self._pixels)[face * size : (face + 1) * size]

    def _index_of(self, face: int, x: int, y: int) -> int:
        """
        Position of a pixel inside the flat buffer.
        """
        return (face * FACE_RESOLUTION + y) * FACE_RESOLUTION + x
