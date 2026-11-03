"""
Tests for the engine, the environment, pixelate and the player.
"""

import asyncio
import unittest

from programs.main.cube import CubeEngine, CubePlayer, EngineError, ProgramError, pixelate
from programs.main.cube.state.cube_state import Face


def script(*blocks: dict) -> dict:
    """
    A program with one script that starts at once.
    """
    return {"version": 1, "scripts": [{"trigger": {"type": "start"}, "blocks": list(blocks)}]}


def create(name: str = "a", face: str = "FRONT", x: int = 0, y: int = 0, color: str = "#ffffff", **fields) -> dict:
    """
    A `create` block.
    """
    return {"op": "create", "name": name, "face": face, "x": x, "y": y, "color": color, **fields}


def solid(color: int) -> list[int]:
    """
    A picture of one color for a whole face.
    """
    return [color] * (64 * 64)


class EngineTest(unittest.TestCase):
    """
    Running programs on a clock that the test moves.
    """

    def test_blank_before_anything_runs(self) -> None:
        """
        Nothing is lit.
        """
        self.assertEqual(CubeEngine().state.get(Face.FRONT, 0, 0), 0)

    def test_runs_a_program_and_shows_the_result(self) -> None:
        """
        A created object is on the state.
        """
        engine = CubeEngine()

        engine.load(script(create(face="LEFT", x=5, y=6, color="#ff8800")))
        engine.start(0)

        self.assertEqual(engine.state.get(Face.LEFT, 5, 6), 0xFF8800)

    def test_follows_an_object_over_the_top_face(self) -> None:
        """
        Up from FRONT, over the top, onto BACK.
        """
        engine = CubeEngine()

        engine.load(script(create(x=32, y=30, color="#ff0000"), {"op": "move", "target": "a", "step": "up", "count": 31}))
        engine.start(0)
        self.assertEqual(engine.state.get(Face.TOP, 32, 63), 0xFF0000)

        engine.load(
            script(
                create(x=32, y=30, color="#ff0000"),
                {"op": "move", "target": "a", "step": "up", "count": 95},
                {"op": "move", "target": "a", "step": "right"},
            )
        )
        engine.start(0)

        # Over the top it arrives on BACK at column 31, and "right" now goes towards the left.
        self.assertEqual(engine.state.get(Face.BACK, 30, 0), 0xFF0000)

    def test_animates_over_time(self) -> None:
        """
        One step per wait.
        """
        engine = CubeEngine()

        engine.load(script(create(), {"op": "forever", "body": [{"op": "move", "target": "a", "step": "right"}, {"op": "wait", "seconds": 0.1}]}))
        engine.start(0)
        self.assertEqual(engine.state.get(Face.FRONT, 1, 0), 0xFFFFFF)

        engine.tick(50)
        self.assertEqual(engine.state.get(Face.FRONT, 2, 0), 0)

        engine.tick(100)
        self.assertEqual(engine.state.get(Face.FRONT, 1, 0), 0)
        self.assertEqual(engine.state.get(Face.FRONT, 2, 0), 0xFFFFFF)

    def test_knows_whether_it_is_running(self) -> None:
        """
        Running until the last script ends.
        """
        engine = CubeEngine()

        engine.load(script({"op": "wait", "seconds": 1}))
        self.assertFalse(engine.running)

        engine.start(0)
        self.assertTrue(engine.running)

        engine.tick(1000)
        self.assertFalse(engine.running)

    def test_starts_from_a_clean_cube_every_time(self) -> None:
        """
        Starting twice is not running twice.
        """
        engine = CubeEngine()

        engine.load(script(create(), {"op": "move", "target": "a", "step": "right", "count": 5}))
        engine.start(0)
        engine.start(100)

        self.assertEqual(engine.state.get(Face.FRONT, 5, 0), 0xFFFFFF)
        self.assertEqual(engine.state.get(Face.FRONT, 0, 0), 0)

    def test_stop_keeps_the_picture_and_reset_blanks_it(self) -> None:
        """
        The two ways to end.
        """
        engine = CubeEngine()

        engine.load(script(create(), {"op": "forever", "body": [{"op": "move", "target": "a", "step": "right"}]}))
        engine.start(0)
        engine.stop()
        engine.tick(33)

        self.assertFalse(engine.running)
        self.assertEqual(engine.state.get(Face.FRONT, 1, 0), 0xFFFFFF)

        engine.reset()

        self.assertEqual(engine.state.get(Face.FRONT, 1, 0), 0)

    def test_refuses_an_invalid_program_and_stays_as_it_was(self) -> None:
        """
        A bad load changes nothing.
        """
        engine = CubeEngine()

        engine.load(script(create(x=2, y=2)))
        engine.start(0)

        with self.assertRaises(ProgramError):
            engine.load({"version": 1, "scripts": 7})

        self.assertEqual(engine.state.get(Face.FRONT, 2, 2), 0xFFFFFF)

    def test_reports_a_script_that_fails_and_keeps_the_others_going(self) -> None:
        """
        One broken script does not stop the program.
        """
        errors = []
        engine = CubeEngine({"on_error": errors.append})

        engine.load(
            {
                "version": 1,
                "scripts": [
                    {"trigger": {"type": "start"}, "blocks": [{"op": "show", "target": "ghost"}]},
                    {"trigger": {"type": "start"}, "blocks": [create(x=1, y=1)]},
                ],
            }
        )
        engine.start(0)

        self.assertEqual([error["script"] for error in errors], [0])
        self.assertEqual(engine.state.get(Face.FRONT, 1, 1), 0xFFFFFF)


