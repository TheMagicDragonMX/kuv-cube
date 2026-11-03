"""
Tests for the format of programs: the validator and the schemas of the blocks.
"""

import typing
import unittest

from programs.main.cube.blocks import DEFINITIONS
from programs.main.cube.blocks.background import BackgroundCommand
from programs.main.cube.blocks.control import ControlBlock
from programs.main.cube.blocks.object import ObjectCommand
from programs.main.cube.errors import ProgramError
from programs.main.cube.program.names import format_color, parse_color
from programs.main.cube.program.validate_program import validate_program


def program(*blocks: object) -> dict:
    """
    A program with one script that starts at once.
    """
    return {"version": 1, "scripts": [{"trigger": {"type": "start"}, "blocks": list(blocks)}]}


class SchemaTest(unittest.TestCase):
    """
    Each block's schema says what its type says.
    """

    def test_schemas_have_exactly_the_fields_of_the_types(self) -> None:
        """
        Same fields, and the optional ones are the optional ones.
        """
        types = [
            *typing.get_args(ObjectCommand),
            *typing.get_args(BackgroundCommand),
            *typing.get_args(ControlBlock),
        ]

        self.assertEqual(len(types), len(DEFINITIONS))

        for block_type in types:
            # The raw annotations: evaluating them would need the `Block` type, which only type checkers import.
            op = typing.get_args(block_type.__annotations__["op"])[0]
            schema = DEFINITIONS[op]["schema"]
            fields = set(block_type.__annotations__) - {"op"}
            optional = {name for name in block_type.__optional_keys__ if name != "op"}

            self.assertEqual(set(schema), fields, op)
            self.assertEqual({name for name, field in schema.items() if field.get("optional")}, optional, op)


class ColorTest(unittest.TestCase):
    """
    Colors written as text.
    """

    def test_converts_both_ways(self) -> None:
        """
        `#RRGGBB` and the packed number.
        """
        self.assertEqual(parse_color("#ff8800"), 0xFF8800)
        self.assertEqual(format_color(0x000FF0), "#000ff0")


