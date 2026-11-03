"""
LAYER: world (object definition).

What an object is. An object is a small piece of data, not a class with behavior: the commands change it, the
renderer reads it.
"""

from typing import NotRequired, TypedDict

from programs.main.cube.geometry.geometry import Pose
from programs.main.cube.state.cube_state import Color


class ShapePixel(TypedDict):
    """
    One pixel of an object's shape.

    `dx` and `dy` are cells from the center of the object, in the object's own frame: `dx` grows to its right and
    `dy` grows downward, as seen when it faces north. When the object turns (crossing the top face, or created with
    another heading) the shape turns with it. A pixel without a color is drawn with the color of the object.
    """

    dx: int
    """
    Cells to the right of the center, when the object faces north.
    """

    dy: int
    """
    Cells down from the center, when the object faces north.
    """

    color: NotRequired[Color | None]
    """
    Color of this pixel. The object's own color when omitted.
    """


SINGLE_PIXEL: tuple[ShapePixel, ...] = ({"dx": 0, "dy": 0},)
"""
The shape of a plain pixel: just the center.
"""


class CubeObject(TypedDict):
    """
    Something that lives on the cube and can be moved around by a program.

    An object is a set of pixels around a center. The pose is the pose of the center; the geometry finds where every
    other pixel lands, so a shape that reaches over an edge is drawn on the other side of it.
    """

    name: str
    """
    Unique name; commands use it to say which object they act on.
    """

    shape: tuple[ShapePixel, ...]
    """
    Pixels the object is made of, around its center. Later pixels are drawn over earlier ones.
    """

    pose: Pose
    """
    Where the object is and which way it faces. See `Pose`.
    """

    color: Color
    """
    Color of the pixels that do not have their own (0xRRGGBB).
    """

    visible: bool
    """
    Hidden objects still exist and keep moving, but are not drawn.
    """