class ConfigTest(unittest.TestCase):
    """
    Settings from the program and from the engine.
    """

    ON_TOP = script(create(face="TOP", x=32, y=63))
    """
    An object at the bottom of the addressed top face.
    """

    def lit(self, engine: CubeEngine, x: int, y: int) -> bool:
        """
        Whether a pixel of the top face is on.
        """
        return engine.state.get(Face.TOP, x, y) == 0xFFFFFF

    def test_front_is_the_default_anchor(self) -> None:
        """
        As stored.
        """
        engine = CubeEngine()

        engine.load(self.ON_TOP)
        engine.start(0)

        self.assertTrue(self.lit(engine, 32, 63))

    def test_takes_the_anchor_from_the_program_or_the_defaults(self) -> None:
        """
        The program wins; defaults can change later.
        """
        engine = CubeEngine({"defaults": {"topAnchor": "LEFT"}})

        engine.load(self.ON_TOP)
        engine.start(0)
        self.assertTrue(self.lit(engine, 0, 32))

        engine.load({**self.ON_TOP, "config": {"topAnchor": "FRONT"}})
        engine.start(0)
        self.assertTrue(self.lit(engine, 32, 63))

        engine.load(self.ON_TOP)
        engine.set_defaults({"topAnchor": "BACK"})
        engine.start(0)
        self.assertTrue(self.lit(engine, 31, 0))

    def test_takes_the_floor_from_the_program(self) -> None:
        """
        A floor of 61 stops the move.
        """
        engine = CubeEngine()

        engine.load(
            {
                **script(create(y=60), {"op": "move", "target": "a", "step": "down", "count": 10}),
                "config": {"floor": 61},
            }
        )
        engine.start(0)

        self.assertEqual(engine.state.get(Face.FRONT, 0, 61), 0xFFFFFF)


