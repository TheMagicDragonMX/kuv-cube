"""
Tests for how the cube reaches the panels: the panel layout, the image item of the matrix protocol and the whole
way from a program to the screen.
"""

import asyncio
import base64
import os
import tempfile
import unittest
from unittest import mock

from programs.common.matrix_client import MatrixClient
from programs.common.matrix_protocol import MAIN_PRIORITY, MAX_ITEMS, clean_item, clean_scene, decode_image, image
from programs.main.cube import CubePlayer
from programs.main.cube.state.cube_state import CubeState, Face
from programs.main.cube.view import panel_layout
from programs.main.cube.view.panel_layout import PANEL_SLOTS, rotate, scene_of
from programs.matrix.server import MatrixServer
from tests.test_matrix import RecordingScreen


def pixel_of(item: dict, x: int, y: int) -> tuple[int, int, int]:
    """
    The color of a pixel of an image item, relative to the image.
    """
    rgb = decode_image(item)
    start = (y * item["width"] + x) * 3

    return rgb[start], rgb[start + 1], rgb[start + 2]


class ImageItemTest(unittest.TestCase):
    """
    The image item of the matrix protocol.
    """

    def test_round_trips(self) -> None:
        """
        What is sent is what is received.
        """
        item = image(64, 128, 2, 1, bytes([1, 2, 3, 4, 5, 6]))

        self.assertEqual(clean_item(item), item)
        self.assertEqual(decode_image(item), bytes([1, 2, 3, 4, 5, 6]))

    def test_rejects_malformed_images(self) -> None:
        """
        Wrong sizes, wrong types and wrong base64 change nothing.
        """
        good = image(0, 0, 2, 1, bytes(6))
        bad = [
            {**good, "width": 3},
            {**good, "width": 0},
            {**good, "width": 100000},
            {**good, "x": "0"},
            {**good, "x": True},
            {**good, "pixels": "not base64!"},
            {**good, "pixels": base64.b64encode(bytes(5)).decode()},
            {**good, "pixels": 5},
        ]

        for item in bad:
            self.assertIsNone(clean_item(item), item)

    def test_a_scene_of_five_faces_fits_the_limits(self) -> None:
        """
        The whole cube in one line is under the size the server accepts.
        """
        from programs.matrix.server import MAX_LINE_SIZE

        scene = [image(0, row * 64, 64, 64, bytes(64 * 64 * 3)) for row in range(5)]

        self.assertLessEqual(len(scene), MAX_ITEMS)
        self.assertEqual(clean_scene(scene), scene)
        self.assertLess(sum(len(item["pixels"]) for item in scene) + 1000, MAX_LINE_SIZE)


class PanelLayoutTest(unittest.TestCase):
    """
    Where each face goes.
    """

    def test_a_blank_cube_has_an_empty_scene(self) -> None:
        """
        Nothing lit, nothing to send.
        """
        self.assertEqual(scene_of(CubeState()), [])

    def test_a_face_goes_to_its_slot(self) -> None:
        """
        The picture of a face is placed on the canvas by the table.
        """
        state = CubeState()

        state.set(Face.BACK, 3, 2, 0x112233)

        scene = scene_of(state)
        slot = PANEL_SLOTS[Face.BACK]

        self.assertEqual(len(scene), 1)
        self.assertEqual((scene[0]["x"], scene[0]["y"]), (slot["column"] * 64, slot["row"] * 64))
        self.assertEqual((scene[0]["width"], scene[0]["height"]), (64, 64))
        self.assertEqual(pixel_of(scene[0], 3, 2), (0x11, 0x22, 0x33))
        self.assertEqual(pixel_of(scene[0], 2, 3), (0, 0, 0))
        self.assertIsNotNone(clean_item(scene[0]))

    def test_every_face_has_a_distinct_slot_inside_the_canvas(self) -> None:
        """
        No two faces share a panel, and all are in the 2x3 grid of the matrix program.
        """
        slots = [(slot["column"], slot["row"]) for slot in PANEL_SLOTS.values()]

        self.assertEqual(len(slots), len(set(slots)))
        self.assertEqual(set(PANEL_SLOTS), set(Face))
        self.assertTrue(all(0 <= column < 2 and 0 <= row < 3 for column, row in slots))

    def test_rotates_a_face_clockwise(self) -> None:
        """
        A quarter turn moves the top-left corner to the top-right.
        """
        pixels = [0] * (64 * 64)

        pixels[0] = 1

        self.assertEqual(rotate(pixels, 1)[63], 1)
        self.assertEqual(rotate(pixels, 2)[64 * 64 - 1], 1)
        self.assertEqual(rotate(pixels, 3)[63 * 64], 1)
        self.assertEqual(rotate(pixels, 4), pixels)

    def test_a_rotated_slot_draws_the_rotated_face(self) -> None:
        """
        The table's `turns` reaches the picture.
        """
        state = CubeState()

        state.set(Face.FRONT, 0, 0, 0xFF0000)

        slots = {**PANEL_SLOTS, Face.FRONT: {**PANEL_SLOTS[Face.FRONT], "turns": 1}}

        with mock.patch.object(panel_layout, "PANEL_SLOTS", slots):
            scene = scene_of(state)

        self.assertEqual(pixel_of(scene[0], 63, 0), (255, 0, 0))
        self.assertEqual(pixel_of(scene[0], 0, 0), (0, 0, 0))

    def test_an_unchanged_face_is_converted_once(self) -> None:
        """
        Faces are remembered by their pixels.
        """
        state = CubeState()

        state.set(Face.FRONT, 1, 1, 5)
        panel_layout.picture_of.cache_clear()

        first = scene_of(state)
        second = scene_of(state)

        self.assertIs(first[0], second[0])
        self.assertEqual(panel_layout.picture_of.cache_info().hits, 5)


class EndToEndTest(unittest.IsolatedAsyncioTestCase):
    """
    A program, the player, the matrix client and the matrix server, with a screen that records.
    """

    async def test_a_program_reaches_the_screen(self) -> None:
        """
        What the cube shows is what the screen is asked to draw, and it moves.
        """
        with tempfile.TemporaryDirectory() as directory:
            screen = RecordingScreen()
            server = MatrixServer(screen, os.path.join(directory, "matrix.sock"))
            client = MatrixClient("main", MAIN_PRIORITY, os.path.join(directory, "matrix.sock"))
            player = CubePlayer({"tick_rate": 50, "on_frame": lambda state: client.show(scene_of(state))})

            await server.start()

            client.start()

            player.play(
                {
                    "version": 1,
                    "objects": [{"op": "create", "name": "a", "face": "FRONT", "x": 0, "y": 5, "color": "#ff0000"}],
                    "scripts": [
                        {
                            "trigger": {"type": "start"},
                            "blocks": [
                                {"op": "setBackgroundColor", "faces": ["TOP"], "color": "#000044"},
                                {"op": "forever", "body": [{"op": "move", "target": "a", "step": "right"}, {"op": "wait", "seconds": 0.1}]},
                            ],
                        }
                    ],
                }
            )

            await asyncio.sleep(0.5)

            player.dispose()

            front = next(item for item in screen.current if item["x"] == 0 and item["y"] == 0)
            top = next(item for item in screen.current if item["y"] == 128)
            x = next(x for x in range(64) if pixel_of(front, x, 5) == (255, 0, 0))

            self.assertGreaterEqual(x, 3)
            self.assertEqual(pixel_of(top, 10, 10), (0, 0, 0x44))
            self.assertGreater(len(screen.drawn), 3)

            await client.close()
            await server.stop()


if __name__ == "__main__":
    unittest.main()
