"""
Tests for the greedy runway scheduler.
Run with:  python -m unittest -v test_runway_scheduler
"""

import math
import unittest

from runway_scheduler import make_flight, schedule


def F(code, cat, earliest, latest):
    return make_flight(code, cat, earliest, latest)


def times_by_code(result):
    return {a.flight.code: a.time for a in result.assignments}


class TestNormalCases(unittest.TestCase):

    def test_single_flight_lands_at_earliest_time(self):
        r = schedule([F("A", "M", 10, 20)], 1)
        a = r.assignments[0]
        self.assertEqual((a.runway, a.time, a.delay), (0, 10, 0))
        self.assertEqual(r.unscheduled, [])

    def test_separation_applied_on_same_runway(self):
        r = schedule([F("A", "M", 0, 30), F("B", "M", 0, 30)], 1)
        self.assertEqual(times_by_code(r), {"A": 0, "B": 2})

    def test_heavy_leader_light_follower_needs_longer_separation(self):
        r = schedule([F("H1", "H", 0, 100), F("L1", "L", 0, 100)], 1)
        self.assertEqual(times_by_code(r), {"H1": 0, "L1": 4})

    def test_flights_spread_across_runways(self):
        flights = [F("A", "M", 0, 100), F("B", "M", 0, 100), F("C", "M", 0, 100)]
        r = schedule(flights, 2)
        placed = {a.flight.code: (a.runway, a.time) for a in r.assignments}
        self.assertEqual(placed, {"A": (0, 0), "B": (1, 0), "C": (0, 2)})

    def test_greedy_picks_earliest_landing_runway(self):
        # After A lands on RWY 1 at t=0, a Heavy flight B is ready at t=1 on the
        # empty RWY 2 but only at t=2 on RWY 1 (M->H separation is 2 min).
        r = schedule([F("A", "M", 0, 100), F("B", "H", 1, 50)], 2)
        b = next(a for a in r.assignments if a.flight.code == "B")
        self.assertEqual((b.runway, b.time), (1, 1))

    def test_delay_is_time_minus_earliest(self):
        r = schedule([F("A", "M", 0, 100), F("B", "M", 0, 100)], 1)
        b = next(a for a in r.assignments if a.flight.code == "B")
        self.assertEqual(b.delay, 2)

    def test_result_independent_of_input_order(self):
        flights = [F("A", "M", 0, 100), F("B", "H", 1, 50), F("C", "L", 3, 60)]
        forward = times_by_code(schedule(flights, 2))
        reverse = times_by_code(schedule(list(reversed(flights)), 2))
        self.assertEqual(forward, reverse)

    def test_step_trace_has_one_step_per_flight(self):
        flights = [F("A", "M", 0, 100), F("B", "M", 1, 100)]
        r = schedule(flights, 1)
        self.assertEqual(len(r.steps), len(flights))
        self.assertTrue(all(len(s.options) == 1 for s in r.steps))


class TestBoundaryCases(unittest.TestCase):

    def test_empty_input(self):
        r = schedule([], 2)
        self.assertEqual(r.assignments, [])
        self.assertEqual(r.unscheduled, [])
        self.assertEqual(r.steps, [])

    def test_zero_runways_rejected(self):
        with self.assertRaises(ValueError):
            schedule([F("A", "M", 0, 10)], 0)

    def test_negative_runways_rejected(self):
        with self.assertRaises(ValueError):
            schedule([F("A", "M", 0, 10)], -3)

    def test_deadline_exactly_met_is_scheduled(self):
        # B's earliest is 2 and it can land at 2 (= its deadline) after A.
        r = schedule([F("A", "M", 0, 10), F("B", "M", 2, 2)], 1)
        self.assertEqual(times_by_code(r), {"A": 0, "B": 2})
        self.assertEqual(r.unscheduled, [])

    def test_deadline_missed_by_separation_is_unscheduled(self):
        # B could only land at 2, but its deadline is 1.
        r = schedule([F("A", "M", 0, 10), F("B", "M", 1, 1)], 1)
        self.assertEqual(times_by_code(r), {"A": 0})
        self.assertEqual([f.code for f in r.unscheduled], ["B"])

    def test_identical_flights_more_than_runways(self):
        flights = [F(f"X{i}", "M", 0, 5) for i in range(4)]
        r = schedule(flights, 2)
        # Two runways, separation 2: slots at t=0 and t=2 on each runway fit;
        # the fifth-style overflow would be unscheduled. Here 4 fit exactly
        # (0, 0, 2, 2) within deadline 5.
        self.assertEqual(len(r.assignments), 4)
        self.assertEqual(r.unscheduled, [])

    def test_identical_flights_overflow_is_unscheduled(self):
        flights = [F(f"X{i}", "M", 0, 2) for i in range(3)]
        r = schedule(flights, 1)
        self.assertEqual(len(r.assignments), 2)   # t=0 and t=2 only
        self.assertEqual(len(r.unscheduled), 1)

    def test_single_runway_many_flights_all_separated(self):
        flights = [F(f"F{i}", "L", 0, 1000) for i in range(10)]
        r = schedule(flights, 1)
        ts = sorted(a.time for a in r.assignments)
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        self.assertTrue(all(g >= 2 for g in gaps))

    def test_duplicate_codes_rejected(self):
        with self.assertRaises(ValueError):
            schedule([F("A", "M", 0, 10), F("A", "H", 5, 20)], 1)

    def test_zero_time_window(self):
        r = schedule([F("A", "M", 0, 0)], 1)
        self.assertEqual(times_by_code(r), {"A": 0})


class TestInputValidation(unittest.TestCase):

    def test_invalid_category(self):
        with self.assertRaises(ValueError):
            make_flight("A", "X", 0, 10)

    def test_earliest_after_latest(self):
        with self.assertRaises(ValueError):
            make_flight("A", "M", 20, 10)

    def test_non_numeric_time(self):
        with self.assertRaises(ValueError):
            make_flight("A", "M", "abc", 10)

    def test_negative_time(self):
        with self.assertRaises(ValueError):
            make_flight("A", "M", -1, 10)

    def test_non_finite_time(self):
        with self.assertRaises(ValueError):
            make_flight("A", "M", math.nan, 10)

    def test_empty_code(self):
        with self.assertRaises(ValueError):
            make_flight("   ", "M", 0, 10)

    def test_inputs_are_normalised(self):
        f = make_flight(" ba101 ", " h ", "0", "20")
        self.assertEqual((f.code, f.category, f.earliest, f.latest), ("BA101", "H", 0.0, 20.0))


if __name__ == "__main__":
    unittest.main()
