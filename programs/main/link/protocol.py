"""
The messages of the cube socket. Mirror of `CubeMessage` in kuv-api and of `kuv-client/src/app/cube/link/protocol.ts`.

Every message, in both directions, is one JSON text frame with the same shape. A client sends commands to the cube, the
cube sends events to its clients, and the server sends its own notices.
"""

from typing import Any, NotRequired, TypedDict


class Message(TypedDict):
    """
    One frame of the socket.
    """

    name: str
    """
    What the message is, e.g. "message" or "reply".
    """

    id: NotRequired[str]
    """
    Identifier of this message. The server gives one to every command it forwards.
    """

    replyTo: NotRequired[str]
    """
    Id of the message this one answers.
    """

    payload: NotRequired[dict[str, Any]]
    """
    The data of the message; its shape depends on the name.
    """


COMMAND_MESSAGE = "message"
"""
Command: a user wrote a text to the cube. Payload: `{"text": str}`.
"""

EVENT_REPLY = "reply"
"""
Event: the cube answers a text. Payload: `{"text": str}`.
"""

EVENT_ERROR = "error"
"""
Event: the cube could not do a command. Payload: `{"code": str, "message": str}`.
"""

ERROR_UNKNOWN_COMMAND = "unknown_command"
"""
Error code: the cube does not know the command.
"""

ERROR_INVALID_PAYLOAD = "invalid_payload"
"""
Error code: the command's payload is not what the command needs.
"""

ERROR_FAILED = "failed"
"""
Error code: the command was understood but failed.
"""


class CommandError(Exception):
    """
    A command that cannot be done, with a code the client can act on. The link reports it as an "error" event.
    """

    def __init__(self, code: str, message: str) -> None:
        """
        Builds the error from its code and a text for the user.
        """
        super().__init__(message)

        self.code = code
        """
        Which kind of failure it is, one of the ERROR_ constants.
        """
