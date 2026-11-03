"""
LAYER: program format (types).

A program is plain data, the same JSON that Blockly produces in the web app and that the Raspberry Pi engine reads.
This file only describes its shape; it contains no behavior.

    Program
     |- config    optional engine settings (top anchor, floor)
     |- objects   optional objects that exist from the start, before any script runs
     '- scripts   each one is a trigger plus a list of blocks
                   '- blocks  commands (do something now) and control blocks (wait, repeat, forever);
                              every block has its own file in `blocks/`

Names are readable strings ('FRONT', 'NORTH', '#ff0000') so programs can be read and written by people. `names.py`
converts them to the engine's internal values.

The keys are the ones of the JSON contract, so they keep the camelCase of the web app (`topAnchor`).
"""

from typing import TYPE_CHECKING, Literal, NotRequired, TypeAlias, TypedDict

if TYPE_CHECKING:
    from programs.main.cube.blocks import Block
    from programs.main.cube.blocks.object.create import CreateCommand


FaceName: TypeAlias = Literal["FRONT", "RIGHT", "BACK", "LEFT", "TOP"]
"""
Name of a face of the cube.
"""

SideName: TypeAlias = Literal["FRONT", "RIGHT", "BACK", "LEFT"]
"""
Name of a side face (every face but the top).
"""

HeadingName: TypeAlias = Literal["NORTH", "EAST", "SOUTH", "WEST"]
"""
Name of a direction on the screen of a surface.
"""

ColorValue: TypeAlias = str
"""
A color written as `#RRGGBB`.
"""


class ProgramConfig(TypedDict, total=False):
    """
    Engine settings a program can carry. See `GeometryConfig` for what each one does.
    """

    topAnchor: SideName
    """
    The side face the top face is lined up with.
    """

    floor: int
    """
    Row of the floor objects cannot go below.
    """


class ShapePixelDefinition(TypedDict):
    """
    One pixel of an object's shape: `dx` cells to the right and `dy` cells down from the center of the object, as
    seen when it faces north (the shape turns with the object). Without a color it takes the color of the object.
    """

    dx: int
    """
    Cells to the right of the center, when the object faces north.
    """

    dy: int
    """
    Cells down from the center, when the object faces north.
    """

    color: NotRequired[ColorValue]
    """
    Color of this pixel. The object's own color when omitted.
    """


class StartTrigger(TypedDict):
    """
    Runs once, as soon as the program starts.
    """

    type: Literal["start"]
    """
    Always "start".
    """


class EveryTrigger(TypedDict):
    """
    Runs again every `seconds`; a run that is still going when the next one is due is skipped.
    """

    type: Literal["every"]
    """
    Always "every".
    """

    seconds: float
    """
    Time between starts.
    """


Trigger: TypeAlias = StartTrigger | EveryTrigger
"""
The event that starts a script.
"""


class Script(TypedDict):
    """
    A stack of blocks and the event that starts it.
    """

    trigger: Trigger
    """
    The event that starts the script.
    """

    blocks: "list[Block]"
    """
    The blocks the script runs, in order.
    """


class Program(TypedDict):
    """
    A complete program.
    """

    version: Literal[1]
    """
    Version of the program format.
    """

    config: NotRequired[ProgramConfig]
    """
    Engine settings for this program.
    """

    objects: NotRequired["list[CreateCommand]"]
    """
    Objects that exist when the program starts, created in this order before any script runs. They are `create`
    blocks, with names that are not repeated. Scripts act on them by name.
    """

    scripts: list[Script]
    """
    The scripts of the program.
    """
