"""
LAYER: drawing primitives.

Single pixel and whole-cube operations (clear, set, get).

These write straight into a CubeState face. They do not know about objects or programs. No program block exposes
them.
"""

from programs.main.cube.state.cube_state import Color, CubeState


def clear(state: CubeState, color: Color = 0x000000) -> None:
    """
    Sets the whole cube to one color.
    """
    state.fill(color)


def set_pixel(state: CubeState, face: int, x: int, y: int, color: Color) -> None:
    """
    Changes one pixel of a face.
    """
    state.set(face, x, y, color)


def get_pixel(state: CubeState, face: int, x: int, y: int) -> Color:
    """
    Returns the current color of a pixel of a face.
    """
    return state.get(face, x, y)
