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

COMMAND_RUN_PROGRAM = "run_program"
"""
Command: run a program on the cube, replacing the one it runs. Payload: a program file, `{"version": 1, "program": {...},
"environment": {...}}` (see `programs/main/cube/program_file/`). Answered with "program_status".
"""

COMMAND_STOP_PROGRAM = "stop_program"
"""
Command: stop the program; the cube keeps what it shows. No payload. Answered with "program_status".
"""

COMMAND_SET_BRIGHTNESS = "set_brightness"
"""
Command: change how bright the LED panels are. Payload: `{"percent": int}`, a whole percent from 1 to 100. The cube
remembers it across reboots. Answered with "brightness".
"""

COMMAND_GET_BRIGHTNESS = "get_brightness"
"""
Command: ask how bright the LED panels are. No payload. Answered with "brightness".
"""

EVENT_REPLY = "reply"
"""
Event: the cube answers a text. Payload: `{"text": str}`.
"""

EVENT_PROGRAM_STATUS = "program_status"
"""
Event: whether the cube is running a program, after "run_program" or "stop_program". Payload: `{"running": bool}`.
"""

EVENT_BRIGHTNESS = "brightness"
"""
Event: how bright the LED panels are, after "set_brightness" or "get_brightness". Payload: `{"percent": int}`. The
server sends it to every client of the cube, so they all show the same value.
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

ERROR_INVALID_PROGRAM = "invalid_program"
"""
Error code: the program sent with "run_program" is not one the cube can run; the message says where.
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