class EnvironmentTest(unittest.TestCase):
    """
    The pictures on the faces that outlive programs.
    """

    def test_shows_the_pictures_at_once(self) -> None:
        """
        With nothing running.
        """
        engine = CubeEngine()

        engine.set_environment({"background": {"LEFT": solid(0x112233)}})

        self.assertEqual(engine.state.get(Face.LEFT, 10, 10), 0x112233)
        self.assertEqual(engine.state.get(Face.FRONT, 10, 10), 0)

    def test_stays_under_the_objects_and_through_resets(self) -> None:
        """
        Objects draw over it, and a reset brings it back.
        """
        engine = CubeEngine()

        engine.set_environment({"background": {"FRONT": solid(0x00FF00)}})
        engine.load(script(create(x=5, y=5, color="#ff0000")))
        engine.start(0)

        self.assertEqual(engine.state.get(Face.FRONT, 5, 5), 0xFF0000)
        self.assertEqual(engine.state.get(Face.FRONT, 6, 5), 0x00FF00)

        engine.reset()

        self.assertEqual(engine.state.get(Face.FRONT, 5, 5), 0x00FF00)

    def test_does_not_restart_a_running_program(self) -> None:
        """
        New pictures are painted under it.
        """
        engine = CubeEngine()

        engine.load(script(create(x=5, y=5, color="#ff0000"), {"op": "forever", "body": [{"op": "wait", "seconds": 1}]}))
        engine.start(0)
        engine.set_environment({"background": {"FRONT": solid(0x0000FF)}})

        self.assertTrue(engine.running)
        self.assertEqual(engine.state.get(Face.FRONT, 5, 5), 0xFF0000)
        self.assertEqual(engine.state.get(Face.FRONT, 6, 5), 0x0000FF)

    def test_blanks_a_face_when_its_picture_is_removed(self) -> None:
        """
        The other faces stay.
        """
        engine = CubeEngine()

        engine.set_environment({"background": {"FRONT": solid(1), "RIGHT": solid(2)}})
        engine.set_environment({"background": {"RIGHT": solid(2)}})

        self.assertEqual(engine.state.get(Face.FRONT, 0, 0), 0)
        self.assertEqual(engine.state.get(Face.RIGHT, 0, 0), 2)

        engine.set_environment(None)

        self.assertEqual(engine.state.get(Face.RIGHT, 0, 0), 0)

    def test_rejects_a_picture_that_is_not_the_size_of_a_face(self) -> None:
        """
        And paints nothing.
        """
        engine = CubeEngine()

        with self.assertRaises(EngineError):
            engine.set_environment({"background": {"FRONT": solid(1), "LEFT": [0] * 10}})

        self.assertEqual(engine.state.get(Face.FRONT, 0, 0), 0)


class StartingObjectsTest(unittest.TestCase):
    """
    The `objects` of a program.
    """

    PROGRAM = {
        "version": 1,
        "objects": [create(name="ball", x=10, y=10, color="#ff0000")],
        "scripts": [{"trigger": {"type": "start"}, "blocks": [{"op": "move", "target": "ball", "step": "right", "count": 2}]}],
    }
    """
    A ball that exists before the script moves it.
    """

    def test_exist_before_the_scripts_run(self) -> None:
        """
        So scripts can act on them.
        """
        engine = CubeEngine()

        engine.load(self.PROGRAM)
        engine.start(0)

        self.assertEqual(engine.state.get(Face.FRONT, 12, 10), 0xFF0000)
        self.assertEqual(engine.state.get(Face.FRONT, 10, 10), 0)

    def test_are_back_where_they_began_after_a_reset(self) -> None:
        """
        Reset undoes what the scripts did.
        """
        engine = CubeEngine()

        engine.load(self.PROGRAM)
        engine.start(0)
        engine.reset()

        self.assertEqual(engine.state.get(Face.FRONT, 10, 10), 0xFF0000)
        self.assertEqual(engine.state.get(Face.FRONT, 12, 10), 0)


