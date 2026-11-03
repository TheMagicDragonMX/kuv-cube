"""
Tests for the state, the world, the commands and the renderer of the cube.
"""

import unittest

from programs.main.cube.blocks import COMMAND_BLOCKS, CONTROL_BLOCKS
from programs.main.cube.blocks.control import CONTROL_BLOCKS as CONTROL_TABLE
from programs.main.cube.commands.apply_command import apply_command, is_command
from programs.main.cube.drawing.shapes import fill_circle, fill_rect
from programs.main.cube.errors import EngineError
from programs.main.cube.geometry.geometry import Heading
from programs.main.cube.renderer.renderer import Renderer
from programs.main.cube.state.cube_state import FACE_RESOLUTION, CubeState, Face
from programs.main.cube.world.world import World


def ball_world(config: dict | None = None) -> World:
    """
    A world with a red ball in the middle of FRONT.
    """
    world = World(config)

    apply_command(world, {"op": "create", "name": "ball", "face": "FRONT", "x": 32, "y": 32, "color": "#ff0000"})

    return world


class CubeStateTest(unittest.TestCase):
    """
    The pixel buffer.
    """

    def test_reads_back_what_was_written(self) -> None:
        """
        Pixels are per face, and writes outside a face are ignored.
        """
        state = CubeState()

        state.set(Face.LEFT, 3, 4, 0x123456)
        state.set(Face.LEFT, 64, 0, 0xFFFFFF)
        state.set(Face.LEFT, -1, 0, 0xFFFFFF)

        self.assertEqual(state.get(Face.LEFT, 3, 4), 0x123456)
        self.assertEqual(state.get(Face.FRONT, 3, 4), 0)
        self.assertEqual(state.get(Face.LEFT, 64, 0), 0)

    def test_version_goes_up_on_writes(self) -> None:
        """
        Every write bumps the version.
        """
        state = CubeState()
        version = state.version

        state.set(Face.FRONT, 0, 0, 1)
        state.fill(2)

        self.assertGreater(state.version, version + 1)

    def test_copies_from_another_state(self) -> None:
        """
        A bulk copy brings every pixel.
        """
        source, target = CubeState(), CubeState()

        source.set(Face.TOP, 63, 63, 7)
        target.copy_from(source)

        self.assertEqual(target.get(Face.TOP, 63, 63), 7)

    def test_face_pixels_is_a_view_of_one_face(self) -> None:
        """
        The pixels of a face come row after row.
        """
        state = CubeState()

        state.set(Face.RIGHT, 5, 2, 9)

        pixels = state.face_pixels(Face.RIGHT)

        self.assertEqual(len(pixels), FACE_RESOLUTION**2)
        self.assertEqual(pixels[2 * FACE_RESOLUTION + 5], 9)
        self.assertFalse(any(state.face_pixels(Face.LEFT)))


class WorldTest(unittest.TestCase):
    """
    What exists on the cube.
    """

    def test_stores_and_finds_objects_by_name(self) -> None:
        """
        Objects are found by name, and names are unique.
        """
        world = ball_world()

        self.assertEqual(world.get("ball")["name"], "ball")

        with self.assertRaises(EngineError):
            apply_command(world, {"op": "create", "name": "ball", "face": "FRONT", "x": 0, "y": 0, "color": "#000000"})

    def test_explains_which_object_is_missing(self) -> None:
        """
        The message names the object.
        """
        with self.assertRaisesRegex(EngineError, 'There is no object called "ghost"'):
            World().get("ghost")

    def test_updates_keep_the_drawing_order(self) -> None:
        """
        Changing an object does not move it in the order.
        """
        world = World()

        for name in ("a", "b"):
            apply_command(world, {"op": "create", "name": name, "face": "FRONT", "x": 0, "y": 0, "color": "#000000"})

        world.update("a", {"color": 1})

        self.assertEqual([cube_object["name"] for cube_object in world.all()], ["a", "b"])
        self.assertEqual(world.get("a")["color"], 1)

    def test_version_goes_up_with_objects_and_background(self) -> None:
        """
        Both kinds of change are visible in the version.
        """
        world = World()
        start = world.version

        apply_command(world, {"op": "create", "name": "a", "face": "FRONT", "x": 0, "y": 0, "color": "#000000"})
        after_add = world.version
        world.background.set(Face.FRONT, 0, 0, 1)

        self.assertGreater(after_add, start)
        self.assertGreater(world.version, after_add)

    def test_clear_removes_objects_and_background(self) -> None:
        """
        Clearing leaves an empty world.
        """
        world = ball_world()

        world.background.set(Face.FRONT, 0, 0, 1)
        world.clear()

        self.assertEqual(list(world.all()), [])
        self.assertEqual(world.background.get(Face.FRONT, 0, 0), 0)

    def test_uses_the_geometry_settings(self) -> None:
        """
        The config reaches the geometry.
        """
        self.assertEqual(World({"floor": 70}).geometry.floor, 70)


