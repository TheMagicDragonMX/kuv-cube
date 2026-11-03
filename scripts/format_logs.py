#!/usr/bin/env python3
"""
Turns the Pi's journal into one tidy line per event. Used by logs.sh, on your laptop.

It reads journalctl's JSON output (one entry per line) from the standard input and prints:

    19:28:52  main      Started, painting the panels blue
    19:30:10  setup     WARN auth refused: unauthorized (Wrong PIN)

The time is shown in this computer's time zone, the source is the program the line is about (not
"systemd[1]" or "python[123]"), and the logger prefix the programs add is dropped.
"""

import argparse
import json
import re
import sys
from datetime import datetime


SOURCE_NAMES = {
    "kuv-matrix.service": "matrix",
    "kuv-setup.service": "setup",
    "kuv-cube.service": "main",
    "bluetooth.service": "bluetooth",
    "NetworkManager.service": "wifi",
}
"""
What each unit is called on screen.
"""

IDENTIFIER_NAMES = {
    "kuv-matrix": "matrix",
    "kuv-setup": "setup",
    "kuv-main": "main",
}
"""
What each program's log label is called on screen.
"""

SOURCE_COLORS = {
    "matrix": "36",
    "setup": "35",
    "main": "32",
    "bluetooth": "34",
    "wifi": "33",
}
"""
ANSI color of each source: cyan, magenta, green, blue, yellow.
"""

SOURCE_WIDTH = 9
"""
Characters reserved for the source, so the messages line up.
"""

DIM = "90"
"""
ANSI color for the time and for lines that systemd wrote about a program.
"""

WARNING_COLOR = "33"
"""
ANSI color of warnings.
"""

ERROR_COLOR = "31"
"""
ANSI color of errors.
"""

LOG_LINE = re.compile(r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL) [\w.]+: (.*)$", re.DOTALL)
"""
How the programs write a line (see programs/common/logs.py): the level, the logger, then the message.
"""

LEVEL_FROM_PRIORITY = {0: "ERROR", 1: "ERROR", 2: "ERROR", 3: "ERROR", 4: "WARNING"}
"""
Journal priorities that deserve a mark when a line carries no level of its own.
"""


def paint(text: str, code: str, color: bool) -> str:
    """
    The text in an ANSI color, or unchanged when colors are off.
    """
    return f"\033[{code}m{text}\033[0m" if color else text


def text_of(entry: dict) -> str:
    """
    The message of a journal entry. Messages that are not plain text arrive as lists of bytes.
    """
    message = entry.get("MESSAGE", "")

    if isinstance(message, list):
        return bytes(message).decode(errors="replace")

    return str(message)


def source_of(entry: dict) -> str:
    """
    Which program a journal entry is about.
    """
    identifier = entry.get("SYSLOG_IDENTIFIER", "")

    if identifier in IDENTIFIER_NAMES:
        return IDENTIFIER_NAMES[identifier]

    # What systemd says about a program (starting, stopped...) names it in UNIT.
    unit = entry.get("UNIT") or entry.get("_SYSTEMD_UNIT") or identifier or "system"

    return SOURCE_NAMES.get(unit, unit.removesuffix(".service"))


def level_and_message(entry: dict) -> tuple[str, str]:
    """
    The level (INFO, WARNING, ERROR...) of an entry and its message without the logger prefix.
    """
    message = text_of(entry)
    match = LOG_LINE.match(message)

    if match:
        return match.group(1), match.group(2)

    try:
        priority = int(entry.get("PRIORITY", 6))

    except ValueError:
        priority = 6

    return LEVEL_FROM_PRIORITY.get(priority, "INFO"), message


def render(entry: dict, color: bool) -> str:
    """
    One line for a journal entry.
    """
    moment = datetime.fromtimestamp(int(entry.get("__REALTIME_TIMESTAMP", 0)) / 1_000_000)
    source = source_of(entry)
    level, message = level_and_message(entry)

    if entry.get("SYSLOG_IDENTIFIER") == "systemd":
        message = paint(message, DIM, color)

    elif level in ("WARNING", "ERROR", "CRITICAL"):
        code = WARNING_COLOR if level == "WARNING" else ERROR_COLOR
        tag = "WARN" if level == "WARNING" else "ERROR"

        message = paint(f"{tag} {message}", code, color)

    return "  ".join((
        paint(moment.strftime("%H:%M:%S"), DIM, color),
        paint(source.ljust(SOURCE_WIDTH), SOURCE_COLORS.get(source, "37"), color),
        message,
    ))


def main() -> None:
    """
    Reads entries from the standard input and prints a line for each, until it ends.
    """
    parser = argparse.ArgumentParser(description="Tidy up the Kuv cube's journal.")
    parser.add_argument("--no-color", action="store_true", help="plain text, no colors")
    parser.add_argument("--cr", action="store_true", help="end lines with a carriage return too")
    arguments = parser.parse_args()

    color = not arguments.no_color
    ending = "\r\n" if arguments.cr else "\n"
    day = None

    try:
        for line in sys.stdin:
            try:
                entry = json.loads(line)

            except ValueError:
                continue

            moment = datetime.fromtimestamp(int(entry.get("__REALTIME_TIMESTAMP", 0)) / 1_000_000)

            if moment.date() != day:
                day = moment.date()

                sys.stdout.write(paint(f"── {moment.strftime('%A %-d %B')} ──", DIM, color) + ending)

            sys.stdout.write(render(entry, color) + ending)
            sys.stdout.flush()

    except (KeyboardInterrupt, BrokenPipeError):
        pass


if __name__ == "__main__":
    main()
