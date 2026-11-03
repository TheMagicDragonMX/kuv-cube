"""
LAYER: view (panel layout).

Turns the cube state into what the LED panels show. This is the only place that knows where each face sits on the
canvas of the panels, and the only one that knows the cube is shown through the matrix program.

    CubeState --read by--> panel layout --scene (one image per face)--> MatrixClient --> matrix program

The canvas is a grid of 64x64 slots (`column`, `row`), one per panel. Each face has a slot, and a number of quarter
turns for panels that are mounted rotated.

Faces that are all black are left out of the scene: the matrix program clears the canvas before drawing, so they
cost nothing to send.
"""

from array import array
from functools import lru_cache
from typing import TypedDict

from programs.common.matrix_protocol import ImageItem, Item, image
from programs.main.cube.state.cube_state import FACE_COUNT, FACE_RESOLUTION, PIXEL_TYPE_CODE, CubeState, Face


class PanelSlot(TypedDict):
    """
    Where the picture of a face goes on the canvas of the panels.
    """

    column: int
    """
    Slot column, counted from the left (the panels chained on one output).
    """

    row: int
    """
    Slot row, counted from the top (the outputs run in parallel).
    """

    turns: int
    """
    Quarter turns clockwise the picture is rotated by before it is drawn, for a panel that is mounted rotated.
    """


PANEL_SLOTS: dict[Face, PanelSlot] = {
    Face.FRONT: {"column": 0, "row": 0, "turns": 0},
    Face.RIGHT: {"column": 1, "row": 0, "turns": 0},
    Face.BACK: {"column": 0, "row": 1, "turns": 0},
    Face.LEFT: {"column": 1, "row": 1, "turns": 0},
    Face.TOP: {"column": 0, "row": 2, "turns": 0},
}
"""
The slot of each face. This is a placeholder: change it to how the panels are really wired and mounted.
"""

def rotate(pixels: list[int], turns: int) -> list[int]:
    """
    The pixels of a face (row after row) rotated by quarter turns clockwise.
    """
    for _ in range(turns % 4):
        pixels = [pixels[(FACE_RESOLUTION - 1 - x) * FACE_RESOLUTION + y] for y in range(FACE_RESOLUTION) for x in range(FACE_RESOLUTION)]

    return pixels


def to_rgb(pixels: list[int]) -> bytes:
    """
    The pixels packed as 0xRRGGBB as three bytes each (red, green, blue).
    """
    rgb = bytearray(len(pixels) * 3)

    rgb[0::3] = bytes((pixel >> 16) & 255 for pixel in pixels)
    rgb[1::3] = bytes((pixel >> 8) & 255 for pixel in pixels)
    rgb[2::3] = bytes(pixel & 255 for pixel in pixels)

    return bytes(rgb)


@lru_cache(maxsize=2 * FACE_COUNT)
def picture_of(raw: bytes, column: int, row: int, turns: int) -> ImageItem | None:
    """
    The picture of a face (its pixels as the bytes of the state) placed on a slot, or None when every LED of the
    face is off. Remembered, so a face that did not change since the last frame costs nothing to convert.
    """
    pixels = array(PIXEL_TYPE_CODE)

    pixels.frombytes(raw)

    if not any(pixels):
        return None

    return image(
        column * FACE_RESOLUTION,
        row * FACE_RESOLUTION,
        FACE_RESOLUTION,
        FACE_RESOLUTION,
        to_rgb(rotate(pixels.tolist(), turns)),
    )


def face_image(state: CubeState, face: Face) -> ImageItem | None:
    """
    The picture of one face placed on its slot, or None when every LED of the face is off.
    """
    slot = PANEL_SLOTS[face]

    return picture_of(state.face_pixels(face).tobytes(), slot["column"], slot["row"], slot["turns"])


def scene_of(state: CubeState) -> list[Item]:
    """
    What the panels must show for a state of the cube: one image per face that has anything lit.
    """
    items = [face_image(state, Face(face)) for face in range(FACE_COUNT)]

    return [item for item in items if item is not None]