class ObjectCommandTest(unittest.TestCase):
    """
    What the object blocks do.
    """

    def test_creates_a_visible_object_facing_north(self) -> None:
        """
        The defaults of `create`.
        """
        ball = ball_world().get("ball")

        self.assertEqual(ball["pose"], {"surface": "strip", "x": 32, "y": 32, "heading": Heading.NORTH})
        self.assertEqual(ball["color"], 0xFF0000)
        self.assertTrue(ball["visible"])
        self.assertEqual(list(ball["shape"]), [{"dx": 0, "dy": 0}])

    def test_creates_with_a_heading(self) -> None:
        """
        The heading of `create` is kept.
        """
        world = World()

        apply_command(world, {"op": "create", "name": "a", "face": "RIGHT", "x": 1, "y": 2, "color": "#000000", "heading": "EAST"})

        self.assertEqual(world.get("a")["pose"], {"surface": "strip", "x": 65, "y": 2, "heading": Heading.EAST})

    def test_moves_relative_to_the_heading(self) -> None:
        """
        `move` takes steps.
        """
        world = ball_world()

        apply_command(world, {"op": "move", "target": "ball", "step": "right", "count": 3})
        apply_command(world, {"op": "move", "target": "ball", "step": "up"})

        self.assertEqual((world.get("ball")["pose"]["x"], world.get("ball")["pose"]["y"]), (35, 31))

    def test_moves_across_the_top_face(self) -> None:
        """
        `move` goes over the top and arrives turned.
        """
        world = ball_world()

        apply_command(world, {"op": "move", "target": "ball", "step": "up", "count": 33})
        self.assertEqual(world.get("ball")["pose"]["surface"], "top")

        apply_command(world, {"op": "move", "target": "ball", "step": "up", "count": 64})
        self.assertEqual(world.get("ball")["pose"], {"surface": "strip", "x": 2 * 64 + 31, "y": 0, "heading": Heading.SOUTH})

    def test_a_move_that_changes_nothing_leaves_the_world_alone(self) -> None:
        """
        No change, no new version, no redraw.
        """
        world = ball_world()

        apply_command(world, {"op": "move", "target": "ball", "step": "down", "count": 100})

        version = world.version

        apply_command(world, {"op": "move", "target": "ball", "step": "down"})
        apply_command(world, {"op": "move", "target": "ball", "step": "up", "count": 0})

        self.assertEqual(world.version, version)

    def test_move_to_resets_the_heading(self) -> None:
        """
        `moveTo` puts the object on a cell, facing north.
        """
        world = ball_world()

        apply_command(world, {"op": "move", "target": "ball", "step": "up", "count": 40})
        apply_command(world, {"op": "moveTo", "target": "ball", "face": "LEFT", "x": 5, "y": 6})

        self.assertEqual(world.get("ball")["pose"], {"surface": "strip", "x": 3 * 64 + 5, "y": 6, "heading": Heading.NORTH})

        with self.assertRaises(ValueError):
            apply_command(world, {"op": "moveTo", "target": "ball", "face": "FRONT", "x": 64, "y": 0})

    def test_recolors_hides_shows_and_deletes(self) -> None:
        """
        The small blocks.
        """
        world = ball_world()

        apply_command(world, {"op": "setColor", "target": "ball", "color": "#00ff00"})
        self.assertEqual(world.get("ball")["color"], 0x00FF00)

        apply_command(world, {"op": "hide", "target": "ball"})
        self.assertFalse(world.get("ball")["visible"])

        apply_command(world, {"op": "show", "target": "ball"})
        self.assertTrue(world.get("ball")["visible"])

        apply_command(world, {"op": "delete", "target": "ball"})

        with self.assertRaises(EngineError):
            world.get("ball")

    def test_points_up_again(self) -> None:
        """
        `pointUp` undoes the turn of going over the top.
        """
        world = ball_world()

        apply_command(world, {"op": "move", "target": "ball", "step": "up", "count": 33 + 64})
        self.assertEqual(world.get("ball")["pose"]["heading"], Heading.SOUTH)

        apply_command(world, {"op": "pointUp", "target": "ball"})
        self.assertEqual(world.get("ball")["pose"]["heading"], Heading.NORTH)

    def test_fails_on_objects_that_do_not_exist(self) -> None:
        """
        Every block that takes a target says so.
        """
        world = World()
        commands = [
            {"op": "move", "target": "x", "step": "up"},
            {"op": "moveTo", "target": "x", "face": "FRONT", "x": 0, "y": 0},
            {"op": "setColor", "target": "x", "color": "#000000"},
            {"op": "show", "target": "x"},
            {"op": "hide", "target": "x"},
            {"op": "delete", "target": "x"},
            {"op": "pointUp", "target": "x"},
        ]

        for command in commands:
            with self.assertRaises(EngineError, msg=command["op"]):
                apply_command(world, command)

    def test_tells_commands_from_control_blocks(self) -> None:
        """
        Only commands take effect at once.
        """
        self.assertTrue(is_command({"op": "hide", "target": "a"}))
        self.assertFalse(is_command({"op": "wait", "seconds": 1}))
        self.assertFalse(is_command({"op": "forever", "body": []}))
        self.assertFalse(is_command({"op": "repeat", "times": 1, "body": []}))

    def test_the_two_registries_do_not_overlap(self) -> None:
        """
        A block is a command or a control block, never both.
        """
        self.assertFalse(set(COMMAND_BLOCKS) & set(CONTROL_TABLE))
        self.assertIs(CONTROL_BLOCKS, CONTROL_TABLE)


