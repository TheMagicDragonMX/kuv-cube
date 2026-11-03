"""
Tests for the log formatter that scripts/logs.sh runs on the laptop.
"""

import importlib.util
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("format_logs", Path(__file__).resolve().parent.parent / "scripts" / "format_logs.py")
"""
Where to load the formatter from: scripts/ is not a package.
"""

format_logs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(format_logs)


def entry(message: str, **fields) -> dict:
    """
    A journal entry, as journalctl prints it in JSON.
    """
    return {"MESSAGE": message, "__REALTIME_TIMESTAMP": "1762110532000000", "SYSLOG_IDENTIFIER": "kuv-setup", **fields}


class FormatLogsTest(unittest.TestCase):
    """
    Entries become one short line that says what and who, without journal noise.
    """

    def test_program_line_drops_the_logger_prefix(self) -> None:
        """
        "INFO programs.setup.dispatcher: auth ok" is shown as just "auth ok", under "setup".
        """
        line = format_logs.render(entry("INFO programs.setup.dispatcher: auth ok"), False)

        self.assertTrue(line.endswith("setup      auth ok"), line)
        self.assertNotIn("programs", line)
        self.assertNotIn("INFO", line)

    def test_warnings_and_errors_are_marked(self) -> None:
        """
        Warnings and errors keep a visible tag.
        """
        self.assertIn("WARN auth refused", format_logs.render(entry("WARNING programs.x: auth refused"), False))
        self.assertIn("ERROR boom", format_logs.render(entry("ERROR programs.x: boom"), False))

    def test_systemd_lines_are_named_after_the_program(self) -> None:
        """
        What systemd says about kuv-cube.service is shown as coming from "main", not "systemd[1]".
        """
        line = format_logs.render(entry("Started kuv-cube.service - Kuv cube.", SYSLOG_IDENTIFIER="systemd", UNIT="kuv-cube.service"), False)

        self.assertIn("main", line)
        self.assertNotIn("systemd", line)

    def test_old_lines_without_a_label_are_found_by_unit(self) -> None:
        """
        Lines from before the labels existed ("python") are still shown under the right program.
        """
        line = format_logs.render(entry("INFO programs.matrix.server: ok", SYSLOG_IDENTIFIER="python", _SYSTEMD_UNIT="kuv-matrix.service"), False)

        self.assertIn("matrix", line)

    def test_system_services_get_short_names(self) -> None:
        """
        Bluetooth and NetworkManager are shown as "bluetooth" and "wifi", and priority marks errors.
        """
        wifi = format_logs.render(entry("device (wlan0): state change", SYSLOG_IDENTIFIER="NetworkManager", _SYSTEMD_UNIT="NetworkManager.service"), False)
        failure = format_logs.render(entry("oh no", SYSLOG_IDENTIFIER="bluetoothd", _SYSTEMD_UNIT="bluetooth.service", PRIORITY="3"), False)

        self.assertIn("wifi", wifi)
        self.assertIn("ERROR oh no", failure)

    def test_colors_only_when_asked(self) -> None:
        """
        Plain output has no escape codes; colored output does.
        """
        self.assertNotIn("\033", format_logs.render(entry("INFO x: hi"), False))
        self.assertIn("\033[", format_logs.render(entry("INFO x: hi"), True))

    def test_messages_that_are_bytes_are_decoded(self) -> None:
        """
        The journal sends non-text messages as lists of byte values.
        """
        self.assertIn("hi", format_logs.render(entry(list(b"INFO x: hi")), False))
