"""
CATEGORY: object.

Blocks that change the objects of the world: create them, move them, recolor them, change their costume, show, hide
or remove them.

To add a block to this category: write its file in this folder, add its type to the union and its definition to the
table below.
"""

from typing import TypeAlias

from programs.main.cube.blocks.block_definition import CommandDefinition
from programs.main.cube.blocks.object.create import CreateCommand, create_block
from programs.main.cube.blocks.object.delete import DeleteCommand, delete_block
from programs.main.cube.blocks.object.hide import HideCommand, hide_block
from programs.main.cube.blocks.object.move import MoveCommand, move_block
from programs.main.cube.blocks.object.move_to import MoveToCommand, move_to_block
from programs.main.cube.blocks.object.next_costume import NextCostumeCommand, next_costume_block
from programs.main.cube.blocks.object.point_up import PointUpCommand, point_up_block
from programs.main.cube.blocks.object.set_color import SetColorCommand, set_color_block
from programs.main.cube.blocks.object.set_costume import SetCostumeCommand, set_costume_block
from programs.main.cube.blocks.object.show import ShowCommand, show_block


ObjectCommand: TypeAlias = (
    CreateCommand
    | MoveCommand
    | MoveToCommand
    | SetColorCommand
    | ShowCommand
    | HideCommand
    | DeleteCommand
    | PointUpCommand
    | SetCostumeCommand
    | NextCostumeCommand
)
"""
A block that changes the objects of the world.
"""

OBJECT_BLOCKS: dict[str, CommandDefinition] = {
    "create": create_block,
    "move": move_block,
    "moveTo": move_to_block,
    "setColor": set_color_block,
    "show": show_block,
    "hide": hide_block,
    "delete": delete_block,
    "pointUp": point_up_block,
    "setCostume": set_costume_block,
    "nextCostume": next_costume_block,
}
"""
The definition of each object command, by `op`.
"""
