"""
What the cube does for each command it can receive. A command is a handler registered under its name; the handler gets
the payload and returns the events to send back, so new commands (a new program, an animation) are new handlers and
nothing else in the link changes.
"""

from typing import Any, Awaitable, Callable, TypeAlias

from programs.main.link.protocol import COMMAND_MESSAGE, ERROR_INVALID_PAYLOAD, ERROR_UNKNOWN_COMMAND, EVENT_ERROR, EVENT_REPLY, CommandError, Message


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


def default_commands() -> CommandRouter:
    """
    The router with every command the cube knows.
    """
    router = CommandRouter()

    router.register(COMMAND_MESSAGE, answer_message)

    return router
