"""
Tests for the interpreter and the scheduler: how scripts run over time.
"""

import unittest

from programs.main.cube.runtime.interpreter import run_blocks
from programs.main.cube.runtime.scheduler import Scheduler
from programs.main.cube.world.world import World


BALL = {"op": "create", "name": "ball", "face": "FRONT", "x": 0, "y": 0, "color": "#ffffff"}
"""
A ball in the corner of FRONT.
"""

RIGHT = {"op": "move", "target": "ball", "step": "right"}
"""
One step to the right.
"""


def pauses(blocks: list, world: World | None = None, limit: int = 20) -> list:
    """
    The pauses of a script, up to `limit` of them.
    """
    run = run_blocks(blocks, world or World())
    collected = []

    for _ in range(limit):
        try:
            collected.append(next(run))

        except StopIteration:
            break

    return collected


class InterpreterTest(unittest.TestCase):
    """
    Control flow of one script.
    """

    def test_commands_run_without_pausing(self) -> None:
        """
        Straight-line code is one go.
        """
        world = World()

        self.assertEqual(pauses([BALL, RIGHT, RIGHT], world), [])
        self.assertEqual(world.get("ball")["pose"]["x"], 2)

    def test_pauses_on_a_wait_and_continues_from_there(self) -> None:
        """
        The generator resumes where it stopped.
        """
        world = World()
        run = run_blocks([BALL, {"op": "wait", "seconds": 0.5}, RIGHT], world)

        self.assertEqual(next(run), {"kind": "wait", "milliseconds": 500})
        self.assertEqual(world.get("ball")["pose"]["x"], 0)

        with self.assertRaises(StopIteration):
            next(run)

        self.assertEqual(world.get("ball")["pose"]["x"], 1)

    def test_repeat_gives_a_turn_after_every_iteration(self) -> None:
        """
        A loop that did not pause by itself gets a tick per iteration.
        """
        world = World()

        self.assertEqual(pauses([BALL, {"op": "repeat", "times": 3, "body": [RIGHT]}], world), [{"kind": "tick"}] * 3)
        self.assertEqual(world.get("ball")["pose"]["x"], 3)

    def test_no_extra_pause_when_the_iteration_already_waited(self) -> None:
        """
        A wait in the body is the pause.
        """
        result = pauses([BALL, {"op": "repeat", "times": 2, "body": [RIGHT, {"op": "wait", "seconds": 1}]}])

        self.assertEqual(result, [{"kind": "wait", "milliseconds": 1000}] * 2)

    def test_repeat_zero_times_runs_nothing(self) -> None:
        """
        An empty loop.
        """
        world = World()

        pauses([BALL, {"op": "repeat", "times": 0, "body": [RIGHT]}], world)

        self.assertEqual(world.get("ball")["pose"]["x"], 0)

    def test_forever_never_blocks(self) -> None:
        """
        Even with an empty body it pauses every iteration.
        """
        result = pauses([{"op": "forever", "body": []}], limit=5)

        self.assertEqual(result, [{"kind": "tick"}] * 5)

    def test_forever_runs_one_iteration_per_pause(self) -> None:
        """
        Each resume is one more step.
        """
        world = World()
        run = run_blocks([BALL, {"op": "forever", "body": [RIGHT]}], world)

        for _ in range(3):
            next(run)

        self.assertEqual(world.get("ball")["pose"]["x"], 3)

    def test_loops_inside_loops(self) -> None:
        """
        3 times 2 steps.
        """
        world = World()

        pauses([BALL, {"op": "repeat", "times": 3, "body": [{"op": "repeat", "times": 2, "body": [RIGHT]}]}], world)

        self.assertEqual(world.get("ball")["pose"]["x"], 6)

    def test_the_error_of_a_command_reaches_the_caller(self) -> None:
        """
        Nothing is swallowed here.
        """
        with self.assertRaisesRegex(Exception, 'There is no object called "ghost"'):
            next(run_blocks([{"op": "hide", "target": "ghost"}], World()))


