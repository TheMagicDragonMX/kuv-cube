"""
What the cube does for each command it can receive. A command is a handler registered under its name; the handler gets
the payload and returns the events to send back, so new commands (a new program, an animation) are new handlers and
nothing else in the link changes.
"""

import asyncio
from typing import Any, Awaitable, Callable, TypeAlias

from programs.common.matrix_client import MatrixClient
from programs.common.matrix_protocol import MAX_BRIGHTNESS, MIN_BRIGHTNESS, clean_brightness
from programs.main.cube import CubePlayer, EngineError, ProgramError, read_program_file
from programs.main.link.protocol import (
    COMMAND_GET_BRIGHTNESS,
    COMMAND_MESSAGE,
    COMMAND_RUN_PROGRAM,
    COMMAND_SET_BRIGHTNESS,
    COMMAND_STOP_PROGRAM,
    ERROR_FAILED,
    ERROR_INVALID_PAYLOAD,
    ERROR_INVALID_PROGRAM,
    ERROR_UNKNOWN_COMMAND,
    EVENT_BRIGHTNESS,
    EVENT_ERROR,
    EVENT_PROGRAM_STATUS,
    EVENT_REPLY,
    CommandError,
    Message,
)


Handler: TypeAlias = Callable[[dict[str, Any]], Awaitable[list[Message]]]
"""
Does one command: takes its payload and returns the events to send as the answer, possibly none.
"""


class CommandRouter:
    """
    Finds the handler of each command and turns its failures into "error" events.
    """

    def __init__(self) -> None:
        """
        Starts with no commands.
        """
        self._handlers: dict[str, Handler] = {}
        """
        The handler of each command, by name.
        """

    def register(self, name: str, handler: Handler) -> None:
        """
        Makes the cube answer the command `name` with `handler`.
        """
        self._handlers[name] = handler

    async def handle(self, message: Message) -> list[Message]:
        """
        Does a command and returns the events to send back. Never raises: a command that cannot be done is answered with
        an "error" event.
        """
        handler = self._handlers.get(message["name"])

        if handler is None:
            return [error_event(ERROR_UNKNOWN_COMMAND, f"The cube does not know the command {message['name']!r}.")]

        payload = message.get("payload")

        try:
            return await handler(payload if isinstance(payload, dict) else {})

        except CommandError as error:
            return [error_event(error.code, str(error))]


def error_event(code: str, text: str) -> Message:
    """
    The "error" event for a command that could not be done.
    """
    return {"name": EVENT_ERROR, "payload": {"code": code, "message": text}}


async def answer_message(payload: dict[str, Any]) -> list[Message]:
    """
    Mock conversation: answers the text a user wrote. Only here to show the round trip; real commands replace it.
    """
    text = payload.get("text")

    if not isinstance(text, str) or not text.strip():
        raise CommandError(ERROR_INVALID_PAYLOAD, "A message needs a text.")

    return [{"name": EVENT_REPLY, "payload": {"text": f"Beep boop! The cube heard: {text.strip()}"}}]


def program_status(player: CubePlayer) -> Message:
    """
    The "program_status" event: whether the player runs a program now.
    """
    return {"name": EVENT_PROGRAM_STATUS, "payload": {"running": player.running}}


def run_program_handler(player: CubePlayer) -> Handler:
    """
    The handler of "run_program": shows the environment of the program file and runs its program on `player`.
    """

    async def run_program(payload: dict[str, Any]) -> list[Message]:
        """
        Runs the program file in the payload, replacing what runs. An invalid file leaves the cube as it was.
        """
        try:
            # Checking a big program file takes a while, so it runs in a thread; only playing it touches the player.
            loaded = await asyncio.to_thread(read_program_file, payload)

            player.set_environment(loaded.get("environment"))
            player.play(loaded["program"], checked=True)

        except (ProgramError, EngineError) as error:
            raise CommandError(ERROR_INVALID_PROGRAM, str(error)) from error

        return [program_status(player)]

    return run_program


def stop_program_handler(player: CubePlayer) -> Handler:
    """
    The handler of "stop_program": stops what `player` runs.
    """

    async def stop_program(payload: dict[str, Any]) -> list[Message]:
        """
        Stops the scripts; the cube keeps what it shows.
        """
        player.stop()

        return [program_status(player)]

    return stop_program


def brightness_event(percent: int) -> Message:
    """
    The "brightness" event: how bright the panels are.
    """
    return {"name": EVENT_BRIGHTNESS, "payload": {"percent": percent}}


def set_brightness_handler(matrix: MatrixClient) -> Handler:
    """
    The handler of "set_brightness": asks the matrix program, through `matrix`, to change the brightness.
    """

    async def set_brightness(payload: dict[str, Any]) -> list[Message]:
        """
        Changes the brightness to the percent in the payload.
        """
        percent = clean_brightness(payload.get("percent"))

        if percent is None:
            raise CommandError(
                ERROR_INVALID_PAYLOAD, f"The brightness must be a whole percent from {MIN_BRIGHTNESS} to {MAX_BRIGHTNESS}."
            )

        if not matrix.set_brightness(percent):
            raise CommandError(ERROR_FAILED, "The LED panels are not ready.")

        return [brightness_event(percent)]

    return set_brightness


def get_brightness_handler(matrix: MatrixClient) -> Handler:
    """
    The handler of "get_brightness": answers how bright the matrix program says the panels are.
    """

    async def get_brightness(payload: dict[str, Any]) -> list[Message]:
        """
        Answers the brightness now.
        """
        if matrix.brightness is None:
            raise CommandError(ERROR_FAILED, "The LED panels are not ready.")

        return [brightness_event(matrix.brightness)]

    return get_brightness


def default_commands(player: CubePlayer | None = None, matrix: MatrixClient | None = None) -> CommandRouter:
    """
    The router with every command the cube knows. The program commands need the `player` that shows programs on the
    panels, and the brightness commands the `matrix` connection; without them the cube only chats.
    """
    router = CommandRouter()

    router.register(COMMAND_MESSAGE, answer_message)

    if player is not None:
        router.register(COMMAND_RUN_PROGRAM, run_program_handler(player))
        router.register(COMMAND_STOP_PROGRAM, stop_program_handler(player))

    if matrix is not None:
        router.register(COMMAND_SET_BRIGHTNESS, set_brightness_handler(matrix))
        router.register(COMMAND_GET_BRIGHTNESS, get_brightness_handler(matrix))

    return router
