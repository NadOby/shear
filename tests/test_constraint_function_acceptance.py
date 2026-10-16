"""Regression tests for the Task 24 candidate acceptance harness.

These tests check the grader, not any proposed replacement for the
constraint evaluator. Test doubles do not constitute experiment evidence.
"""

from __future__ import annotations

from dataclasses import fields
import unittest
from unittest.mock import patch

from tests.constraint_function_acceptance import (
    CandidateInput,
    Failure,
    Observation,
    Report,
    acceptance_vectors,
    assess,
    candidate_input,
    summarize,
)
from tests.constraint_function_oracle import (
    SAT,
    UNK,
    VIO,
    Vector,
    all_fixed_vectors,
    generated_budget_vector,
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


class CandidateIsolationTests(unittest.TestCase):
    def test_input_schema_excludes_oracle_and_fixture_metadata(
        self,
    ) -> None:
        self.assertEqual(
            tuple(field.name for field in fields(CandidateInput)),
            ("expression", "subject", "budget", "externals"),
        )

    def test_candidate_cannot_read_expected_answer(self) -> None:
        seen = []

        def evaluate(case: CandidateInput) -> Observation:
            self.assertIsInstance(case, CandidateInput)
            self.assertNotIsInstance(case, Vector)

            for name in ("expected", "name", "seed"):
                self.assertFalse(hasattr(case, name))

            seen.append(case.expression)
            return Observation(SAT, "compiled", 0)

        report = grade((SAT_CASE,), evaluate)

        self.assertTrue(report.vector_passed)
        self.assertEqual(seen, [SAT_CASE.expression])

    def test_grader_retains_expected_answer_privately(self) -> None:
        control = Vector("correct", ("external", "sat"), 0, SAT)
        poisoned = Vector("poisoned", ("external", "sat"), 0, VIO)

        inputs = []

        def evaluate(case: CandidateInput) -> Observation:
            inputs.append(case)
            return Observation(SAT, "compiled", 0)

        report = grade((control, poisoned), evaluate)

        self.assertEqual(inputs[0], inputs[1])
        self.assertEqual(report.checked, 2)
        self.assertEqual(len(report.failures), 1)
        self.assertEqual(report.failures[0].name, "poisoned")
        self.assertEqual(report.failures[0].expected, VIO)

    def test_mutating_candidate_inputs_cannot_change_oracle(
        self,
    ) -> None:
        vector = Vector(
            "mutable",
            ("one_of", ({"a": [1]},)),
            {"value": [2]},
            SAT,
        )

        first = candidate_input(vector)
        first.subject["value"].append(3)
        first.expression[1][0]["a"].append(4)

        second = candidate_input(vector)

        self.assertEqual(second.subject, {"value": [2]})
        self.assertEqual(
            second.expression,
            ("one_of", ({"a": [1]},)),
        )
        self.assertEqual(vector.subject, {"value": [2]})
        self.assertEqual(vector.expected, SAT)

    def test_budget_and_externals_reach_adapter(self) -> None:
        vector = Vector(
            "context",
            ("external", "probe"),
            7,
            UNK,
            budget=2,
            externals=(("probe", UNK),),
        )
        seen = []

        def evaluate(case: CandidateInput) -> Observation:
            seen.append(case)
            return Observation(UNK, "interpreted", 0)

        report = grade((vector,), evaluate)

        self.assertTrue(report.vector_passed)
        self.assertEqual(seen[0].budget, 2)
        self.assertEqual(seen[0].externals, (("probe", UNK),))


class AcceptanceVectorTests(unittest.TestCase):
    def test_fixed_cases_are_not_omitted(self) -> None:
        cases = acceptance_vectors(())

        self.assertEqual(
            tuple(vector for vector, seed in cases),
            all_fixed_vectors(),
        )
        self.assertTrue(all(seed is None for _, seed in cases))

    def test_both_generated_families_are_included(self) -> None:
        seeds = (7, 3, 7)
        cases = acceptance_vectors(seeds)
        fixed_count = len(all_fixed_vectors())
        generated = cases[fixed_count:]

        self.assertEqual(len(generated), 2 * len(seeds))

        logical = generated[:len(seeds)]
        budgeted = generated[len(seeds):]

        self.assertEqual(
            logical,
            tuple(
                (generated_vector(seed), seed)
                for seed in seeds
            ),
        )
        self.assertEqual(
            budgeted,
            tuple(
                (generated_budget_vector(seed), seed)
                for seed in seeds
            ),
        )
        self.assertTrue(
            all(vector.budget is not None for vector, _ in budgeted)
        )

    def test_seed_iterator_is_not_consumed_twice(self) -> None:
        seeds = iter((2, 5))
        generated = acceptance_vectors(seeds)[len(all_fixed_vectors()):]

        self.assertEqual(
            tuple(seed for _, seed in generated),
            (2, 5, 2, 5),
        )

    def test_no_cases_cannot_pass(self) -> None:
        report = grade(
            (),
            lambda _: Observation(SAT, "compiled", 0),
        )

        self.assertEqual(report.checked, 0)
        self.assertFalse(report.vector_passed)


class AcceptanceFailureTests(unittest.TestCase):
    def test_all_three_outcomes_can_be_accepted(self) -> None:
        cases = (SAT_CASE, VIO_CASE, UNK_CASE)
        seen = []
        by_external = {
            "sat": SAT,
            "vio": VIO,
            "unk": UNK,
        }

        def evaluate(case: CandidateInput) -> Observation:
            seen.append(case.expression)
            result = by_external[case.expression[1]]
            return Observation(result, "interpreted", 0)

        report = grade(cases, evaluate)

        self.assertTrue(report.vector_passed)
        self.assertEqual(report.checked, 3)
        self.assertEqual(
            seen,
            [case.expression for case in cases],
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

        def evaluate(case: CandidateInput) -> Observation:
            seen.append(case.expression)
            if case.expression == SAT_CASE.expression:
                raise RuntimeError("candidate failure")
            return Observation(VIO, "compiled", 0)

        report = grade((SAT_CASE, VIO_CASE), evaluate)

        self.assertEqual(report.checked, 2)
        self.assertEqual(
            seen,
            [SAT_CASE.expression, VIO_CASE.expression],
        )
        self.assertEqual(len(report.failures), 1)
        self.assertEqual(
            report.failures[0].actual,
            "RuntimeError",
        )

    def test_empty_candidate_name_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            assess(
                "",
                lambda _: Observation(SAT, "compiled", 0),
                (),
            )


class AcceptanceReportingTests(unittest.TestCase):
    def test_generated_failure_keeps_replay_seed(self) -> None:
        with patch(
            "tests.constraint_function_acceptance.all_fixed_vectors",
            return_value=(),
        ):
            report = assess(
                "candidate-b",
                lambda _: Observation(
                    "invalid", "interpreted", 0
                ),
                generated_seeds=(13,),
            )

        self.assertEqual(report.checked, 2)
        self.assertEqual(len(report.failures), 2)
        self.assertEqual(
            [failure.seed for failure in report.failures],
            [13, 13],
        )
        self.assertEqual(
            {failure.replay for failure in report.failures},
            {"SHEAR_SEED=13"},
        )
        self.assertEqual(
            {failure.name for failure in report.failures},
            {
                generated_vector(13).name,
                generated_budget_vector(13).name,
            },
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
