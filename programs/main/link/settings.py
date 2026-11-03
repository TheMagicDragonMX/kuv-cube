"""
Where the server is and who this cube is. Everything comes from the environment, which systemd fills from /etc/kuv/kuv.env (see deploy/kuv.env.example).

  KUV_SERVER_URL    base address of the server, e.g. ws://192.168.1.20:5038 (the link is off without it)
  KUV_CUBE_SECRET   the secret the server expects from cubes (`Cubes:Secret` in kuv-api)
  KUV_CUBE_ID       this cube's id (default: the machine id)
"""

import os
from pathlib import Path
from typing import TypedDict
from urllib.parse import quote


MACHINE_ID_PATH = Path("/etc/machine-id")
"""
Identifier systemd creates once per installation; the cube id defaults to it.
"""

SOCKET_PATH = "/ws/cube"
"""
Path of the server's cube endpoint.
"""


class LinkSettings(TypedDict):
    """
    What the link needs to reach the server.
    """

    url: str
    """
    Full address of the cube endpoint, with the cube id in its query.
    """

    secret: str
    """
    Sent as the bearer token to prove this is a cube.
    """

    cube_id: str
    """
    Identifier of this cube, the one users pick in the web app.
    """


def cube_id() -> str:
    """
    The id of this cube: KUV_CUBE_ID, or the machine id.
    """
    configured = os.environ.get("KUV_CUBE_ID", "").strip()

    if configured:
        return configured

    try:
        return MACHINE_ID_PATH.read_text().strip()

    except OSError:
        return ""


def load_settings() -> LinkSettings | None:
    """
    The settings from the environment, or None when the link is not configured (no server, no secret or no id).
    """
    server = os.environ.get("KUV_SERVER_URL", "").strip().rstrip("/")
    secret = os.environ.get("KUV_CUBE_SECRET", "").strip()
    identifier = cube_id()

    if not server or not secret or not identifier:
        return None

    return {"url": f"{server}{SOCKET_PATH}?cubeId={quote(identifier, safe='')}", "secret": secret, "cube_id": identifier}
