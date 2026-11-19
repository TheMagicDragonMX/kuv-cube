"""
Panel check: `python -m programs.panels`.

Writes on every panel the name of the face the cube shows there, where that panel is wired (output of the bonnet and
place in its chain, 1 being the one closest to the Pi) and a red bar along the top edge of the picture. Seen on the
cube, it tells whether `PANEL_SLOTS` in `programs/main/cube/view/panel_layout.py` sends each face to the right panel
and the right way up. It draws through the matrix program, over main, until it is stopped.
"""

import asyncio
import signal

from programs.common.matrix_client import MatrixClient
from programs.common.matrix_protocol import Color, Item, image, text
from programs.main.cube.state.cube_state import FACE_RESOLUTION, Face
from programs.main.cube.view.panel_layout import PANEL_SLOTS, rotate, to_rgb
from programs.matrix.screen import PANEL_CHAIN_LENGTH


PRIORITY = 20
"""
Priority of the check: drawn over main and setup.
"""

NAME_FONT = "10x20"
"""
Font of the face name.
"""

PLACE_FONT = "6x10"
"""
Font of the line that says where the panel is wired.
"""

TEXT_LEFT = 4
"""
Pixels between the left edge of a panel and the text.
"""

NAME_BASELINE = 34
"""
Pixel row of the baseline of the face name, inside the panel.
"""

PLACE_BASELINE = 52
"""
Pixel row of the baseline of the wiring line, inside the panel.
"""

BAR_HEIGHT = 3
"""
Rows of the red bar that marks the top edge of the picture.
"""

COLORS: dict[Face, Color] = {
    Face.FRONT: (255, 255, 255),
    Face.RIGHT: (255, 255, 0),
    Face.BACK: (0, 255, 255),
    Face.LEFT: (255, 0, 255),
    Face.TOP: (0, 255, 0),
}
"""
Color of each face's name, so the panels are easy to tell apart.
"""


def top_bar(turns: int) -> bytes:
    """
    The pixels of a whole panel with only the red bar on its top edge, turned like the face it marks.
    """
    red = 0xFF0000
    pixels = [red if y < BAR_HEIGHT else 0 for y in range(FACE_RESOLUTION) for _ in range(FACE_RESOLUTION)]

    return to_rgb(rotate(pixels, turns))


def labels() -> list[Item]:
    """
    The scene: for every face, its top bar, its name and where its panel is wired.
    """
    items: list[Item] = []

    for face, slot in PANEL_SLOTS.items():
        left = slot["column"] * FACE_RESOLUTION
        top = slot["row"] * FACE_RESOLUTION
        place = f"P{slot['row'] + 1} #{PANEL_CHAIN_LENGTH - slot['column']}"

        items.append(image(left, top, FACE_RESOLUTION, FACE_RESOLUTION, top_bar(slot["turns"])))
        items.append(text(face.name, left + TEXT_LEFT, top + NAME_BASELINE, COLORS[face], NAME_FONT))
        items.append(text(place, left + TEXT_LEFT, top + PLACE_BASELINE, COLORS[face], PLACE_FONT))

    return items


async def run() -> None:
    """
    Shows the labels until the program is stopped.
    """
    matrix = MatrixClient("panels", PRIORITY)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    for signal_number in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_number, stop.set)

    matrix.start()
    matrix.show(labels())

    await stop.wait()
    await matrix.close()


if __name__ == "__main__":
    asyncio.run(run())
