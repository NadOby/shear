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

from shear import bytecode, machine
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


def _no_host_lowering(*args, **kwargs):
    raise AssertionError("host bytecode lowering during restricted execution")


@contextmanager
def candidate_execution_guard():
    """Observe authentic evaluator entry, not attempted runner calls."""
    opened = []
    active = []
    original_open = machine._open
    original_run = RestrictedExecutor.run

    def observe_open(activation, args, *rest, **kwargs):
        chunk, env, node = original_open(
            activation, args, *rest, **kwargs
        )
        if not active:
            return chunk, env, node

        deployment, entry = active[-1]
        state = deployment._target.state
        if activation.hold.version.state.id != deployment.source_state_id:
            raise AssertionError("restricted execution used wrong state")

        key = (node, state.values[node].version_id)
        artifact = deployment.artifacts.get(key)
        if artifact is None or chunk is not artifact.chunk:
            raise AssertionError("VM opened non-admitted bytecode")

        if (
            artifact.state_id != state.id
            or artifact.entity != node
            or artifact.version != key[1]
            or artifact.owner != activation.entity
            or artifact.produced_by != deployment.compiler_generation
        ):
            raise AssertionError("admitted artifact provenance mismatch")

        artifact.verify()
        if activation.entity == entry:
            opened.append((
                deployment.source_state_id,
                entry,
                node,
                key[1],
                artifact.artifact_id,
            ))
        return chunk, env, node

    def traced_run(executor, deployment, entry, *args, **kwargs):
        active.append((deployment, entry))
        try:
            with (
                patch.object(
                    bytecode, "lower_value",
                    side_effect=_no_host_lowering,
                ),
                patch.object(
                    bytecode, "chunk_of",
                    side_effect=_no_host_lowering,
                ),
            ):
                return original_run(
                    executor, deployment, entry, *args, **kwargs
                )
        finally:
            active.pop()

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
            patch.object(machine, "_open", side_effect=observe_open)
        )
        stack.enter_context(
            patch.object(RestrictedExecutor, "run", traced_run)
        )
        yield opened


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