class ValidateProgramTest(unittest.TestCase):
    """
    What is accepted as a program and what is not.
    """

    def assertRejects(self, value: object, message: str) -> None:
        """
        The value is refused with an error that has the message in it.
        """
        with self.assertRaisesRegex(ProgramError, message):
            validate_program(value)

    def test_accepts_the_simplest_programs(self) -> None:
        """
        No scripts, and the program it was given is the one it returns.
        """
        validate_program({"version": 1, "scripts": []})

        value = program()

        self.assertIs(validate_program(value), value)

    def test_rejects_what_is_not_a_program(self) -> None:
        """
        The top level.
        """
        self.assertRejects("nope", "program: must be an object")
        self.assertRejects([], "program: must be an object")
        self.assertRejects({"version": 2, "scripts": []}, "version: must be 1")
        self.assertRejects({"version": True, "scripts": []}, "version: must be 1")
        self.assertRejects({"version": 1}, "scripts: must be a list of scripts")
        self.assertRejects({"version": 1, "scripts": [], "extra": 1}, r"program\.extra: unknown field")

    def test_config(self) -> None:
        """
        A side as top anchor and a floor are fine; the top face as anchor and a negative floor are not.
        """
        validate_program({"version": 1, "config": {"topAnchor": "LEFT", "floor": 70}, "scripts": []})

        self.assertRejects({"version": 1, "config": {"topAnchor": "TOP"}, "scripts": []}, r"config\.topAnchor")
        self.assertRejects({"version": 1, "config": {"floor": -1}, "scripts": []}, r"config\.floor")

    def test_triggers(self) -> None:
        """
        `start` and `every` with a positive, finite interval.
        """
        validate_program(
            {
                "version": 1,
                "scripts": [
                    {"trigger": {"type": "start"}, "blocks": []},
                    {"trigger": {"type": "every", "seconds": 2}, "blocks": []},
                ],
            }
        )

        self.assertRejects({"version": 1, "scripts": [{"trigger": {"type": "key"}, "blocks": []}]}, r"scripts\[0\]\.trigger\.type")

        for seconds in (0, -1, float("nan"), float("inf"), True, "1"):
            self.assertRejects(
                {"version": 1, "scripts": [{"trigger": {"type": "every", "seconds": seconds}, "blocks": []}]},
                r"scripts\[0\]\.trigger\.seconds",
            )

    def test_says_where_the_problem_is(self) -> None:
        """
        The path of the field is in the message.
        """
        value = program(
            {"op": "create", "name": "a", "face": "FRONT", "x": 0, "y": 0, "color": "#ffffff"},
            {"op": "move", "target": "a", "step": "up", "count": -1},
        )

        self.assertRejects(value, r"scripts\[0\]\.blocks\[1\]\.count: must be a whole number")

    def test_rejects_unknown_blocks_typos_and_missing_fields(self) -> None:
        """
        Strict on purpose.
        """
        self.assertRejects(program({"op": "jump"}), 'unknown block "jump"')
        self.assertRejects(program({"op": "move", "target": "a", "step": "up", "cont": 2}), r"blocks\[0\]\.cont: unknown field")
        self.assertRejects(program({"op": "move", "step": "up"}), r"blocks\[0\]\.target: is required")

    def test_rejects_values_of_the_wrong_kind(self) -> None:
        """
        One bad field per block.
        """
        blocks = [
            {"op": "moveTo", "target": "a", "face": "MIDDLE", "x": 0, "y": 0},
            {"op": "create", "name": "a", "face": "FRONT", "x": 0, "y": 0, "color": "#000000", "heading": "UP"},
            {"op": "move", "target": "a", "step": "forward"},
            {"op": "setColor", "target": "a", "color": "red"},
            {"op": "setColor", "target": "a", "color": "#12345678"},
            {"op": "moveTo", "target": "a", "face": "FRONT", "x": 1.5, "y": 0},
            {"op": "moveTo", "target": "a", "face": "FRONT", "x": True, "y": 0},
            {"op": "wait", "seconds": -1},
            {"op": "wait", "seconds": float("nan")},
            {"op": "show", "target": ""},
        ]

        for block in blocks:
            with self.assertRaises(ProgramError, msg=str(block)):
                validate_program(program(block))

    def test_allows_cells_outside_a_face(self) -> None:
        """
        Shapes may overflow.
        """
        validate_program(program({"op": "moveTo", "target": "a", "face": "FRONT", "x": -3, "y": 100}))

    def test_shapes(self) -> None:
        """
        A good shape is accepted; every kind of bad one is not.
        """
        create = {"op": "create", "name": "a", "face": "FRONT", "x": 5, "y": 5, "color": "#ffffff"}

        validate_program(program({**create, "pixels": [{"dx": 0, "dy": -1}, {"dx": 1, "dy": 0, "color": "#ff0000"}]}))

        for pixels in ([], [{"dx": 1}], [{"dx": 0.5, "dy": 0}], [{"dx": 0, "dy": 0, "color": "red"}], [{"dx": 0, "dy": 0, "z": 1}], {"dx": 0, "dy": 0}):
            with self.assertRaises(ProgramError, msg=str(pixels)):
                validate_program(program({**create, "pixels": pixels}))

    def test_checks_the_blocks_nested_in_loops(self) -> None:
        """
        The path goes through the bodies.
        """
        value = program({"op": "forever", "body": [{"op": "repeat", "times": 2, "body": [{"op": "wait", "seconds": "x"}]}]})

        self.assertRejects(value, r"scripts\[0\]\.blocks\[0\]\.body\[0\]\.body\[0\]\.seconds")

    def test_background_blocks(self) -> None:
        """
        Faces and pictures.
        """
        pixels = ["#000000"] * (64 * 64)

        validate_program(program({"op": "setBackgroundImage", "faces": ["FRONT", "TOP"], "pixels": pixels}))
        validate_program(program({"op": "setBackgroundColor", "faces": ["LEFT"], "color": "#ff00ff"}))

        bad = [
            ({"op": "setBackgroundColor", "faces": [], "color": "#000000"}, "faces"),
            ({"op": "setBackgroundColor", "faces": ["MIDDLE"], "color": "#000000"}, "faces"),
            ({"op": "setBackgroundColor", "faces": "FRONT", "color": "#000000"}, "faces"),
            ({"op": "setBackgroundImage", "faces": ["FRONT"], "pixels": pixels[1:]}, "pixels"),
            ({"op": "setBackgroundImage", "faces": ["FRONT"], "pixels": [*pixels[1:], "red"]}, "pixels"),
        ]

        for block, field in bad:
            self.assertRejects(program(block), rf"scripts\[0\]\.blocks\[0\]\.{field}")

    def test_objects_the_program_starts_with(self) -> None:
        """
        Only `create` blocks, with names that are not repeated.
        """
        ball = {"op": "create", "name": "ball", "face": "FRONT", "x": 32, "y": 32, "color": "#ff0000"}

        validate_program({"version": 1, "objects": [ball, {**ball, "name": "other"}], "scripts": []})

        self.assertRejects({"version": 1, "objects": [{"op": "wait", "seconds": 1}], "scripts": []}, r"objects\[0\]\.op")
        self.assertRejects({"version": 1, "objects": [ball, ball], "scripts": []}, r"objects\[1\]\.name")
        self.assertRejects({"version": 1, "objects": "ball", "scripts": []}, "objects")
        self.assertRejects({"version": 1, "objects": [{**ball, "color": "red"}], "scripts": []}, r"objects\[0\]\.color")


if __name__ == "__main__":
    unittest.main()