class EditingTest(unittest.TestCase):
    """
    Frames, grabbing, placing, moving by hand and hiding layers.
    """

    def test_frame_is_one_rectangle_over_an_edge(self) -> None:
        """
        No outline runs along the edge between faces.
        """
        engine = CubeEngine()

        engine.load({"version": 1, "objects": [create(x=63, y=32, color="#ff8800")], "scripts": []})

        frame = engine.frame_of("a", 1)

        self.assertEqual(sorted(box["face"] for box in frame["boxes"]), [Face.FRONT, Face.RIGHT])
        self.assertEqual(len(frame["edges"]), 12)
        self.assertFalse(any(edge["face"] == Face.FRONT and edge["x"] == 63 and edge["side"] == "right" for edge in frame["edges"]))
        self.assertFalse(any(edge["face"] == Face.RIGHT and edge["x"] == 0 and edge["side"] == "left" for edge in frame["edges"]))
        self.assertEqual(engine.frame_of("ghost"), {"boxes": [], "edges": []})

    def test_moves_an_object_at_once(self) -> None:
        """
        Without loading the program again.
        """
        engine = CubeEngine()

        engine.load({"version": 1, "objects": [create(x=10, y=10, color="#ff8800")], "scripts": []})
        engine.move_object("a", "RIGHT", 5, 6)

        self.assertEqual(engine.state.get(Face.FRONT, 10, 10), 0)
        self.assertEqual(engine.state.get(Face.RIGHT, 5, 6), 0xFF8800)

    def test_grabs_the_frontmost_object_unless_one_is_preferred(self) -> None:
        """
        And says where its center is.
        """
        engine = CubeEngine()

        engine.load({"version": 1, "objects": [create(name="under", x=10, y=10), create(name="over", x=10, y=10)], "scripts": []})

        self.assertEqual(engine.grab_at(Face.FRONT, 11, 10, 1)["name"], "over")
        self.assertEqual(engine.grab_at(Face.FRONT, 10, 10, 0, "under")["name"], "under")
        self.assertEqual(engine.grab_at(Face.FRONT, 10, 10, 0)["center"], {"face": Face.FRONT, "x": 10, "y": 10})
        self.assertIsNone(engine.grab_at(Face.FRONT, 40, 40, 1))

    def test_placement_at(self) -> None:
        """
        Where a `create` must put an object to land on a pixel.
        """
        engine = CubeEngine({"defaults": {"topAnchor": "LEFT"}})

        self.assertEqual(engine.placement_at(Face.FRONT, 3, 4), {"face": "FRONT", "x": 3, "y": 4})
        self.assertEqual(engine.placement_at(Face.TOP, 0, 32), {"face": "TOP", "x": 32, "y": 63})

    def test_hidden_layers_are_not_drawn_but_keep_existing(self) -> None:
        """
        And come back when no longer hidden.
        """
        engine = CubeEngine()

        engine.load({"version": 1, "objects": [create(x=1, y=1)], "scripts": []})
        engine.set_hidden(["a", "nobody"])
        self.assertEqual(engine.state.get(Face.FRONT, 1, 1), 0)

        engine.start(0)
        self.assertEqual(engine.state.get(Face.FRONT, 1, 1), 0)

        engine.set_hidden([])
        self.assertEqual(engine.state.get(Face.FRONT, 1, 1), 0xFFFFFF)


class PixelateTest(unittest.TestCase):
    """
    Shrinking a picture to a face.
    """

    @staticmethod
    def picture(width: int, height: int, color) -> dict:
        """
        A picture whose pixel (x, y) is `color(x, y)`, as RGBA.
        """
        data = []

        for y in range(height):
            for x in range(width):
                data.extend(color(x, y))

        return {"width": width, "height": height, "data": bytes(data)}

    def test_keeps_a_picture_that_already_has_the_size_of_a_face(self) -> None:
        """
        Pixel for pixel.
        """
        pixels = pixelate(self.picture(64, 64, lambda x, y: [x * 4, y * 4, 7, 255]))

        self.assertEqual(len(pixels), 64 * 64)
        self.assertEqual(pixels[0], 0x000007)
        self.assertEqual(pixels[5 * 64 + 10], (40 << 16) | (20 << 8) | 7)

    def test_averages_the_area_each_pixel_covers(self) -> None:
        """
        Shrinking.
        """
        pixels = pixelate(self.picture(128, 128, lambda x, y: [0, 0, 0, 255] if x < 64 else [255, 255, 255, 255]))

        self.assertEqual(pixels[0], 0x000000)
        self.assertEqual(pixels[63], 0xFFFFFF)

    def test_mixes_the_colors_under_a_pixel(self) -> None:
        """
        Four pixels into one.
        """
        image = self.picture(2, 2, lambda x, y: [[0, 100, 200, 40][y * 2 + x], 0, 0, 255])

        self.assertEqual(pixelate(image, 1)[0], 85 << 16)

    def test_weights_pixels_cut_by_the_border_of_a_cell(self) -> None:
        """
        By the part that is inside.
        """
        left, right = pixelate(self.picture(3, 1, lambda x, y: [[0, 90, 180][x], 0, 0, 255]), 2)[:2]

        self.assertEqual(left, 30 << 16)
        self.assertEqual(right, 150 << 16)

    def test_stretches_a_small_picture(self) -> None:
        """
        Four corners.
        """
        pixels = pixelate(self.picture(2, 2, lambda x, y: [x * 255, y * 255, 0, 255]))

        self.assertEqual([pixels[0], pixels[63], pixels[63 * 64], pixels[-1]], [0x000000, 0xFF0000, 0x00FF00, 0xFFFF00])

    def test_transparent_parts_are_black(self) -> None:
        """
        An LED that is off.
        """
        pixels = pixelate(self.picture(64, 64, lambda x, y: [255, 255, 255, 0] if x < 32 else [255, 255, 255, 255]))

        self.assertEqual(pixels[0], 0x000000)
        self.assertEqual(pixels[63], 0xFFFFFF)

    def test_rejects_a_picture_whose_bytes_do_not_match(self) -> None:
        """
        Or one that is empty.
        """
        with self.assertRaises(EngineError):
            pixelate({"width": 4, "height": 4, "data": bytes(10)})

        with self.assertRaises(EngineError):
            pixelate({"width": 0, "height": 0, "data": b""})


