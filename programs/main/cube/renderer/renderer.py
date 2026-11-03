"""
LAYER: renderer.

Turns the world into pixels. This is the only place where "an object at this pose" becomes "this pixel has this
color".

    World --read by--> Renderer --writes--> CubeState (output)

Each frame is built the same way:

    1. start from the background layer (one bulk copy)
    2. draw every visible object on top, in the order they were created, pixel by pixel

Nothing is erased pixel by pixel: because every frame starts from the background, an object that moved simply is not
drawn where it used to be.

The renderer remembers the world version it last drew and does nothing if it has not changed, so a cube with nothing
moving costs nothing per tick.
"""

from programs.main.cube.state.cube_state import CubeState
from programs.main.cube.world.world import World


class Renderer:
    """
    Draws the world onto the cube state, only when the world changed since the last draw.
    """

    def __init__(self, world: World, output: CubeState) -> None:
        """
        Draws `world` onto `output`, which the view reads.
        """
        self._world = world
        """
        What to draw.
        """

        self.output = output
        """
        Where to draw it.
        """

        self._rendered_version = -1
        """
        World version the output currently shows. -1 means nothing has been drawn yet.
        """

    def render(self) -> bool:
        """
        Redraws the output if the world changed since the last call. Returns whether anything was drawn.
        """
        if self._rendered_version == self._world.version:
            return False

        self.output.copy_from(self._world.background)

        geometry = self._world.geometry

        for cube_object in self._world.all():
            if not cube_object["visible"]:
                continue

            for part in cube_object["shape"]:
                # The geometry finds where each pixel of the shape lands, across edges too. Pixels below the last
                # visible row have no cell, so they are simply not drawn.
                pixel = geometry.pixel_at(cube_object["pose"], part["dx"], part["dy"])

                if pixel is not None:
                    color = part.get("color")

                    self.output.set(pixel["face"], pixel["x"], pixel["y"], cube_object["color"] if color is None else color)

        self._rendered_version = self._world.version

        return True
