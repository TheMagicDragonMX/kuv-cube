"""
LAYER: world.

The source of truth for *what exists* on the cube: the objects, and the background layer that holds the pictures and
colors behind the objects.

    commands --change--> World <--read by-- renderer

The world never draws anything and never decides when things happen; it only stores things and keeps a `version`
that goes up on every change, so the renderer can skip frames where nothing changed.
"""

from typing import TypedDict, ValuesView

from programs.main.cube.errors import EngineError
from programs.main.cube.geometry.geometry import CubeGeometry, GeometryConfig, Pose
from programs.main.cube.state.cube_state import Color, CubeState
from programs.main.cube.world.cube_object import CubeObject


class ObjectChanges(TypedDict, total=False):
    """
    The parts of an object a command can change.
    """

    pose: Pose
    """
    Where the object is and which way it faces.
    """

    color: Color
    """
    Color of the pixels that do not have their own.
    """

    visible: bool
    """
    Whether the object is drawn.
    """


class World:
    """
    The objects of the program and the background behind them, placed on the geometry of the cube.
    """

    def __init__(self, config: GeometryConfig | None = None) -> None:
        """
        Builds an empty world with the given geometry settings.
        """
        self.geometry = CubeGeometry(config)
        """
        How the surfaces of this world connect. Fixed for the life of the world, because the poses of the objects
        only make sense with the settings they were created with.
        """

        self.background = CubeState()
        """
        Persistent layer under the objects. It is written by the environment (the pictures the user puts on the
        faces before running) and by the background blocks (a program changing what is behind the objects). The
        renderer copies it first on every frame, so what is painted here stays on the cube.
        """

        self._objects: dict[str, CubeObject] = {}
        """
        Objects by name. A dict remembers insertion order, so objects are drawn in the order they were created
        (later ones on top).
        """

        self._object_changes = 0
        """
        Number of changes made to the objects.
        """

    @property
    def version(self) -> int:
        """
        Goes up whenever the objects or the background change.
        """
        return self._object_changes + self.background.version

    def add(self, cube_object: CubeObject) -> None:
        """
        Adds an object. Its name must not be taken.
        """
        if cube_object["name"] in self._objects:
            raise EngineError(f'There is already an object called "{cube_object["name"]}"')

        self._objects[cube_object["name"]] = cube_object
        self._object_changes += 1

    def get(self, name: str) -> CubeObject:
        """
        Returns the object with a name, or raises if there is none.
        """
        cube_object = self._objects.get(name)

        if cube_object is None:
            raise EngineError(f'There is no object called "{name}"')

        return cube_object

    def update(self, name: str, changes: ObjectChanges) -> None:
        """
        Replaces some properties of an object, keeping its place in the drawing order.
        """
        self._objects[name] = {**self.get(name), **changes}
        self._object_changes += 1

    def remove(self, name: str) -> None:
        """
        Removes an object.
        """
        self.get(name)

        del self._objects[name]
        self._object_changes += 1

    def all(self) -> ValuesView[CubeObject]:
        """
        Every object, in drawing order.
        """
        return self._objects.values()

    def clear(self) -> None:
        """
        Removes every object and blanks the background.
        """
        self._objects.clear()
        self._object_changes += 1
        self.background.fill(0)