class BackgroundCommandTest(unittest.TestCase):
    """
    What the background blocks do.
    """

    @staticmethod
    def solid(color: str) -> list[str]:
        """
        A picture of one color for a whole face.
        """
        return [color] * (64 * 64)

    def test_puts_a_picture_on_the_faces_it_names(self) -> None:
        """
        Only the named faces change, and the objects are not touched.
        """
        world = ball_world()

        apply_command(world, {"op": "setBackgroundImage", "faces": ["FRONT", "TOP"], "pixels": self.solid("#336699")})

        self.assertEqual(world.background.get(Face.FRONT, 10, 10), 0x336699)
        self.assertEqual(world.background.get(Face.TOP, 63, 63), 0x336699)
        self.assertEqual(world.background.get(Face.LEFT, 10, 10), 0)
        self.assertEqual(world.get("ball")["color"], 0xFF0000)

    def test_places_the_pixels_row_after_row(self) -> None:
        """
        Index `y * 64 + x`.
        """
        world = World()
        pixels = self.solid("#000000")
        pixels[2 * 64 + 5] = "#ff0000"

        apply_command(world, {"op": "setBackgroundImage", "faces": ["RIGHT"], "pixels": pixels})

        self.assertEqual(world.background.get(Face.RIGHT, 5, 2), 0xFF0000)
        self.assertEqual(world.background.get(Face.RIGHT, 2, 5), 0)

    def test_paints_faces_one_color(self) -> None:
        """
        A color replaces a picture, and makes the world change.
        """
        world = World()

        apply_command(world, {"op": "setBackgroundImage", "faces": ["BACK", "LEFT"], "pixels": self.solid("#336699")})

        version = world.version

        apply_command(world, {"op": "setBackgroundColor", "faces": ["BACK"], "color": "#112233"})

        self.assertEqual(world.background.get(Face.BACK, 63, 63), 0x112233)
        self.assertEqual(world.background.get(Face.LEFT, 0, 0), 0x336699)
        self.assertGreater(world.version, version)


