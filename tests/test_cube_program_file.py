"""
Tests for the program file: a program and its environment as the web app sends them.
"""

import unittest

from programs.main.cube import FACE_RESOLUTION, ProgramError, read_program_file


PROGRAM = {"version": 1, "scripts": [{"trigger": {"type": "start"}, "blocks": [{"op": "wait", "seconds": 1}]}]}
"""
A small valid program.
"""

RED_FACE = ["#ff0000"] * (FACE_RESOLUTION * FACE_RESOLUTION)
"""
A picture of one face, all red, as a file writes it.
"""


class ReadProgramFileTest(unittest.TestCase):
    """
    What `read_program_file` accepts and what it gives back.
    """

    def test_file_without_environment(self) -> None:
        """
        A file with only a program gives the program and no environment.
        """
        loaded = read_program_file({"version": 1, "program": PROGRAM})

        self.assertEqual(loaded["program"], PROGRAM)
        self.assertNotIn("environment", loaded)

    def test_pictures_become_packed_colors(self) -> None:
        """
        The `#rrggbb` colors of a face become the numbers the engine uses.
        """
        loaded = read_program_file({"version": 1, "program": PROGRAM, "environment": {"background": {"FRONT": RED_FACE}}})

        self.assertEqual(loaded["environment"]["background"]["FRONT"][0], 0xFF0000)

    def test_settings_the_engine_does_not_use_are_checked_and_left_out(self) -> None:
        """
        Named backgrounds, the start background and the brightness are accepted but not passed on.
        """
        environment = {
            "backgrounds": [{"name": "Background 1", "images": {"FRONT": RED_FACE}}],
            "startBackground": "Background 1",
            "brightness": {"background": 0.5},
        }

        loaded = read_program_file({"version": 1, "program": PROGRAM, "environment": environment})

        self.assertEqual(loaded["environment"], {})

    def test_wrong_version_is_rejected(self) -> None:
        """
        A file of another version is not read.
        """
        with self.assertRaisesRegex(ProgramError, "programFile.version"):
            read_program_file({"version": 2, "program": PROGRAM})

    def test_invalid_program_is_rejected(self) -> None:
        """
        The program inside is validated.
        """
        with self.assertRaises(ProgramError):
            read_program_file({"version": 1, "program": {"version": 1}})

    def test_picture_of_the_wrong_size_is_rejected(self) -> None:
        """
        A face needs exactly one color per pixel.
        """
        with self.assertRaisesRegex(ProgramError, "environment.background.FRONT"):
            read_program_file({"version": 1, "program": PROGRAM, "environment": {"background": {"FRONT": ["#ff0000"]}}})

    def test_unknown_face_is_rejected(self) -> None:
        """
        A picture for a face the cube does not have is an error.
        """
        with self.assertRaisesRegex(ProgramError, "is not a face"):
            read_program_file({"version": 1, "program": PROGRAM, "environment": {"background": {"BOTTOM": RED_FACE}}})


if __name__ == "__main__":
    unittest.main()
