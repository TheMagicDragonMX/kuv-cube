"""
Tests for the geometry of the cube: how its faces connect.
"""

import unittest

from programs.main.cube.geometry.geometry import SIDES, STRIP_WIDTH, CubeGeometry, Heading
from programs.main.cube.state.cube_state import FACE_RESOLUTION, Face


def strip(x: int, y: int, heading: Heading = Heading.NORTH) -> dict:
    """
    A pose on the strip of the sides.
    """
    return {"surface": "strip", "x": x, "y": y, "heading": heading}


def top(x: int, y: int, heading: Heading = Heading.NORTH) -> dict:
    """
    A pose on the top face.
    """
    return {"surface": "top", "x": x, "y": y, "heading": heading}


class PlacingTest(unittest.TestCase):
    """
    Putting objects on faces.
    """

    geometry = CubeGeometry()

    def test_side_with_north_heading_by_default(self) -> None:
        """
        A side is placed on the strip, facing north.
        """
        self.assertEqual(self.geometry.place({"face": Face.BACK, "x": 5, "y": 7}), strip(2 * FACE_RESOLUTION + 5, 7))

    def test_keeps_the_given_heading(self) -> None:
        """
        A heading in the placement is kept.
        """
        pose = self.geometry.place({"face": Face.FRONT, "x": 0, "y": 0, "heading": Heading.EAST})

        self.assertEqual(pose["heading"], Heading.EAST)

    def test_top_as_stored_when_front_is_the_anchor(self) -> None:
        """
        With the default anchor the top is addressed as it is stored.
        """
        self.assertEqual(self.geometry.place({"face": Face.TOP, "x": 10, "y": 20}), top(10, 20))

    def test_rejects_cells_outside_the_faces(self) -> None:
        """
        Cells beyond a face are errors.
        """
        for placement in (
            {"face": Face.FRONT, "x": 64, "y": 0},
            {"face": Face.FRONT, "x": 0, "y": 64},
            {"face": Face.TOP, "x": 0, "y": -1},
        ):
            with self.assertRaises(ValueError):
                self.geometry.place(placement)