class RendererTest(unittest.TestCase):
    """
    Turning the world into pixels.
    """

    PLUS = [{"dx": 0, "dy": 0}, {"dx": 0, "dy": -1}, {"dx": 1, "dy": 0}, {"dx": 0, "dy": 1}, {"dx": -1, "dy": 0}]
    """
    A plus sign around the center.
    """

    @staticmethod
    def setup(config: dict | None = None) -> tuple[World, CubeState, Renderer]:
        """
        An empty world, its output and the renderer between them.
        """
        world, output = World(config), CubeState()

        return world, output, Renderer(world, output)

    def create(self, world: World, **fields) -> None:
        """
        Adds an object at FRONT (10, 10) unless the fields say otherwise.
        """
        apply_command(world, {"op": "create", "name": "a", "face": "FRONT", "x": 10, "y": 10, "color": "#ff0000", **fields})

    def test_draws_a_visible_object_where_its_pose_is(self) -> None:
        """
        On a side and on the top.
        """
        world, output, renderer = self.setup()

        self.create(world, face="RIGHT", x=3, y=4)
        self.create(world, name="b", face="TOP", x=7, y=8, color="#00ff00")
        renderer.render()

        self.assertEqual(output.get(Face.RIGHT, 3, 4), 0xFF0000)
        self.assertEqual(output.get(Face.TOP, 7, 8), 0x00FF00)

    def test_draws_every_pixel_of_a_shape(self) -> None:
        """
        A plus sign around the center.
        """
        world, output, renderer = self.setup()

        self.create(world, pixels=self.PLUS)
        renderer.render()

        for x, y in [(10, 10), (10, 9), (11, 10), (10, 11), (9, 10)]:
            self.assertEqual(output.get(Face.FRONT, x, y), 0xFF0000)

        self.assertEqual(output.get(Face.FRONT, 11, 11), 0)

    def test_draws_the_pixels_that_cross_an_edge_on_the_other_face(self) -> None:
        """
        Over the top edge and from one side to the next.
        """
        world, output, renderer = self.setup()

        self.create(world, y=0, pixels=self.PLUS)
        self.create(world, name="b", x=63, pixels=self.PLUS)
        renderer.render()

        self.assertEqual(output.get(Face.TOP, 10, 63), 0xFF0000)
        self.assertEqual(output.get(Face.RIGHT, 0, 10), 0xFF0000)

    def test_turns_the_shape_with_the_object(self) -> None:
        """
        Facing east, the shape's up points east.
        """
        world, output, renderer = self.setup()

        self.create(world, heading="EAST", pixels=[{"dx": 0, "dy": -1}])
        renderer.render()

        self.assertEqual(output.get(Face.FRONT, 11, 10), 0xFF0000)

    def test_a_pixel_color_wins_over_the_object_color(self) -> None:
        """
        Pixels with their own color keep it.
        """
        world, output, renderer = self.setup()

        self.create(world, pixels=[{"dx": 0, "dy": 0}, {"dx": 1, "dy": 0, "color": "#0000ff"}])
        renderer.render()

        self.assertEqual(output.get(Face.FRONT, 10, 10), 0xFF0000)
        self.assertEqual(output.get(Face.FRONT, 11, 10), 0x0000FF)

    def test_skips_pixels_blocked_by_the_floor_and_hidden_objects(self) -> None:
        """
        Below the visible rows nothing is drawn, and hidden objects do not show.
        """
        world, output, renderer = self.setup({"floor": 70})

        self.create(world, y=63)
        apply_command(world, {"op": "move", "target": "a", "step": "down", "count": 3})
        self.create(world, name="b", x=1, y=1)
        apply_command(world, {"op": "hide", "target": "b"})
        renderer.render()

        self.assertEqual(output.get(Face.FRONT, 10, 63), 0)
        self.assertEqual(output.get(Face.FRONT, 1, 1), 0)

    def test_background_is_underneath_and_leaves_no_trail(self) -> None:
        """
        Objects draw over the background, and where they were it shows again.
        """
        world, output, renderer = self.setup()

        fill_rect(world.background, Face.FRONT, 0, 0, 4, 4, 0x0000FF)
        self.create(world, x=1, y=1)
        renderer.render()

        self.assertEqual(output.get(Face.FRONT, 0, 0), 0x0000FF)
        self.assertEqual(output.get(Face.FRONT, 1, 1), 0xFF0000)

        apply_command(world, {"op": "move", "target": "a", "step": "right", "count": 10})
        renderer.render()

        self.assertEqual(output.get(Face.FRONT, 1, 1), 0x0000FF)

    def test_later_objects_are_on_top(self) -> None:
        """
        Creation order is drawing order.
        """
        world, output, renderer = self.setup()

        self.create(world)
        self.create(world, name="b", color="#00ff00")
        renderer.render()

        self.assertEqual(output.get(Face.FRONT, 10, 10), 0x00FF00)

    def test_does_nothing_when_the_world_has_not_changed(self) -> None:
        """
        A still cube costs nothing.
        """
        world, output, renderer = self.setup()

        self.create(world)

        self.assertTrue(renderer.render())

        version = output.version

        self.assertFalse(renderer.render())
        self.assertEqual(output.version, version)

    def test_the_circle_helper_fills_a_disc(self) -> None:
        """
        A drawing primitive, even if no block uses it.
        """
        state = CubeState()

        fill_circle(state, Face.FRONT, 10, 10, 3, 5)

        self.assertEqual(state.get(Face.FRONT, 10, 10), 5)
        self.assertEqual(state.get(Face.FRONT, 13, 10), 5)
        self.assertEqual(state.get(Face.FRONT, 14, 10), 0)


if __name__ == "__main__":
    unittest.main()
