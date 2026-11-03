"""
CATEGORY: background.

Blocks that change what is behind the objects: the pictures and colors of the faces. They are the only blocks that
write to the world's background layer (besides the environment, which is where the cube starts).
"""

from typing import TypeAlias

from programs.main.cube.blocks.background.set_background_color import SetBackgroundColorCommand, set_background_color_block
from programs.main.cube.blocks.background.set_background_image import SetBackgroundImageCommand, set_background_image_block
from programs.main.cube.blocks.block_definition import CommandDefinition


BackgroundCommand: TypeAlias = SetBackgroundImageCommand | SetBackgroundColorCommand
"""
A block that changes the background.
"""

BACKGROUND_BLOCKS: dict[str, CommandDefinition] = {
    "setBackgroundImage": set_background_image_block,
    "setBackgroundColor": set_background_color_block,
}
"""
The definition of each background command, by `op`.
"""