class MovingTest(unittest.TestCase):
    """
    Walking around the strip and over the top face.
    """

    geometry = CubeGeometry()

    def test_moves_inside_a_face(self) -> None:
        """
        Steps inside a face change one coordinate.
        """
        self.assertEqual(self.geometry.move(strip(10, 10), "right", 3), strip(13, 10))
        self.assertEqual(self.geometry.move(strip(10, 10), "down", 2), strip(10, 12))

    def test_wraps_around_the_strip(self) -> None:
        """
        Going right from the last side comes back to the first.
        """
        self.assertEqual(self.geometry.move(strip(63, 5), "right"), strip(64, 5))
        self.assertEqual(self.geometry.move(strip(STRIP_WIDTH - 1, 5), "right"), strip(0, 5))
        self.assertEqual(self.geometry.move(strip(0, 5), "left"), strip(STRIP_WIDTH - 1, 5))

    def test_steps_follow_the_heading(self) -> None:
        """
        Relative steps are relative to the heading.
        """
        self.assertEqual(self.geometry.move(strip(10, 10, Heading.EAST), "up", 2), strip(12, 10, Heading.EAST))
        self.assertEqual(self.geometry.move(strip(10, 10, Heading.SOUTH), "right"), strip(9, 10, Heading.SOUTH))

    def test_stops_at_the_floor(self) -> None:
        """
        Moving down stops at the last visible row, or at the floor of the config.
        """
        self.assertEqual(self.geometry.move(strip(10, 60), "down", 10), strip(10, 63))

        deep = CubeGeometry({"floor": 70})
        pose = deep.move(strip(10, 60), "down", 20)

        self.assertEqual(pose, strip(10, 70))
        self.assertIsNone(deep.to_pixel(pose))
        self.assertEqual(deep.to_pixel(strip(10, 63)), {"face": Face.FRONT, "x": 10, "y": 63})

    def test_rejects_a_floor_that_is_not_a_row(self) -> None:
        """
        A negative floor is an error.
        """
        with self.assertRaises(ValueError):
            CubeGeometry({"floor": -1})

    def test_enters_the_top_face_from_every_side(self) -> None:
        """
        Going up from the top row of a side arrives on the top face, turned to the way it was going.
        """
        expected = {
            Face.FRONT: top(10, 63, Heading.NORTH),
            Face.RIGHT: top(63, 53, Heading.WEST),
            Face.BACK: top(53, 0, Heading.SOUTH),
            Face.LEFT: top(0, 10, Heading.EAST),
        }

        for face, pose in expected.items():
            start = self.geometry.place({"face": face, "x": 10, "y": 0})

            self.assertEqual(self.geometry.move(start, "up"), pose, face.name)

    def test_leaves_the_top_face_towards_every_side(self) -> None:
        """
        Going off an edge of the top face arrives on the side that lies there.
        """
        cases = [
            (top(10, 0), Heading.NORTH, strip(2 * 64 + 53, 0, Heading.SOUTH)),
            (top(63, 20), Heading.EAST, strip(64 + 43, 0, Heading.SOUTH)),
            (top(10, 63), Heading.SOUTH, strip(10, 0, Heading.SOUTH)),
            (top(0, 20), Heading.WEST, strip(3 * 64 + 20, 0, Heading.SOUTH)),
        ]

        for start, heading, expected in cases:
            self.assertEqual(self.geometry.move({**start, "heading": heading}, "up"), expected)

    def test_comes_back_to_the_same_cell(self) -> None:
        """
        Going up onto the top and down again returns to where it started.
        """
        for x in range(STRIP_WIDTH):
            start = strip(x, 0)
            there = self.geometry.move(start, "up")

            self.assertEqual(there["surface"], "top")
            self.assertEqual(self.geometry.move(there, "down"), start)

    def test_goes_over_the_top_to_the_opposite_side(self) -> None:
        """
        Over the top the object arrives upside down: left and right, and up and down, swap.
        """
        pose = self.geometry.place({"face": Face.FRONT, "x": 32, "y": 30})

        pose = self.geometry.move(pose, "up", 31)
        self.assertEqual(pose, top(32, 63))

        pose = self.geometry.move(pose, "up", 63)
        self.assertEqual(pose, top(32, 0))

        pose = self.geometry.move(pose, "up")
        self.assertEqual(pose, strip(2 * 64 + 31, 0, Heading.SOUTH))
        self.assertEqual(self.geometry.to_pixel(pose), {"face": Face.BACK, "x": 31, "y": 0})

        self.assertEqual(self.geometry.move(pose, "up")["y"], 1)
        self.assertEqual(self.geometry.move(pose, "right")["x"], pose["x"] - 1)

    def test_turns_a_quarter_around_a_corner_of_the_top(self) -> None:
        """
        Walking around a corner of the top face leaves the object turned.
        """
        pose = strip(63, 0)

        for step in ("right", "up", "left"):
            pose = self.geometry.move(pose, step)

        self.assertEqual(pose, strip(63, 0, Heading.WEST))


class TopAnchorTest(unittest.TestCase):
    """
    Which side the addressed top face is lined up with.
    """

    def test_rejects_the_top_as_an_anchor(self) -> None:
        """
        Only a side can be the anchor.
        """
        with self.assertRaises(ValueError):
            CubeGeometry({"top_anchor": Face.TOP})

    def test_rotates_the_addressed_top_face(self) -> None:
        """
        The bottom of the addressed top face touches the anchor.
        """
        anchored = CubeGeometry({"top_anchor": Face.LEFT})
        pose = anchored.place({"face": Face.TOP, "x": 32, "y": 63})

        self.assertEqual(pose, top(0, 32, Heading.EAST))
        self.assertEqual(anchored.move(pose, "down"), strip(3 * 64 + 32, 0, Heading.NORTH))

    def test_leaving_the_bottom_reaches_the_anchor(self) -> None:
        """
        For every anchor, going down from the bottom of the addressed top face reaches it.
        """
        for anchor in SIDES:
            anchored = CubeGeometry({"top_anchor": anchor})
            left = anchored.move(anchored.place({"face": Face.TOP, "x": 32, "y": 63}), "down")

            self.assertEqual(anchored.to_pixel(left)["face"], anchor)

    def test_does_not_change_how_the_sides_work(self) -> None:
        """
        The anchor only affects the top face.
        """
        anchored = CubeGeometry({"top_anchor": Face.BACK})

        self.assertEqual(anchored.place({"face": Face.RIGHT, "x": 3, "y": 4}), strip(64 + 3, 4))
        self.assertEqual(anchored.move(strip(10, 0), "up"), CubeGeometry().move(strip(10, 0), "up"))

    def test_point_up(self) -> None:
        """
        Pointing up resets the heading to the north the user sees.
        """
        anchored = CubeGeometry({"top_anchor": Face.LEFT})

        self.assertEqual(CubeGeometry().point_up(strip(5, 5, Heading.WEST)), strip(5, 5))
        self.assertEqual(CubeGeometry().point_up(top(5, 5, Heading.WEST)), top(5, 5))
        self.assertEqual(
            anchored.point_up(top(5, 5, Heading.WEST))["heading"],
            anchored.place({"face": Face.TOP, "x": 5, "y": 5})["heading"],
        )

    def test_placement_of_is_the_inverse_of_place(self) -> None:
        """
        A pixel gives back the placement that puts an object on it.
        """
        for anchor in SIDES:
            anchored = CubeGeometry({"top_anchor": anchor})
            pose = anchored.place({"face": Face.TOP, "x": 12, "y": 34})
            pixel = anchored.to_pixel(pose)

            self.assertEqual(anchored.placement_of(pixel), {"face": Face.TOP, "x": 12, "y": 34})

        self.assertIsNone(CubeGeometry({"floor": 10}).placement_of({"face": Face.FRONT, "x": 0, "y": 11}))


