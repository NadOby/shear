"""Task 24: run full frozen graders against bounded B/C limitations.

A boundary script that lacks candidate integration must fail closed. An
adapter exception is a recorded failure, not a substitute observation.
Run with: python3 -m tests.constraint_function_disqualification_probe
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from shear import Constraint
from shear.lang import run
from tests.constraint_function_acceptance import (
    CandidateInput,
    Observation,
    assess,
)
from tests.constraint_function_boundary_acceptance import (
    BOUNDARY_CASES,
    BoundaryInput,
    BoundaryObservation,
    assess_boundaries,
)
from tests.constraint_function_b_probe import (
    ENTRY,
    argument,
    element,
    ordinary_runtime,
)
from tests.constraint_function_c_probe import (
    UnsupportedCandidateC,
    candidate_c,
    materialize,
)
from tests.constraint_function_oracle import all_fixed_vectors


class UnsupportedCandidateB(ValueError):
    """Candidate B lacks the required canonical-data projection."""


def candidate_b(case: CandidateInput) -> Observation:
    """Attempt VM-side projection of a real canonical constraint value.

    This is a deliberately bounded capability attempt, not a complete
    interpreter. Unsupported operations are not guessed or delegated.
    """
    if case.budget is not None or case.externals:
        raise UnsupportedCandidateB("budget and authority unsupported")

    try:
        constraint = materialize(case.expression)
    except UnsupportedCandidateC as exc:
        raise UnsupportedCandidateB(str(exc)) from exc

    runtime = ordinary_runtime(
        ("constraint",), element(argument("constraint"), 2),
    )
    outcome = run(runtime, ENTRY, constraint)
    return Observation(outcome, "interpreted", 0)


def boundary_b(case: BoundaryInput) -> BoundaryObservation:
    """Reject scripts without a candidate-integrated admission path."""
    if not case.script:
        raise UnsupportedCandidateB("empty boundary script")
    raise UnsupportedCandidateB("B has no candidate runtime admission path")


def boundary_c(case: BoundaryInput) -> BoundaryObservation:
    """Reject scripts without a candidate-integrated admission path."""
    if not case.script:
        raise UnsupportedCandidateC("empty boundary script")
    raise UnsupportedCandidateC("C has no candidate runtime admission path")


class CandidateDisqualificationTests(unittest.TestCase):
    def test_all_frozen_semantic_cases_are_attempted_for_b(self) -> None:
        with patch.object(
            Constraint, "evaluate",
            side_effect=AssertionError("incumbent fallback"),
        ):
            report = assess("B-bounded", candidate_b)

        self.assertEqual(report.checked, len(all_fixed_vectors()) + 200)
        self.assertFalse(report.vector_passed)
        self.assertTrue(report.failures)
        self.assertFalse(any(
            failure.actual == "AssertionError"
            for failure in report.failures
        ))

    def test_all_frozen_semantic_cases_are_attempted_for_c(self) -> None:
        with patch.object(
            Constraint, "evaluate",
            side_effect=AssertionError("incumbent fallback"),
        ):
            report = assess("C-bounded", candidate_c)

        self.assertEqual(report.checked, len(all_fixed_vectors()) + 200)
        self.assertFalse(report.vector_passed)
        self.assertTrue(report.failures)
        self.assertFalse(any(
            failure.actual == "AssertionError"
            for failure in report.failures
        ))

    def test_all_17_boundaries_fail_without_a_candidate_path(self) -> None:
        for name, candidate, missing in (
            ("B-bounded", boundary_b, "UnsupportedCandidateB"),
            ("C-bounded", boundary_c, "UnsupportedCandidateC"),
        ):
            with self.subTest(candidate=name):
                with patch.object(
                    Constraint, "evaluate",
                    side_effect=AssertionError("incumbent fallback"),
                ):
                    report = assess_boundaries(name, candidate)

                self.assertTrue(report.complete_contract)
                self.assertEqual(report.checked, len(BOUNDARY_CASES))
                self.assertEqual(len(BOUNDARY_CASES), 17)
                self.assertFalse(report.passed)
                self.assertEqual(len(report.failures), 17)
                self.assertEqual(
                    tuple(failure.name for failure in report.failures),
                    tuple(case.name for case in BOUNDARY_CASES),
                )
                self.assertTrue(all(
                    failure.field == "execution"
                    and failure.actual == missing
                    for failure in report.failures
                ))


if __name__ == "__main__":
    unittest.main()
