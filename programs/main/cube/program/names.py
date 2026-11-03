"""
LAYER: program format (names).

Converts the readable names used in programs ('FRONT', 'NORTH', '#ff8800') into the values the engine works with
(Face, Heading, 0xRRGGBB), and back. It is the only place that knows both vocabularies.
"""

import re

from programs.main.cube.geometry.geometry import Heading
from programs.main.cube.program.program import ColorValue
from programs.main.cube.state.cube_state import Color, Face


FACE_BY_NAME: dict[str, Face] = {
    "FRONT": Face.FRONT,
    "RIGHT": Face.RIGHT,
    "BACK": Face.BACK,
    "LEFT": Face.LEFT,
    "TOP": Face.TOP,
}
"""
Face for each face name.
"""

FACE_NAME: dict[Face, str] = {
    Face.FRONT: "FRONT",
    Face.RIGHT: "RIGHT",
    Face.LEFT: "LEFT",
    Face.BACK: "BACK",
    Face.TOP: "TOP",
}
"""
Name of each face.
"""

HEADING_BY_NAME: dict[str, Heading] = {
    "NORTH": Heading.NORTH,
    "EAST": Heading.EAST,
    "SOUTH": Heading.SOUTH,
    "WEST": Heading.WEST,
}
"""
Heading for each heading name.
"""

COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{6}")
"""
Matches a color written as `#RRGGBB`.
"""


def is_color_value(value: object) -> bool:
    """
    Tells whether a value is a color written as `#RRGGBB`.
    """
    return isinstance(value, str) and COLOR_PATTERN.fullmatch(value) is not None


def parse_color(value: ColorValue) -> Color:
    """
    Converts `#RRGGBB` to the packed number the pixel buffer uses.
    """
    return int(value[1:], 16)


def format_color(color: Color) -> ColorValue:
    """
    Converts a packed color back to `#RRGGBB`.
    """
    return f"#{color:06x}"
