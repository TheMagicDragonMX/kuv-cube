"""
Who this cube is: its advertised name, its PIN and its software version.
"""

import hashlib
import secrets
import socket
import subprocess
from pathlib import Path

from setup.protocol import DEVICE_NAME_PREFIX


MACHINE_ID_PATH = Path("/etc/machine-id")
"""
Identifier systemd creates once per installation; it makes the name stable and unique.
"""

PIN_LENGTH = 6
"""
Digits in a generated PIN.
"""

PIN_FILE = "setup-pin"
"""
Name of the file, inside the state folder, that remembers the PIN.
"""


def cube_name() -> str:
    """
    The advertised name: "Kuv-" and four hex digits taken from the machine id.
    """
    try:
        source = MACHINE_ID_PATH.read_text().strip()

    except OSError:
        source = hashlib.sha1(socket.gethostname().encode()).hexdigest()

    return f"{DEVICE_NAME_PREFIX}-{source[-4:].upper()}"


def load_pin(state_dir: Path, override: str | None = None) -> str | None:
    """
    The PIN pages must send, created and remembered on first use.

    `override` wins when given; an empty string turns the PIN off.
    """
    if override is not None:
        return override or None

    path = state_dir / PIN_FILE

    try:
        pin = path.read_text().strip()

        if pin:
            return pin

    except OSError:
        pass

    pin = "".join(secrets.choice("0123456789") for _ in range(PIN_LENGTH))

    state_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(pin + "\n")
    path.chmod(0o600)

    return pin


def software_version(repo: Path) -> str:
    """
    The short git commit the cube runs, or "dev" when it cannot be read.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )

        return result.stdout.strip() or "dev"

    except (OSError, subprocess.SubprocessError):
        return "dev"
