"""
Remembers the brightness of the panels between boots, in a file of the cube's state folder.
"""

import logging
import os
from pathlib import Path

from programs.common.matrix_protocol import DEFAULT_BRIGHTNESS, clean_brightness


logger = logging.getLogger(__name__)
"""
Where this module reports problems.
"""

STATE_DIR = Path(os.environ.get("KUV_STATE_DIR", "/var/lib/kuv"))
"""
Folder where the cube remembers things between boots (the same one setup keeps the PIN in).
"""

BRIGHTNESS_FILE = "brightness"
"""
Name of the file, inside the state folder, that holds the brightness as a whole percent.
"""


def load_brightness(state_dir: Path = STATE_DIR) -> int:
    """
    The brightness saved last time, or DEFAULT_BRIGHTNESS when none was saved or the file is not a valid percent.
    """
    try:
        saved = clean_brightness(int((state_dir / BRIGHTNESS_FILE).read_text().strip()))

    except (OSError, ValueError):
        saved = None

    return DEFAULT_BRIGHTNESS if saved is None else saved


def save_brightness(brightness: int, state_dir: Path = STATE_DIR) -> None:
    """
    Remembers the brightness for the next boot. A failure is logged: the panels keep the new brightness anyway.
    """
    try:
        state_dir.mkdir(parents=True, exist_ok=True)

        (state_dir / BRIGHTNESS_FILE).write_text(f"{brightness}\n")

    except OSError:
        logger.exception("Could not save the brightness")
