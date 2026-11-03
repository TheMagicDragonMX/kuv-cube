"""
What programs and the matrix program say to each other.

Only programs/matrix touches the LED panels. Everything else sends it a "scene" (a list of things to
draw) over a local socket, as one JSON object per line:

    {"op": "hello", "name": "setup", "priority": 10}
    {"op": "show", "items": [{"type": "fill", "color": [0, 0, 255]}]}

Each program has one scene; the matrix shows the scene of the program with the highest priority
that has something to draw. A program that disconnects takes its scene with it.
"""

import re
from typing import Any, Literal, TypeAlias, TypedDict


SOCKET_PATH = "/run/kuv/matrix.sock"
"""
Where the matrix program listens.
"""

MAIN_PRIORITY = 0
"""
Priority of the main program: it draws underneath everything else.
"""

SETUP_PRIORITY = 10
"""
Priority of the setup program: the PIN is drawn over whatever main shows.
"""

MAX_ITEMS = 32
"""
Most items a scene may have.
"""

MAX_TEXT_LENGTH = 64
"""
Most characters a text item may have.
"""

DEFAULT_FONT = "10x20"
"""
Font used when a text item does not name one.
"""

FONT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
"""
Font names are letters, digits and underscores, so they can never point outside the fonts folder.
"""

Color: TypeAlias = list[int]
"""
Red, green and blue, 0 to 255 each.
"""


class FillItem(TypedDict):
    """
    Paints every LED one color.
    """

    type: Literal["fill"]
    """
    Always "fill".
    """

    color: Color
    """
    The color.
    """


class TextItem(TypedDict):
    """
    Writes text.
    """

    type: Literal["text"]
    """
    Always "text".
    """

    text: str
    """
    What to write.
    """

    x: int
    """
    Pixel column of the left edge.
    """

    y: int
    """
    Pixel row of the baseline.
    """

    color: Color
    """
    The color.
    """

    font: str
    """
    Font name, e.g. "10x20".
    """


Item: TypeAlias = FillItem | TextItem
"""
One thing to draw.
"""


def fill(red: int, green: int, blue: int) -> FillItem:
    """
    An item that paints every LED one color.
    """
    return {"type": "fill", "color": [red, green, blue]}


def text(content: str, x: int, y: int, color: Color = (255, 255, 255), font: str = DEFAULT_FONT) -> TextItem:
    """
    An item that writes `content` with its baseline at row `y`, starting at column `x`.
    """
    return {"type": "text", "text": content, "x": x, "y": y, "color": list(color), "font": font}


def is_color(value: Any) -> bool:
    """
    True when the value is three integers from 0 to 255.
    """
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(channel, int) and not isinstance(channel, bool) and 0 <= channel <= 255 for channel in value)
    )


def clean_item(value: Any) -> Item | None:
    """
    The item if it is well formed, otherwise None.
    """
    if not isinstance(value, dict) or not is_color(value.get("color")):
        return None

    if value.get("type") == "fill":
        return {"type": "fill", "color": value["color"]}

    if value.get("type") != "text":
        return None

    content, x, y = value.get("text"), value.get("x"), value.get("y")
    font = value.get("font", DEFAULT_FONT)

    if not isinstance(content, str) or len(content) > MAX_TEXT_LENGTH:
        return None

    if not all(isinstance(number, int) and not isinstance(number, bool) for number in (x, y)):
        return None

    if not isinstance(font, str) or not FONT_NAME_PATTERN.match(font):
        return None

    return {"type": "text", "text": content, "x": x, "y": y, "color": value["color"], "font": font}


def clean_scene(value: Any) -> list[Item] | None:
    """
    The scene if every item in it is well formed, otherwise None.
    """
    if not isinstance(value, list) or len(value) > MAX_ITEMS:
        return None

    items = [clean_item(item) for item in value]

    if any(item is None for item in items):
        return None

    return items
