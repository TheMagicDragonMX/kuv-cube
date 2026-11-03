"""
LAYER: program format (validation).

Checks that something that claims to be a program really is one, before the engine runs it. A program can come from
a file, the network or Blockly, so nothing about it can be trusted. Everything the engine does later assumes the
program passed through here.

Errors say exactly where the problem is, for example:

    scripts[0].blocks[2].count: must be a whole number, zero or more

Unknown fields are rejected on purpose: a typo like `cont` instead of `count` would otherwise be silently ignored
and the block would do something unexpected.

What a valid block looks like is not written here but in the file of each block, in `blocks/`. This file only reads
it.
"""

import json
import math
from typing import Any, NoReturn, TypeAlias

from programs.main.cube.blocks import get_block_definition
from programs.main.cube.blocks.fields import FieldKind
from programs.main.cube.errors import ProgramError
from programs.main.cube.program.names import FACE_BY_NAME, HEADING_BY_NAME, is_color_value
from programs.main.cube.program.program import Program
from programs.main.cube.state.cube_state import FACE_RESOLUTION


SIDE_NAMES = ["FRONT", "RIGHT", "BACK", "LEFT"]
"""
Names of the faces around the cube, as programs write them.
"""

STEP_NAMES = ["up", "right", "down", "left"]
"""
Names of the directions a move can take, as programs write them.
"""

Fields: TypeAlias = dict[str, Any]
"""
The fields of a block, before they are checked.
"""


def validate_program(value: Any) -> Program:
    """
    Checks a value and returns it typed as a Program. Raises a ProgramError if it is not one.
    """
    program = expect_object(value, "program")

    expect_only_keys(program, ["version", "config", "objects", "scripts"], "program")

    if not is_integer(program.get("version")) or program["version"] != 1:
        fail("version", "must be 1")

    if "config" in program:
        validate_config(program["config"])

    if "objects" in program:
        validate_objects(program["objects"])

    scripts = program.get("scripts")

    if not isinstance(scripts, list):
        fail("scripts", "must be a list of scripts")

    for index, script in enumerate(scripts):
        validate_script(script, f"scripts[{index}]")

    return value


def validate_config(value: Any) -> None:
    """
    Checks the optional engine settings.
    """
    config = expect_object(value, "config")

    expect_only_keys(config, ["topAnchor", "floor"], "config")

    if "topAnchor" in config and config["topAnchor"] not in SIDE_NAMES:
        fail("config.topAnchor", f"must be one of {', '.join(SIDE_NAMES)}")

    if "floor" in config and not is_count(config["floor"]):
        fail("config.floor", "must be a whole number, zero or more")


def validate_objects(value: Any) -> None:
    """
    Checks the objects a program starts with: `create` blocks with names that are not repeated.
    """
    if not isinstance(value, list):
        fail("objects", "must be a list of create blocks")

    names = set()

    for index, cube_object in enumerate(value):
        path = f"objects[{index}]"

        validate_block(cube_object, path)

        if cube_object["op"] != "create":
            fail(f"{path}.op", "must be 'create'")

        name = cube_object["name"]

        if name in names:
            fail(f"{path}.name", f'there is already an object called "{name}"')

        names.add(name)


def validate_script(value: Any, path: str) -> None:
    """
    Checks a script: its trigger and its blocks.
    """
    script = expect_object(value, path)

    expect_only_keys(script, ["trigger", "blocks"], path)

    validate_trigger(script.get("trigger"), f"{path}.trigger")
    validate_blocks(script.get("blocks"), f"{path}.blocks")


def validate_trigger(value: Any, path: str) -> None:
    """
    Checks the event that starts a script.
    """
    trigger = expect_object(value, path)
    kind = trigger.get("type")

    if kind == "start":
        expect_only_keys(trigger, ["type"], path)

    elif kind == "every":
        expect_only_keys(trigger, ["type", "seconds"], path)

        if not is_number(trigger.get("seconds")) or trigger["seconds"] <= 0:
            fail(f"{path}.seconds", "must be a number greater than zero")

    else:
        fail(f"{path}.type", "must be 'start' or 'every'")


def validate_blocks(value: Any, path: str) -> None:
    """
    Checks a list of blocks, including the lists nested inside loops.
    """
    if not isinstance(value, list):
        fail(path, "must be a list of blocks")

    for index, block in enumerate(value):
        validate_block(block, f"{path}[{index}]")


