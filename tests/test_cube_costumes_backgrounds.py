"""
Tests for costumes, named backgrounds and brightness: the parts of the web app's engine that came last to the cube.
"""

import unittest

from programs.main.cube import CubeEngine, ProgramError, validate_program
from programs.main.cube.state.cube_state import Face


def script(*blocks: dict) -> dict:
    """
    A program with one script that starts at once.
    """
    return {"version": 1, "scripts": [{"trigger": {"type": "start"}, "blocks": list(blocks)}]}


def solid(color: int) -> list[int]:
    """
    A picture of one color for a whole face.
    """
    return [color] * (64 * 64)


ROBOT = {
    "op": "create",
    "name": "robot",
    "face": "FRONT",
    "x": 5,
    "y": 5,
    "color": "#ff0000",
    "costumes": [
        {"name": "red", "color": "#ff0000"},
        {"name": "wide", "color": "#00ff00", "pixels": [{"dx": 0, "dy": 0}, {"dx": 1, "dy": 0}]},
    ],
}
"""
An object with two costumes: one red pixel, and two green pixels side by side.
"""

BACKGROUNDS = {
    "background": {"FRONT": solid(0x110000)},
    "backgrounds": [
        {"name": "one", "images": {"FRONT": solid(0x110000)}},
        {"name": "two", "images": {"FRONT": solid(0x002200)}},
    ],
    "startBackground": "one",
}
"""
An environment with two backgrounds for the front face, starting on the first.
"""


class CostumeTest(unittest.TestCase):
    """
    The setCostume and nextCostume blocks.
    """

    def run_blocks(self, *blocks: dict) -> tuple[CubeEngine, list]:
        """
        Runs the robot and some blocks, and returns the engine and the script errors.
        """
        errors: list = []
        engine = CubeEngine({"on_error": errors.append})

        engine.load(script(ROBOT, *blocks))
        engine.start(0)

        return engine, errors

    def test_set_costume_changes_shape_and_color(self) -> None:
        """
        The object takes the pixels and the color of the costume.
        """
        engine, _ = self.run_blocks({"op": "setCostume", "target": "robot", "name": "wide"})

        self.assertEqual(engine.state.get(Face.FRONT, 5, 5), 0x00FF00)
        self.assertEqual(engine.state.get(Face.FRONT, 6, 5), 0x00FF00)

    def test_next_costume_cycles(self) -> None:
        """
        After the last costume comes the first again.
        """
        engine, _ = self.run_blocks({"op": "nextCostume", "target": "robot"}, {"op": "nextCostume", "target": "robot"})

        self.assertEqual(engine.state.get(Face.FRONT, 5, 5), 0xFF0000)
        self.assertEqual(engine.state.get(Face.FRONT, 6, 5), 0)

    def test_unknown_costume_stops_the_script(self) -> None:
        """
        A costume the object does not have is a script error.
        """
        _, errors = self.run_blocks({"op": "setCostume", "target": "robot", "name": "blue"})

        self.assertIn("no costume", errors[0]["message"])

    def test_repeated_costume_names_are_invalid(self) -> None:
        """
        Two costumes with the same name are rejected before running.
        """
        robot = {**ROBOT, "costumes": [{"name": "a", "color": "#ff0000"}, {"name": "a", "color": "#00ff00"}]}

        with self.assertRaisesRegex(ProgramError, "already a costume"):
            validate_program(script(robot))


class NamedBackgroundTest(unittest.TestCase):
    """
    The setBackground and nextBackground blocks.
    """

    def run_blocks(self, *blocks: dict, environment: dict | None = None) -> tuple[CubeEngine, list]:
        """
        Runs some blocks on the two backgrounds, and returns the engine and the script errors.
        """
        errors: list = []
        engine = CubeEngine({"on_error": errors.append})

        engine.set_environment(BACKGROUNDS if environment is None else environment)
        engine.load(script(*blocks))
        engine.start(0)

        return engine, errors

    def test_set_background_shows_it(self) -> None:
        """
        The faces of the background take its pictures.
        """
        engine, _ = self.run_blocks({"op": "setBackground", "name": "two"})

        self.assertEqual(engine.state.get(Face.FRONT, 0, 0), 0x002200)

    def test_next_background_goes_on_from_the_start_one(self) -> None:
        """
        From the start background the next one is the second, and then the first again.
        """
        engine, _ = self.run_blocks({"op": "nextBackground"})

        self.assertEqual(engine.state.get(Face.FRONT, 0, 0), 0x002200)

        engine, _ = self.run_blocks({"op": "nextBackground"}, {"op": "nextBackground"})

        self.assertEqual(engine.state.get(Face.FRONT, 0, 0), 0x110000)

    def test_unknown_background_stops_the_script(self) -> None:
        """
        A name that is not one of the backgrounds is a script error.
        """
        _, errors = self.run_blocks({"op": "setBackground", "name": "three"})

        self.assertIn("no background", errors[0]["message"])

    def test_next_background_without_backgrounds_stops_the_script(self) -> None:
        """
        There is nothing to switch to.
        """
        _, errors = self.run_blocks({"op": "nextBackground"}, environment={})

        self.assertIn("no backgrounds", errors[0]["message"])


class BrightnessTest(unittest.TestCase):
    """
    The brightness of the environment, applied by the renderer.
    """

    def test_dims_the_background_behind_objects_and_the_objects(self) -> None:
        """
        A face with objects shows its background at `behindObjects`, a face without at `background`, and the objects
        at `objects`.
        """
        engine = CubeEngine()

        engine.set_environment(
            {
                "background": {"FRONT": solid(0xC8C8C8), "RIGHT": solid(0xC8C8C8)},
                "brightness": {"background": 0.5, "behindObjects": 0.25, "objects": 0.5},
            }
        )
        engine.load(script({"op": "create", "name": "a", "face": "FRONT", "x": 1, "y": 1, "color": "#ff0000"}))
        engine.start(0)

        self.assertEqual(engine.state.get(Face.FRONT, 0, 0), 0x323232)
        self.assertEqual(engine.state.get(Face.RIGHT, 0, 0), 0x646464)
        self.assertEqual(engine.state.get(Face.FRONT, 1, 1), 0x800000)

    def test_full_brightness_without_settings(self) -> None:
        """
        Without brightness nothing is dimmed.
        """
        engine = CubeEngine()

        engine.set_environment({"background": {"FRONT": solid(0xC8C8C8)}})

        self.assertEqual(engine.state.get(Face.FRONT, 0, 0), 0xC8C8C8)


if __name__ == "__main__":
    unittest.main()