class OffsetTest(unittest.TestCase):
    """
    Cells at a distance from a pose, for the pixels of a shape.
    """

    geometry = CubeGeometry()

    def test_cells_right_and_below(self) -> None:
        """
        An offset is plain arithmetic in the frame of the pose.
        """
        self.assertEqual(self.geometry.offset(strip(10, 10), 2, 3), strip(12, 13))
        self.assertEqual(self.geometry.offset(strip(10, 10, Heading.EAST), 0, -1), strip(11, 10, Heading.EAST))
        self.assertEqual(self.geometry.offset(strip(10, 10, Heading.EAST), 1, 0), strip(10, 11, Heading.EAST))

    def test_wraps_crosses_and_is_blocked(self) -> None:
        """
        The strip wraps, the top is reachable, and the floor blocks.
        """
        self.assertEqual(self.geometry.offset(strip(0, 5), -1, 0), strip(STRIP_WIDTH - 1, 5))
        self.assertEqual(self.geometry.offset(strip(10, 0), 0, -1), top(10, 63))
        self.assertIsNone(self.geometry.offset(strip(10, 63), 0, 1))

    def test_is_the_same_as_walking_step_by_step(self) -> None:
        """
        The shortcut gives the cell that walking sideways and then vertically does, on the strip and on the top.
        """
        deep = CubeGeometry({"floor": 300})

        for heading in Heading:
            for dx, dy in [(0, 0), (5, 3), (-7, 2), (20, -30), (-20, -40), (50, 1), (-3, 70), (130, -4), (-200, 9)]:
                for start in (strip(250, 20, heading), top(20, 40, heading)):
                    walked = deep.move(deep.move(start, "right" if dx > 0 else "left", abs(dx)), "down" if dy > 0 else "up", abs(dy))

                    self.assertEqual(deep.offset(start, dx, dy), walked)
                    self.assertEqual(deep.pixel_at(start, dx, dy), deep.to_pixel(walked))

    def test_pixel_at_is_offset_then_to_pixel(self) -> None:
        """
        The renderer's shortcut agrees with the long way.
        """
        tall = CubeGeometry({"floor": 70})

        for pose in (strip(250, 20, Heading.EAST), strip(3, 0), strip(10, 66, Heading.SOUTH), top(5, 5, Heading.WEST)):
            for dx, dy in [(0, 0), (5, 3), (-7, -2), (130, -4), (-2, 9), (0, -3)]:
                moved = tall.offset(pose, dx, dy)

                self.assertEqual(tall.pixel_at(pose, dx, dy), moved and tall.to_pixel(moved))

    def test_rejects_offsets_that_are_not_whole_numbers(self) -> None:
        """
        A fractional offset is an error.
        """
        with self.assertRaises(ValueError):
            self.geometry.offset(strip(10, 10), 0.5, 0)

    def test_maps_poses_to_pixels(self) -> None:
        """
        Strip poses land on side faces, top poses on the top.
        """
        self.assertEqual(self.geometry.to_pixel(strip(64 + 3, 4)), {"face": Face.RIGHT, "x": 3, "y": 4})
        self.assertEqual(self.geometry.to_pixel(strip(3 * 64 + 63, 63)), {"face": Face.LEFT, "x": 63, "y": 63})
        self.assertEqual(self.geometry.to_pixel(top(7, 9)), {"face": Face.TOP, "x": 7, "y": 9})


if __name__ == "__main__":
    unittest.main()
