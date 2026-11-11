"""
The cube: runs the programs the users make, and shows them on the LED panels.

A program is JSON, the same one the web app produces (see `kuv-client/src/app/cube/engine/`). This folder is a port of that
folder, layer by layer, so a change in one is a change in the other.

    program (JSON) --> interpreter + scheduler --> world --> renderer --> state --> panel layout --> matrix
                             |                       ^
                             '---- commands ---------'
                                       |
                                     blocks (what each block is and does)

    environment (pictures on the faces) --painted onto the world's background by the engine

Each layer does one thing and only uses the layers above it in this list. The data flows down:

    state/        The pixel buffer: one 64x64 grid of colors per face
    geometry/     Where an object ends up when it steps: the strip, the top face, headings, edges, the floor
    drawing/      Draws pixels, lines, rectangles, circles and pictures on one face of a state
    world/        What exists: the objects and the background layer
    blocks/       One file per block, in the folder of its category: its type, its fields and what it does
    program/      The shape of a program, names to engine values, and the validator
    commands/     Looks up a command in `blocks/` and applies it to the world
    runtime/      The interpreter (runs one script) and the scheduler (decides when each script runs)
    environment/  The stage a program runs on: the picture of each face
    renderer/     Turns the world into pixels
    engine/       Puts the layers together; the engine takes the time as an argument, the player has a clock
    view/         Turns a state into the scene the matrix program draws on the panels

Rules that keep it this way:

  - Everything up to `engine/` is plain Python. Only `view/` knows the panels, and it never opens them: it makes a
    scene for `MatrixClient`.
  - The engine never reads a clock. The time is always passed in.
  - Every file starts with a comment saying what its layer does and does not do.

Outside this folder, import from here and nothing else.
"""

from programs.main.cube.blocks import Block, CreateCommand
from programs.main.cube.engine.cube_engine import CubeEngine, CubeEngineOptions
from programs.main.cube.engine.cube_player import CubePlayer, CubePlayerOptions
from programs.main.cube.environment.environment import BackgroundImages, Environment
from programs.main.cube.environment.pixelate import RawImage, pixelate
from programs.main.cube.errors import EngineError, ProgramError
from programs.main.cube.program.names import format_color, parse_color
from programs.main.cube.program.program import (
    FaceName,
    HeadingName,
    Program,
    ProgramConfig,
    Script,
    ShapePixelDefinition,
    SideName,
    Trigger,
)
from programs.main.cube.program.validate_program import validate_program
from programs.main.cube.runtime.scheduler import ScriptError
from programs.main.cube.state.cube_state import FACE_RESOLUTION, Color, CubeState, Face
from programs.main.cube.view.panel_layout import scene_of


__all__ = [
    "BackgroundImages",
    "Block",
    "Color",
    "CreateCommand",
    "CubeEngine",
    "CubeEngineOptions",
    "CubePlayer",
    "CubePlayerOptions",
    "CubeState",
    "EngineError",
    "Environment",
    "FACE_RESOLUTION",
    "Face",
    "FaceName",
    "HeadingName",
    "Program",
    "ProgramConfig",
    "ProgramError",
    "RawImage",
    "Script",
    "ScriptError",
    "ShapePixelDefinition",
    "SideName",
    "Trigger",
    "format_color",
    "parse_color",
    "pixelate",
    "scene_of",
    "validate_program",
]
"""
What other folders may import from here.
"""
