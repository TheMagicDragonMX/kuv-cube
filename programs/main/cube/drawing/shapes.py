"""
LAYER: drawing primitives.

Lines, rectangles and circles (outline and filled), drawn on one face. Anything outside the face is clipped by
CubeState, so shapes can safely overflow.

These write straight into a CubeState face. They do not know about objects or programs: `fill_rect` paints faces for
the background blocks. No block exposes the rest of the drawing (there is no line or circle block).
"""

from math import isqrt

from programs.main.cube.state.cube_state import Color, CubeState


def draw_line(state: CubeState, face: int, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
    """
    Draws a straight line between two points (Bresenham).
    """
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    step_x = 1 if x0 < x1 else -1
    step_y = 1 if y0 < y1 else -1
    error = dx + dy
    x, y = x0, y0

    while True:
        state.set(face, x, y, color)

        if x == x1 and y == y1:
            return

        doubled = 2 * error

        if doubled >= dy:
            error += dy
            x += step_x

        if doubled <= dx:
            error += dx
            y += step_y


def draw_rect(state: CubeState, face: int, x: int, y: int, width: int, height: int, color: Color) -> None:
    """
    Draws the outline of a rectangle whose top-left corner is (x, y).
    """
    if width <= 0 or height <= 0:
        return

    draw_line(state, face, x, y, x + width - 1, y, color)
    draw_line(state, face, x, y + height - 1, x + width - 1, y + height - 1, color)
    draw_line(state, face, x, y, x, y + height - 1, color)
    draw_line(state, face, x + width - 1, y, x + width - 1, y + height - 1, color)


def fill_rect(state: CubeState, face: int, x: int, y: int, width: int, height: int, color: Color) -> None:
    """
    Fills a rectangle whose top-left corner is (x, y).
    """
    for row in range(y, y + height):
        for column in range(x, x + width):
            state.set(face, column, row, color)


def draw_circle(state: CubeState, face: int, cx: int, cy: int, radius: int, color: Color) -> None:
    """
    Draws the outline of a circle (midpoint algorithm).
    """
    if radius < 0:
        return

    x, y = radius, 0
    error = 1 - radius

    while x >= y:
        state.set(face, cx + x, cy + y, color)
        state.set(face, cx - x, cy + y, color)
        state.set(face, cx + x, cy - y, color)
        state.set(face, cx - x, cy - y, color)
        state.set(face, cx + y, cy + x, color)
        state.set(face, cx - y, cy + x, color)
        state.set(face, cx + y, cy - x, color)
        state.set(face, cx - y, cy - x, color)

        y += 1

        if error < 0:
            error += 2 * y + 1

        else:
            x -= 1
            error += 2 * (y - x) + 1


def fill_circle(state: CubeState, face: int, cx: int, cy: int, radius: int, color: Color) -> None:
    """
    Fills a circle.
    """
    for y in range(-radius, radius + 1):
        half = isqrt(radius * radius - y * y)

        for x in range(-half, half + 1):
            state.set(face, cx + x, cy + y, color)
