"""Regression tests for the Task 24 candidate acceptance harness.

These tests check the grader, not any proposed replacement for the
constraint evaluator. Test doubles do not constitute experiment evidence.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from tests.constraint_function_acceptance import (
    Failure,
    Observation,
    Report,
    acceptance_vectors,
    assess,
    summarize,
)
from tests.constraint_function_oracle import (
    SAT,
    UNK,
    VIO,
    Vector,
    all_fixed_vectors,
    generated_vector,
)


SAT_CASE = Vector("sat_case", ("external", "sat"), 0, SAT)
VIO_CASE = Vector("vio_case", ("external", "vio"), 0, VIO)
UNK_CASE = Vector("unk_case", ("external", "unk"), 0, UNK)


def grade(cases: tuple[Vector, ...], evaluate) -> Report:
    """Supply a small independent fixture set without generated cases."""
    with patch(
        "tests.constraint_function_acceptance.all_fixed_vectors",
        return_value=cases,
    ):
        return assess("harness-test", evaluate, generated_seeds=())


class AcceptanceVectorTests(unittest.TestCase):
    def test_fixed_cases_are_not_omitted(self) -> None:
        cases = acceptance_vectors(())

        self.assertEqual(
            tuple(vector for vector, seed in cases),
            all_fixed_vectors(),
        )
        self.assertTrue(all(seed is None for _, seed in cases))

    def test_generated_seeds_are_preserved(self) -> None:
        cases = acceptance_vectors((7, 3, 7))
        generated = cases[-3:]

        self.assertEqual(
            tuple(seed for _, seed in generated),
            (7, 3, 7),
        )
        self.assertEqual(generated[0][0], generated_vector(7))
        self.assertEqual(generated[1][0], generated_vector(3))
        self.assertEqual(generated[2][0], generated_vector(7))

    def test_no_cases_cannot_pass(self) -> None:
        report = grade((), lambda _: Observation(SAT, "compiled", 0))

        self.assertEqual(report.checked, 0)
        self.assertFalse(report.vector_passed)


class AcceptanceFailureTests(unittest.TestCase):
    def test_all_three_outcomes_can_be_accepted(self) -> None:
        cases = (SAT_CASE, VIO_CASE, UNK_CASE)
        seen = []

        def evaluate(vector: Vector) -> Observation:
            seen.append(vector.name)
            return Observation(vector.expected, "interpreted", 0)

        report = grade(cases, evaluate)

        self.assertTrue(report.vector_passed)
        self.assertEqual(report.checked, 3)
        self.assertEqual(
            seen,
            ["sat_case", "vio_case", "unk_case"],
        )

    def test_wrong_result_is_not_silently_accepted(self) -> None:
        report = grade(
            (SAT_CASE,),
            lambda _: Observation(VIO, "compiled", 0),
        )

        self.assertFalse(report.vector_passed)
        self.assertEqual(len(report.failures), 1)
        self.assertEqual(report.failures[0].expected, SAT)
        self.assertEqual(report.failures[0].actual, VIO)
        self.assertEqual(
            report.failures[0].expression,
            SAT_CASE.expression,
        )

    def test_unknown_is_not_equivalent_to_violation(self) -> None:
        report = grade(
            (UNK_CASE,),
            lambda _: Observation(VIO, "compiled", 0),
        )

        self.assertFalse(report.vector_passed)
        self.assertEqual(report.failures[0].expected, UNK)

    def test_bad_execution_route_is_rejected(self) -> None:
        for route in ("", "python-fallback", "constraint-evaluator"):
            with self.subTest(route=route):
                report = grade(
                    (SAT_CASE,),
                    lambda _: Observation(SAT, route, 0),
                )
                self.assertFalse(report.vector_passed)
                self.assertIn(
                    "unapproved execution route",
                    report.failures[0].reason,
                )

    def test_each_declared_candidate_route_is_recognized(self) -> None:
        for route in ("callable", "interpreted", "compiled"):
            with self.subTest(route=route):
                report = grade(
                    (SAT_CASE,),
                    lambda _: Observation(SAT, route, 0),
                )
                self.assertTrue(report.vector_passed)

    def test_incumbent_fallback_is_rejected(self) -> None:
        for calls in (1, -1, True, 0.0, None):
            with self.subTest(calls=calls):
                report = grade(
                    (SAT_CASE,),
                    lambda _: Observation(SAT, "compiled", calls),
                )
                self.assertFalse(report.vector_passed)
                self.assertIn(
                    "dedicated evaluator fallback",
                    report.failures[0].reason,
                )

    def test_multiple_independent_failures_are_preserved(self) -> None:
        report = grade(
            (SAT_CASE,),
            lambda _: Observation(VIO, "python-fallback", 1),
        )

        self.assertEqual(len(report.failures), 3)
        self.assertFalse(report.vector_passed)

    def test_invalid_observation_is_not_a_pass(self) -> None:
        report = grade(
            (SAT_CASE,),
            lambda _: {"outcome": SAT},
        )

        self.assertFalse(report.vector_passed)
        self.assertIn(
            "did not return an Observation",
            report.failures[0].reason,
        )

    def test_candidate_exception_does_not_skip_later_cases(
        self,
    ) -> None:
        seen = []

        def evaluate(vector: Vector) -> Observation:
            seen.append(vector.name)
            if vector.name == "sat_case":
                raise RuntimeError("candidate failure")
            return Observation(vector.expected, "compiled", 0)

        report = grade((SAT_CASE, VIO_CASE), evaluate)

        self.assertEqual(report.checked, 2)
        self.assertEqual(seen, ["sat_case", "vio_case"])
        self.assertEqual(len(report.failures), 1)
        self.assertEqual(
            report.failures[0].actual,
            "RuntimeError",
        )

    def test_empty_candidate_name_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            assess("", lambda _: Observation(SAT, "compiled", 0), ())


class AcceptanceReportingTests(unittest.TestCase):
    def test_generated_failure_keeps_replay_seed(self) -> None:
        with patch(
            "tests.constraint_function_acceptance.all_fixed_vectors",
            return_value=(),
        ):
            report = assess(
                "candidate-b",
                lambda _: Observation("invalid", "interpreted", 0),
                generated_seeds=(13,),
            )

        self.assertEqual(report.checked, 1)
        self.assertEqual(report.failures[0].seed, 13)
        self.assertEqual(
            report.failures[0].replay,
            "SHEAR_SEED=13",
        )

    def test_failure_summary_is_deterministic(self) -> None:
        failure = Failure(
            "case",
            SAT,
            UNK,
            "mismatch",
            ("external", "sat"),
            5,
        )
        report = Report("candidate-c", 1, (failure,))
        first = summarize(report)

        self.assertEqual(first, summarize(report))
        self.assertIn("candidate-c: FAIL", first)
        self.assertIn("SHEAR_SEED=5", first)
        self.assertIn("mismatch", first)

    def test_success_summary_reports_checked_count(self) -> None:
        report = Report("candidate-a", 3, ())
        summary = summarize(report)

        self.assertEqual(
            summary,
            "candidate-a: PASS\nvectors checked: 3\nfailures: 0",
        )


if __name__ == "__main__":
    unittest.main()
