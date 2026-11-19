import datetime as dt
import unittest

from clockfold import (
    GAP,
    FOLD,
    NORMAL,
    classify,
    daily_runs,
    load_zone,
    occurrences,
    parse_time,
    transitions,
)


def at(year, month, day, hour, minute=0):
    return dt.datetime(year, month, day, hour, minute)


class ClassifyTests(unittest.TestCase):
    def test_spring_forward_reading_is_a_gap(self):
        reading = classify(at(2026, 3, 8, 2, 30), load_zone("America/New_York"))
        self.assertEqual(reading.kind, GAP)
        self.assertEqual(reading.shift, dt.timedelta(hours=1))

    def test_autumn_reading_is_a_fold(self):
        reading = classify(at(2026, 11, 1, 1, 30), load_zone("America/New_York"))
        self.assertEqual(reading.kind, FOLD)
        self.assertEqual(reading.later - reading.earlier, dt.timedelta(hours=1))

    def test_ordinary_winter_reading_is_unique(self):
        reading = classify(at(2026, 1, 15, 9, 0), load_zone("America/New_York"))
        self.assertEqual(reading.kind, NORMAL)
        self.assertEqual(reading.earlier, reading.later)

    def test_utc_never_transitions(self):
        reading = classify(at(2026, 3, 8, 2, 30), load_zone("UTC"))
        self.assertEqual(reading.kind, NORMAL)

    def test_half_hour_zone_gap_is_thirty_minutes(self):
        # Lord Howe moves by half an hour, so a one hour assumption is wrong
        reading = classify(at(2026, 10, 4, 2, 15), load_zone("Australia/Lord_Howe"))
        self.assertEqual(reading.kind, GAP)
        self.assertEqual(reading.shift, dt.timedelta(minutes=30))


class OccurrenceTests(unittest.TestCase):
    def setUp(self):
        self.zone = load_zone("America/New_York")

    def test_skip_policy_drops_a_gap(self):
        self.assertEqual(occurrences(at(2026, 3, 8, 2, 30), self.zone, "skip"), [])

    def test_earlier_and_later_bracket_the_gap(self):
        early = occurrences(at(2026, 3, 8, 2, 30), self.zone, "earlier")[0]
        late = occurrences(at(2026, 3, 8, 2, 30), self.zone, "later")[0]
        self.assertLess(early, late)
        # the two candidates sit one gap length apart, either side of the jump
        self.assertEqual(late - early, dt.timedelta(hours=1))

    def test_double_policy_keeps_both_passes_of_a_fold(self):
        runs = occurrences(at(2026, 11, 1, 1, 30), self.zone, "double")
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[1] - runs[0], dt.timedelta(hours=1))

    def test_skip_policy_keeps_one_pass_of_a_fold(self):
        runs = occurrences(at(2026, 11, 1, 1, 30), self.zone, "skip")
        self.assertEqual(len(runs), 1)

    def test_unknown_policy_is_rejected(self):
        with self.assertRaises(ValueError):
            occurrences(at(2026, 11, 1, 1, 30), self.zone, "whenever")


class ScheduleTests(unittest.TestCase):
    def test_daily_job_survives_a_spring_forward(self):
        zone = load_zone("America/New_York")
        runs = daily_runs("02:30", zone, "2026-03-07", days=3, policy="skip")
        self.assertEqual(len(runs), 2)
        self.assertEqual([run.day for run in runs], [7, 9])

    def test_daily_job_doubles_on_a_fall_back(self):
        zone = load_zone("America/New_York")
        runs = daily_runs("01:30", zone, "2026-10-31", days=3, policy="double")
        self.assertEqual(len(runs), 4)

    def test_runs_stay_in_order_and_are_utc(self):
        zone = load_zone("Europe/London")
        runs = daily_runs("01:30", zone, "2026-10-24", days=3, policy="double")
        self.assertEqual(runs, sorted(runs))
        for run in runs:
            self.assertEqual(run.utcoffset(), dt.timedelta(0))


class TransitionTests(unittest.TestCase):
    def test_new_york_changes_twice_in_2026(self):
        found = transitions(2026, load_zone("America/New_York"))
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0][0], dt.datetime(2026, 3, 8, 7, 0, tzinfo=dt.timezone.utc))
        self.assertEqual(found[1][0], dt.datetime(2026, 11, 1, 6, 0, tzinfo=dt.timezone.utc))

    def test_singapore_does_not_change(self):
        self.assertEqual(transitions(2026, load_zone("Asia/Singapore")), [])


class ParseTests(unittest.TestCase):
    def test_two_part_time_gets_zero_seconds(self):
        self.assertEqual(parse_time("02:30"), (2, 30, 0))

    def test_bad_hour_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_time("25:00")


if __name__ == "__main__":
    unittest.main()
