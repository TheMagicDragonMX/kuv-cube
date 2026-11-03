"""
How the programs write down what they do.

Everything goes to the terminal's error output, which systemd collects in the Pi's journal. From a
laptop, scripts/logs.sh streams it. Never log secrets (WiFi passwords): log what happened, not the
values that were sent.
"""

import logging


LOG_FORMAT = "%(levelname)s %(name)s: %(message)s"
"""
One line per event; the journal adds the time and the program's name.
"""


def configure_logging() -> None:
    """
    Sets up logging for a program. Call it once, first thing.
    """
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
