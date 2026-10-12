"""The mutation performance summary reads old and new campaign reports."""

from __future__ import annotations

import unittest

from tests import mutation_performance as performance


def outcome(
    outcome: str,
    seconds: float,
    **extra: object,
) -> dict[str, object]:
    return {
        "event": "mutant_outcome",
        "outcome": outcome,
        "elapsed_seconds": seconds,
        "key": ["shear/x.py", "if", "line", 0],
        **extra,
    }


def done(seconds: float) -> dict[str, object]:
    return {"event": "campaign_complete", "elapsed_seconds": seconds}


class SummaryTests(unittest.TestCase):
    def test_wall_is_the_slowest_shard_and_cpu_is_the_sum(self) -> None:
        result = performance.summarize({
            "a": [outcome("killed", 2.0, cpu_seconds=3.0), done(10.0)],
            "b": [outcome("killed", 4.0, cpu_seconds=5.0), done(30.0)],
        })

        self.assertEqual(result["campaign_wall_seconds"], 30.0)
        self.assertEqual(result["sum_of_shard_wall_seconds"], 40.0)
        self.assertEqual(result["mutant_cpu_seconds"], 8.0)

    def test_pinned_survivors_that_were_not_run_cost_nothing(self) -> None:
        result = performance.summarize({
            "a": [
                outcome("classified_survivor", 0.0, executed=False),
                outcome("killed", 2.0, cpu_seconds=1.0),
                done(2.0),
            ],
        })

        self.assertEqual(result["not_run_pinned"], 1)
        self.assertEqual(result["kill_seconds"]["count"], 1)

    def test_outcomes_stages_and_killers_are_counted(self) -> None:
        result = performance.summarize({
            "a": [
                outcome("killed", 1.0, cpu_seconds=1.0, stage="covering",
                        killed_by="test_a"),
                outcome("killed", 9.0, cpu_seconds=1.0, stage="rest",
                        killed_by="test_a"),
                outcome("timeout", 180.0, cpu_seconds=1.0),
                done(190.0),
            ],
        })

        self.assertEqual(result["outcomes"], {"killed": 2, "timeout": 1})
        self.assertEqual(result["kill_stage"], {"covering": 1, "rest": 1})
        self.assertEqual(result["killed_by"], {"test_a": 2})
        self.assertEqual(result["slowest"][0]["outcome"], "timeout")
        # A timeout is never part of the kill-time distribution.
        self.assertEqual(result["kill_seconds"]["max"], 9.0)

    def test_old_reports_have_unknown_cpu_not_zero(self) -> None:
        result = performance.summarize({
            "a": [outcome("killed", 1.0), done(1.0)],
        })

        self.assertIsNone(result["mutant_cpu_seconds"])
        self.assertIn("unknown", performance.render(result))

    def test_a_report_without_completion_is_flagged(self) -> None:
        result = performance.summarize({"a": [outcome("killed", 1.0)]})

        self.assertEqual(result["incomplete_reports"], ["a"])
        self.assertIsNone(result["campaign_wall_seconds"])
        self.assertIn("INCOMPLETE", performance.render(result))


if __name__ == "__main__":
    unittest.main()
