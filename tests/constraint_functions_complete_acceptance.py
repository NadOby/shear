"""Frozen executable acceptance for SHEAR issue #123.

Execute supplies tests.constraint_functions_complete_candidate with:
    semantic(CandidateInput) -> Observation
    boundary(BoundaryInput) -> BoundaryObservation

The frozen Task 24 graders own the expected results. This module
enforces execution through Task 32 and disables the incumbent
constraint interpreter while candidate acceptance is running.
"""

from contextlib import ExitStack, contextmanager
from importlib import import_module
import unittest
from unittest.mock import patch

from shear.constraints import (
    Constraint,
    IsKind,
    IntRange,
    Length,
    OneOf,
    AllOf,
    AnyOf,
    Not,
    Role,
    External,
)
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from tests.constraint_function_acceptance import (
    acceptance_vectors,
    assess,
)
from tests.constraint_function_boundary_acceptance import (
    BOUNDARY_CASES,
    assess_boundaries,
)


# These boundaries must execute at least one actual restricted
# evaluator invocation. Other cases may legitimately fail preflight,
# lack an evaluator, or exercise non-constraint language behavior.
MACHINE_REQUIRED = frozenset({
    "external_raises",
    "external_under_catch",
    "write_unknown",
    "relation_unknown",
    "owned_subtree",
    "write_satisfied",
    "activation_satisfied",
    "trial_satisfied",
})


@contextmanager
def candidate_execution_guard():
    """Reject incumbent evaluation and independently count VM entry."""
    runs = []
    original_run = RestrictedExecutor.run

    def traced_run(executor, *args, **kwargs):
        runs.append((args[0], args[1]))
        return original_run(executor, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("incumbent constraint evaluation invoked")

    with ExitStack() as stack:
        stack.enter_context(
            patch.object(Constraint, "evaluate", forbidden)
        )
        stack.enter_context(
            patch.object(Constraint, "_evaluate", forbidden)
        )

        for cls in (
            IsKind, IntRange, Length, OneOf, AllOf,
            AnyOf, Not, Role, External,
        ):
            stack.enter_context(
                patch.object(cls, "_check", forbidden)
            )

        stack.enter_context(
            patch.object(RestrictedExecutor, "run", traced_run)
        )
        yield runs


class CompleteConstraintAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.adapter = import_module(
                "tests.constraint_functions_complete_candidate"
            )
        except ModuleNotFoundError as exc:
            raise AssertionError(
                "Execute must supply the real #123 candidate adapter"
            ) from exc

        for entry in ("semantic", "boundary"):
            if not callable(getattr(cls.adapter, entry, None)):
                raise AssertionError(
                    f"candidate adapter lacks callable {entry}"
                )

    def test_complete_semantic_oracle(self):
        with candidate_execution_guard() as runs:
            def observed(case):
                before = len(runs)
                result = self.adapter.semantic(case)

                if len(runs) == before:
                    raise AssertionError(
                        "semantic vector did not enter restricted VM"
                    )
                return result

            report = assess(
                "complete-shear-constraints",
                observed,
                generated_seeds=range(100),
            )

        self.assertEqual(
            report.checked,
            len(acceptance_vectors(range(100))),
        )
        self.assertTrue(
            report.vector_passed,
            repr(report.failures[:10]),
        )

    def test_all_frozen_runtime_boundaries(self):
        self.assertEqual(len(BOUNDARY_CASES), 17)

        with candidate_execution_guard() as runs:
            index = 0

            def observed(case):
                nonlocal index
                name = BOUNDARY_CASES[index].name
                index += 1

                before = len(runs)
                result = self.adapter.boundary(case)

                if name in MACHINE_REQUIRED and len(runs) == before:
                    raise AssertionError(
                        f"{name}: no restricted VM execution"
                    )
                return result

            report = assess_boundaries(
                "complete-shear-constraints",
                observed,
            )

        self.assertEqual(index, 17)
        self.assertTrue(
            report.complete_contract,
            "frozen boundary inventory was not fully checked",
        )
        self.assertTrue(
            report.passed,
            repr(report.failures[:10]),
        )


if __name__ == "__main__":
    unittest.main()