class PlayerTest(unittest.IsolatedAsyncioTestCase):
    """
    The engine with a real clock.
    """

    MOVER = script(create(), {"op": "forever", "body": [{"op": "move", "target": "a", "step": "right"}, {"op": "wait", "seconds": 0.1}]})
    """
    An object that walks right ten cells a second.
    """

    async def test_runs_a_program_on_its_own_as_time_passes(self) -> None:
        """
        And tells whoever shows it about each new picture.
        """
        frames = []
        player = CubePlayer({"tick_rate": 100, "on_frame": lambda state: frames.append(state.version)})

        player.play(self.MOVER)
        self.assertEqual(player.state.get(Face.FRONT, 1, 0), 0xFFFFFF)

        await asyncio.sleep(0.35)

        x = next(x for x in range(64) if player.state.get(Face.FRONT, x, 0))

        self.assertIn(x, (3, 4, 5))
        self.assertGreaterEqual(len(frames), 4)
        self.assertEqual(frames, sorted(set(frames)))

        player.dispose()

    async def test_tells_when_it_starts_and_stops_running(self) -> None:
        """
        Once each.
        """
        changes = []
        player = CubePlayer({"tick_rate": 100, "on_running_change": changes.append})

        player.play(self.MOVER)
        player.stop()

        self.assertEqual(changes, [True, False])

        player.dispose()

    async def test_stops_its_timer_by_itself_when_the_program_is_over(self) -> None:
        """
        A finished program costs nothing.
        """
        changes = []
        player = CubePlayer({"tick_rate": 100, "on_running_change": changes.append})

        player.play(script({"op": "wait", "seconds": 0.05}))
        self.assertEqual(changes, [True])

        await asyncio.sleep(0.2)

        self.assertEqual(changes, [True, False])
        self.assertFalse(player._loop.running)

    async def test_keeps_the_picture_on_stop_and_blanks_it_on_reset(self) -> None:
        """
        And shows the blank.
        """
        shown = []
        player = CubePlayer({"tick_rate": 100, "on_frame": lambda state: shown.append(state.get(Face.FRONT, 1, 0))})

        player.play(self.MOVER)
        player.stop()
        await asyncio.sleep(0.1)

        self.assertEqual(player.state.get(Face.FRONT, 1, 0), 0xFFFFFF)

        player.reset()

        self.assertEqual(player.state.get(Face.FRONT, 1, 0), 0)
        self.assertEqual(shown[-1], 0)

    async def test_refuses_an_invalid_program_without_disturbing_the_running_one(self) -> None:
        """
        The old program keeps going.
        """
        player = CubePlayer({"tick_rate": 100})

        player.play(self.MOVER)

        with self.assertRaises(ProgramError):
            player.play({"nope": True})

        self.assertTrue(player.running)

        player.dispose()

    async def test_stops_ticking_when_disposed(self) -> None:
        """
        No timer is left.
        """
        player = CubePlayer({"tick_rate": 100})

        player.play(self.MOVER)
        player.dispose()

        self.assertFalse(player._loop.running)

    async def test_preview_shows_objects_without_running(self) -> None:
        """
        Unless something is running.
        """
        player = CubePlayer()

        player.preview([create(x=4, y=4)])
        self.assertEqual(player.state.get(Face.FRONT, 4, 4), 0xFFFFFF)
        self.assertFalse(player.running)

        player.play(self.MOVER)
        player.preview([create(name="b", x=30, y=30)])

        self.assertEqual(player.state.get(Face.FRONT, 30, 30), 0)

        player.dispose()


if __name__ == "__main__":
    unittest.main()
