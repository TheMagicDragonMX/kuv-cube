"""
LAYER: program file.

The complete program of a creation as one JSON document: the program the cube runs and the environment it runs on.
It is what the web app sends to the cube and what the API keeps as `program.json`. Mirror of
`kuv-client/src/app/cube/engine/program-file/program-file.ts`.

    ProgramFile
     ├─ version      version of this format
     ├─ program      the program (see `program/program.py`)
     └─ environment  optional pictures behind the objects and brightness

In a file every picture is a list of colors written `#RRGGBB`; the engine wants packed numbers. This file checks a
file and converts its pictures.
"""

from typing import Any, NotRequired, TypedDict, cast

from programs.main.cube.environment.environment import BackgroundImages, Environment
from programs.main.cube.errors import ProgramError
from programs.main.cube.program.names import FACE_BY_NAME, is_color_value, parse_color
from programs.main.cube.program.program import Program
from programs.main.cube.program.validate_program import validate_program
from programs.main.cube.renderer.renderer import Brightness
from programs.main.cube.state.cube_state import FACE_RESOLUTION


PROGRAM_FILE_VERSION = 1
"""
Version of the program file format.
"""

FACE_PIXELS = FACE_RESOLUTION * FACE_RESOLUTION
"""
Pixels on one face.
"""


class LoadedProgramFile(TypedDict):
    """
    What a program file holds, ready for the engine.
    """

    program: Program
    """
    The program the cube runs.
    """

    environment: NotRequired[Environment]
    """
    The environment the program runs on, when the file has one.
    """


def read_program_file(value: Any) -> LoadedProgramFile:
    """
    Checks a program file, for example one the web app sent, and returns what it holds for the engine. Raises a
    ProgramError, saying where, if it is not valid.
    """
    file = expect_object(value, "programFile")

    if file.get("version") != PROGRAM_FILE_VERSION or isinstance(file.get("version"), bool):
        raise ProgramError(f"programFile.version: must be {PROGRAM_FILE_VERSION}")

    program = validate_program(file.get("program"))

    if "environment" not in file:
        return {"program": program}

    return {"program": program, "environment": read_environment(file["environment"])}


def read_environment(value: Any) -> Environment:
    """
    Checks the environment of a file and turns its pictures into packed colors.
    """
    file = expect_object(value, "environment")
    environment: Environment = {}

    if "background" in file:
        environment["background"] = read_images(file["background"], "environment.background")

    if "backgrounds" in file:
        if not isinstance(file["backgrounds"], list):
            raise ProgramError("environment.backgrounds: must be a list of backgrounds")

        environment["backgrounds"] = []

        for index, item in enumerate(file["backgrounds"]):
            path = f"environment.backgrounds[{index}]"
            background = expect_object(item, path)

            if not isinstance(background.get("name"), str) or not background["name"]:
                raise ProgramError(f"{path}.name: must be a non-empty text")

            images = read_images(background.get("images"), f"{path}.images")

            environment["backgrounds"].append({"name": background["name"], "images": images})

    if "startBackground" in file:
        if not isinstance(file["startBackground"], str):
            raise ProgramError("environment.startBackground: must be a text")

        environment["startBackground"] = file["startBackground"]

    if "brightness" in file:
        environment["brightness"] = cast(Brightness, expect_object(file["brightness"], "environment.brightness"))

    return environment


def read_images(value: Any, path: str) -> BackgroundImages:
    """
    Checks the pictures of the faces and turns each into a list of packed colors.
    """
    images: BackgroundImages = {}

    for face, colors in expect_object(value, path).items():
        if face not in FACE_BY_NAME:
            raise ProgramError(f"{path}.{face}: is not a face")

        if not isinstance(colors, list) or len(colors) != FACE_PIXELS or not all(is_color_value(color) for color in colors):
            raise ProgramError(f"{path}.{face}: must be {FACE_PIXELS} colors written as #rrggbb, row after row")

        images[face] = [parse_color(color) for color in colors]

    return images


def expect_object(value: Any, path: str) -> dict[str, Any]:
    """
    Requires a JSON object.
    """
    if not isinstance(value, dict):
        raise ProgramError(f"{path}: must be an object")

    return value