def validate_block(value: Any, path: str) -> None:
    """
    Checks one block against its schema.
    """
    block = expect_object(value, path)
    op = block.get("op")
    definition = get_block_definition(op) if isinstance(op, str) else None

    if definition is None:
        fail(f"{path}.op", f"unknown block {json.dumps(op, default=str)}")

    schema = definition["schema"]

    expect_only_keys(block, ["op", *schema], path)

    for name, field in schema.items():
        if name not in block:
            if not field.get("optional"):
                fail(f"{path}.{name}", "is required")

            continue

        validate_field(field["kind"], block[name], f"{path}.{name}")


def validate_field(kind: FieldKind, value: Any, path: str) -> None:
    """
    Checks the value of one field.
    """
    face_names = ", ".join(FACE_BY_NAME)

    if kind == "text":
        if not isinstance(value, str) or not value:
            fail(path, "must be a non-empty text")

    elif kind == "face":
        if not is_name(value, FACE_BY_NAME):
            fail(path, f"must be one of {face_names}")

    elif kind == "faces":
        if not isinstance(value, list) or not value or not all(is_name(name, FACE_BY_NAME) for name in value):
            fail(path, f"must be a non-empty list of faces ({face_names})")

    elif kind == "heading":
        if not is_name(value, HEADING_BY_NAME):
            fail(path, f"must be one of {', '.join(HEADING_BY_NAME)}")

    elif kind == "step":
        if not is_name(value, STEP_NAMES):
            fail(path, f"must be one of {', '.join(STEP_NAMES)}")

    elif kind == "color":
        if not is_color_value(value):
            fail(path, "must be a color written as #rrggbb")

    elif kind == "integer":
        if not is_integer(value):
            fail(path, "must be a whole number")

    elif kind == "count":
        if not is_count(value):
            fail(path, "must be a whole number, zero or more")

    elif kind == "seconds":
        if not is_number(value) or value < 0:
            fail(path, "must be a number of seconds, zero or more")

    elif kind == "shape":
        validate_shape(value, path)

    elif kind == "image":
        if not isinstance(value, list) or len(value) != FACE_RESOLUTION**2 or not all(map(is_color_value, value)):
            fail(path, f"must be {FACE_RESOLUTION**2} colors written as #rrggbb, row after row")

    elif kind == "blocks":
        validate_blocks(value, path)


def validate_shape(value: Any, path: str) -> None:
    """
    Checks the pixels of an object: a non-empty list of offsets with an optional color each.
    """
    if not isinstance(value, list) or not value:
        fail(path, "must be a non-empty list of pixels")

    for index, item in enumerate(value):
        pixel = expect_object(item, f"{path}[{index}]")

        expect_only_keys(pixel, ["dx", "dy", "color"], f"{path}[{index}]")

        for axis in ("dx", "dy"):
            if not is_integer(pixel.get(axis)):
                fail(f"{path}[{index}].{axis}", "must be a whole number")

        if "color" in pixel and not is_color_value(pixel["color"]):
            fail(f"{path}[{index}].color", "must be a color written as #rrggbb")


def is_name(value: Any, names: Any) -> bool:
    """
    Tells whether a value is a text that is one of the names.
    """
    return isinstance(value, str) and value in names


def is_integer(value: Any) -> bool:
    """
    Tells whether a value is a whole number. A boolean is not one.
    """
    return isinstance(value, int) and not isinstance(value, bool)


def is_count(value: Any) -> bool:
    """
    Tells whether a value is a whole number, zero or more.
    """
    return is_integer(value) and value >= 0


def is_number(value: Any) -> bool:
    """
    Tells whether a value is a finite number. A boolean is not one.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def expect_object(value: Any, path: str) -> Fields:
    """
    Requires a plain object (not None, not a list).
    """
    if not isinstance(value, dict):
        fail(path, "must be an object")

    return value


def expect_only_keys(fields: Fields, allowed: list[str], path: str) -> None:
    """
    Rejects fields that are not in the allowed list.
    """
    for key in fields:
        if key not in allowed:
            fail(f"{path}.{key}", f"unknown field (allowed: {', '.join(allowed)})")


def fail(path: str, message: str) -> NoReturn:
    """
    Reports a problem found at a place of the program.
    """
    raise ProgramError(f"{path}: {message}")