class SchedulerTest(unittest.TestCase):
    """
    When each script gets its turn.
    """

    @staticmethod
    def setup(scripts: list):
        """
        A world, the errors reported, and a scheduler started at time 0.
        """
        world, errors = World(), []
        scheduler = Scheduler(world, scripts, errors.append)

        scheduler.start(0)

        return world, errors, scheduler

    @staticmethod
    def start(*blocks: dict) -> dict:
        """
        A script that starts at once.
        """
        return {"trigger": {"type": "start"}, "blocks": list(blocks)}

    def test_nothing_runs_before_the_first_tick(self) -> None:
        """
        Starting only arms the scripts.
        """
        world, _, scheduler = self.setup([self.start(BALL)])

        self.assertTrue(scheduler.active)
        self.assertEqual(list(world.all()), [])

    def test_runs_a_script_until_it_finishes(self) -> None:
        """
        Then the scheduler has nothing left.
        """
        world, _, scheduler = self.setup([self.start(BALL, RIGHT)])

        scheduler.tick(0)

        self.assertEqual(world.get("ball")["pose"]["x"], 1)
        self.assertFalse(scheduler.active)

    def test_wakes_a_script_when_its_wait_is_over_not_before(self) -> None:
        """
        A wait of a second.
        """
        world, _, scheduler = self.setup([self.start(BALL, {"op": "wait", "seconds": 1}, RIGHT)])

        scheduler.tick(0)
        scheduler.tick(999)
        self.assertEqual(world.get("ball")["pose"]["x"], 0)

        scheduler.tick(1000)
        self.assertEqual(world.get("ball")["pose"]["x"], 1)

    def test_a_looping_script_gets_one_turn_per_tick(self) -> None:
        """
        It cannot run away within a tick.
        """
        world, _, scheduler = self.setup([self.start(BALL, {"op": "forever", "body": [RIGHT]})])

        for now in (0, 33, 66):
            scheduler.tick(now)

        self.assertEqual(world.get("ball")["pose"]["x"], 3)

    def test_runs_several_scripts_side_by_side(self) -> None:
        """
        One goes right, the other down.
        """
        world, _, scheduler = self.setup(
            [
                self.start(BALL, {"op": "forever", "body": [RIGHT]}),
                self.start({"op": "wait", "seconds": 0.001}, {"op": "forever", "body": [{"op": "move", "target": "ball", "step": "down"}]}),
            ]
        )

        for now in (0, 33, 66):
            scheduler.tick(now)

        pose = world.get("ball")["pose"]

        self.assertEqual((pose["x"], pose["y"]), (3, 2))

    def test_keeps_the_rhythm_of_a_wait_loop(self) -> None:
        """
        Ticks of 33 ms and a wait of 100 ms do not drift by a tick each time.
        """
        world, _, scheduler = self.setup([self.start(BALL, {"op": "forever", "body": [RIGHT, {"op": "wait", "seconds": 0.1}]})])

        for now in range(0, 331, 33):
            scheduler.tick(now)

        self.assertEqual(world.get("ball")["pose"]["x"], 4)

    def test_does_not_rush_to_catch_up_after_a_freeze(self) -> None:
        """
        A minute without ticks does not mean 600 steps.
        """
        world, _, scheduler = self.setup([self.start(BALL, {"op": "forever", "body": [RIGHT, {"op": "wait", "seconds": 0.1}]})])

        scheduler.tick(0)
        scheduler.tick(60000)

        self.assertEqual(world.get("ball")["pose"]["x"], 2)

    def test_every_runs_each_time_the_interval_passes(self) -> None:
        """
        An `every` script, and it keeps the scheduler active.
        """
        every = {"trigger": {"type": "every", "seconds": 1}, "blocks": [RIGHT]}
        world, _, scheduler = self.setup([self.start(BALL), every])

        for now, expected in ((0, 0), (1000, 1), (1500, 1), (2000, 2)):
            scheduler.tick(now)

            self.assertEqual(world.get("ball")["pose"]["x"], expected, now)

        self.assertTrue(scheduler.active)

    def test_every_skips_a_run_due_while_the_previous_one_is_going(self) -> None:
        """
        No two runs of the same script at once.
        """
        every = {"trigger": {"type": "every", "seconds": 1}, "blocks": [{"op": "wait", "seconds": 2.5}, RIGHT]}
        world, _, scheduler = self.setup([self.start(BALL), every])

        for now in (0, 1000, 2000, 3000):
            scheduler.tick(now)

        self.assertEqual(world.get("ball")["pose"]["x"], 0)

        scheduler.tick(3500)

        self.assertEqual(world.get("ball")["pose"]["x"], 1)

    def test_a_failing_script_stops_alone_and_is_reported(self) -> None:
        """
        The other scripts keep going.
        """
        world, errors, scheduler = self.setup(
            [
                self.start(BALL, {"op": "forever", "body": [RIGHT]}),
                self.start({"op": "hide", "target": "ghost"}),
            ]
        )

        scheduler.tick(0)
        scheduler.tick(33)

        self.assertEqual(errors, [{"script": 1, "message": 'There is no object called "ghost"'}])
        self.assertEqual(world.get("ball")["pose"]["x"], 2)

    def test_forgets_its_scripts_when_stopped(self) -> None:
        """
        What they did stays.
        """
        world, _, scheduler = self.setup([self.start(BALL, {"op": "forever", "body": [RIGHT]})])

        scheduler.tick(0)
        scheduler.stop()
        scheduler.tick(33)

        self.assertFalse(scheduler.active)
        self.assertEqual(world.get("ball")["pose"]["x"], 1)


if __name__ == "__main__":
    unittest.main()
