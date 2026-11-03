"""
LAYER: drawing primitives.

Copies a small picture (a list of colors) onto a face.

These write straight into a CubeState face. They do not know about objects or programs: `draw_bitmap` paints the
pictures of the faces onto the background layer (the environment and the background blocks use it).
"""

from typing import Sequence

from programs.main.cube.state.cube_state import Color, CubeState


def draw_bitmap(state: CubeState, face: int, x: int, y: int, width: int, height: int, pixels: Sequence[Color]) -> None:
    """
    Copies a bitmap onto a face with its top-left corner at (x, y). `pixels` holds width * height colors, row after
    row.
    """
    for row in range(height):
        for column in range(width):
            state.set(face, x + column, y + row, pixels[row * width + column])
