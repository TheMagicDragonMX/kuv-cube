"""
LAYER: blocks (fields).

The kinds of value a block field can take, and ready-made field descriptions to use in block schemas. The validator
knows how to check each kind; a Blockly block uses the same list to know which input to show.

To add a new kind of value, add it to `FieldKind` here and teach `validate_field` in `program/validate_program.py`
how to check it.
"""

from typing import Literal, NotRequired, TypeAlias, TypedDict


FieldKind: TypeAlias = Literal[
    "text", "face", "faces", "heading", "step", "color", "integer", "count", "seconds", "shape", "image", "blocks"
]
"""
Kind of value a field takes.

    text      non-empty string
    face      a FaceName
    faces     non-empty list of FaceName
    heading   a HeadingName
    step      'up' | 'right' | 'down' | 'left'
    color     '#RRGGBB'
    integer   any whole number (cells can be negative: shapes may overflow a face)
    count     whole number, zero or more
    seconds   number, zero or more
    shape     non-empty list of { dx, dy, color? }: the pixels of an object
    image     the pixels of one face: FACE_RESOLUTION * FACE_RESOLUTION '#RRGGBB', row after row
    blocks    nested list of blocks
"""


class FieldSchema(TypedDict):
    """
    One field of a block.
    """

    kind: FieldKind
    """
    What kind of value the field takes.
    """

    optional: NotRequired[bool]
    """
    True when the field may be left out.
    """


BlockSchema: TypeAlias = dict[str, FieldSchema]
"""
Fields of a block, by name (without `op`).
"""

FIELD: dict[FieldKind, FieldSchema] = {
    "text": {"kind": "text"},
    "face": {"kind": "face"},
    "faces": {"kind": "faces"},
    "heading": {"kind": "heading"},
    "step": {"kind": "step"},
    "color": {"kind": "color"},
    "integer": {"kind": "integer"},
    "count": {"kind": "count"},
    "seconds": {"kind": "seconds"},
    "shape": {"kind": "shape"},
    "image": {"kind": "image"},
    "blocks": {"kind": "blocks"},
}
"""
A required field of each kind. Use these in block schemas: `"x": FIELD["integer"]`.
"""


def optional(field: FieldSchema) -> FieldSchema:
    """
    The same field, but the block may leave it out: `"heading": optional(FIELD["heading"])`.
    """
    return {**field, "optional": True}
