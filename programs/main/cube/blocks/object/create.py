"""
BLOCK: create (object).

Creates a new visible object. Without `pixels` it is a single pixel. With `costumes` it can switch looks later (see
`set_costume.py`); it starts with its own color and pixels, which are those of the first costume.
"""

from typing import Literal, NotRequired, TypedDict

from programs.main.cube.blocks.block_definition import CommandDefinition
from programs.main.cube.blocks.fields import FIELD, optional
from programs.main.cube.program.names import FACE_BY_NAME, HEADING_BY_NAME, parse_color
from programs.main.cube.program.program import ColorValue, CostumeDefinition, FaceName, HeadingName, ShapePixelDefinition
from programs.main.cube.world.cube_object import SINGLE_PIXEL, CubeObject, ShapePixel
from programs.main.cube.world.world import World


class CreateCommand(TypedDict):
    """
    Creates an object. The name must be new. The heading defaults to north.

    `pixels` is the shape, around the center cell given by `face`, `x` and `y`. It defaults to a single pixel on the
    center. For a plus sign:

        [{"dx": 0, "dy": 0}, {"dx": 0, "dy": -1}, {"dx": 1, "dy": 0}, {"dx": 0, "dy": 1}, {"dx": -1, "dy": 0}]
    """

    op: Literal["create"]
    """
    Identifies the command.
    """

    name: str
    """
    Name of the new object. It must not be taken.
    """

    face: FaceName
    """
    The face the object starts on.
    """

    x: int
    """
    Column of the object's center cell.
    """

    y: int
    """
    Row of the object's center cell.
    """

    color: ColorValue
    """
    The object's color.
    """

    heading: NotRequired[HeadingName]
    """
    Where the object faces. Defaults to north.
    """

    pixels: NotRequired[list[ShapePixelDefinition]]
    """
    The cells of the shape around its center. Defaults to a single pixel.
    """

    costumes: NotRequired[list[CostumeDefinition]]
    """
    The looks the object can switch between. The first one is how it starts, so `color` and `pixels` are the ones of
    the first costume.
    """


def shape_of(pixels: list[ShapePixelDefinition] | None) -> tuple[ShapePixel, ...]:
    """
    The shape an object is drawn with, from the pixels of a block. Without pixels it is a single pixel.
    """
    if pixels is None:
        return SINGLE_PIXEL

    return tuple(
        {"dx": pixel["dx"], "dy": pixel["dy"], "color": parse_color(pixel["color"]) if "color" in pixel else None}
        for pixel in pixels
    )


def apply(world: World, command: CreateCommand) -> None:
    """
    Adds a visible object, with the shape, pose and color of the command, and its costumes.
    """
    heading = command.get("heading")

    cube_object: CubeObject = {
        "name": command["name"],
        "shape": shape_of(command.get("pixels")),
        "pose": world.geometry.place(
            {
                "face": FACE_BY_NAME[command["face"]],
                "x": command["x"],
                "y": command["y"],
                "heading": HEADING_BY_NAME[heading] if heading else None,
            }
        ),
        "color": parse_color(command["color"]),
        "visible": True,
    }

    costumes = command.get("costumes")

    if costumes is not None:
        cube_object["costumes"] = tuple(
            {"name": costume["name"], "color": parse_color(costume["color"]), "shape": shape_of(costume.get("pixels"))}
            for costume in costumes
        )
        cube_object["costume"] = costumes[0]["name"]

    world.add(cube_object)


create_block: CommandDefinition = {
    "schema": {
        "name": FIELD["text"],
        "face": FIELD["face"],
        "x": FIELD["integer"],
        "y": FIELD["integer"],
        "color": FIELD["color"],
        "heading": optional(FIELD["heading"]),
        "pixels": optional(FIELD["shape"]),
        "costumes": optional(FIELD["costumes"]),
    },
    "apply": apply,
}
"""
The shape of the command, its fields, and how it adds the object to the world.
"""
