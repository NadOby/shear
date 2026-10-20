"""Frozen executable acceptance for SHEAR issue #123.

Execute supplies tests.constraint_functions_complete_candidate with:
    EVALUATOR_ENTRIES: nonempty frozenset[EntityID]
    semantic(CandidateInput) -> Observation
    boundary(BoundaryInput) -> BoundaryObservation

The Task 24 graders own the expected outcomes. The test independently
checks admitted machine entry and forces evaluator verdicts to establish
that semantic observations depend on executable SHEAR computation.
Passing tests do not replace independent source-path and fallback audit.
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
from shear.identity import EntityID
from tests.constraint_function_acceptance import (
    Observation,
    acceptance_vectors,
    assess,
    candidate_input,
)
from tests.constraint_function_boundary_acceptance import (
    BOUNDARY_CASES,
    assess_boundaries,
)

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

OPERATIONS = frozenset({
    "is_kind", "int_range", "length", "one_of", "all_of",
    "any_of", "not", "role", "external",
})


class EvaluatorMachineFault(RuntimeError):
    """Fault injected only after authentic evaluator bytecode is opened."""


@contextmanager
def forbid_incumbent():
    def forbidden(*args, **kwargs):
        raise AssertionError("incumbent constraint evaluation invoked")

    with ExitStack() as stack:
        stack.enter_context(patch.object(Constraint, "evaluate", forbidden))
        stack.enter_context(patch.object(Constraint, "_evaluate", forbidden))
        for cls in (
            IsKind, IntRange, Length, OneOf, AllOf,
            AnyOf, Not, Role, External,
        ):
            stack.enter_context(patch.object(cls, "_check", forbidden))
        yield


def no_host_lowering(*args, **kwargs):
    raise AssertionError("host lowering during restricted execution")


@contextmanager
def candidate_execution_guard(entries, *, forced=None, fault=False):
    """Observe pinned evaluator roots and optionally perturb their verdicts."""
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

        deployment, _ = active[-1]
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

        if activation.entity in entries:
            opened.append((
                deployment.source_state_id, activation.entity,
                node, key[1], artifact.artifact_id,
            ))
            if fault:
                raise EvaluatorMachineFault("injected evaluator-machine fault")
        return chunk, env, node

    def traced_run(executor, deployment, entry, *args, **kwargs):
        active.append((deployment, entry))
        before = len(opened)
        try:
            with (
                patch.object(
                    bytecode, "lower_value", side_effect=no_host_lowering,
                ),
                patch.object(
                    bytecode, "chunk_of", side_effect=no_host_lowering,
                ),
            ):
                result = original_run(
                    executor, deployment, entry, *args, **kwargs
                )
            if forced is not None and entry in entries:
                if len(opened) == before:
                    raise AssertionError("verdict override without VM entry")
                return forced
            return result
        finally:
            active.pop()

    with (
        forbid_incumbent(),
        patch.object(machine, "_open", side_effect=observe_open),
        patch.object(RestrictedExecutor, "run", traced_run),
    ):
        yield opened


class CompleteConstraintAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            try:
                cls.adapter = import_module(
                    "tests.constraint_functions_complete_candidate"
                )
            except ModuleNotFoundError as exc:
                raise AssertionError(
                    "Execute must supply the real #123 candidate adapter"
                ) from exc

        entries = getattr(cls.adapter, "EVALUATOR_ENTRIES", None)
        if (
            not isinstance(entries, frozenset)
            or not entries
            or not all(isinstance(entry, EntityID) for entry in entries)
        ):
            raise AssertionError(
                "candidate must declare nonempty EVALUATOR_ENTRIES"
            )
        cls.entries = entries
        for name in ("semantic", "boundary"):
            if not callable(getattr(cls.adapter, name, None)):
                raise AssertionError(f"candidate lacks callable {name}")

    def test_complete_semantic_oracle(self):
        with candidate_execution_guard(self.entries) as opened:
            def observed(case):
                before = len(opened)
                result = self.adapter.semantic(case)
                if len(opened) == before:
                    raise AssertionError(
                        "semantic vector did not execute evaluator bytecode"
                    )
                return result

            report = assess(
                "complete-shear-constraints", observed,
                generated_seeds=range(100),
            )

        self.assertEqual(
            report.checked, len(acceptance_vectors(range(100))),
        )
        self.assertTrue(report.vector_passed, repr(report.failures[:10]))

    def test_all_frozen_runtime_boundaries(self):
        self.assertEqual(len(BOUNDARY_CASES), 17)
        with candidate_execution_guard(self.entries) as opened:
            index = 0

            def observed(case):
                nonlocal index
                name = BOUNDARY_CASES[index].name
                index += 1
                before = len(opened)
                result = self.adapter.boundary(case)
                if name in MACHINE_REQUIRED and len(opened) == before:
                    raise AssertionError(
                        f"{name}: no admitted evaluator machine entry"
                    )
                return result

            report = assess_boundaries(
                "complete-shear-constraints", observed,
            )

        self.assertEqual(index, 17)
        self.assertTrue(report.complete_contract)
        self.assertTrue(report.passed, repr(report.failures[:10]))

    def test_evaluator_fault_propagates_for_every_operation(self):
        representatives = {}
        for vector, _ in acceptance_vectors(generated_seeds=()):
            kind = vector.expression[0]
            if kind in OPERATIONS and kind not in representatives:
                representatives[kind] = vector
        self.assertEqual(set(representatives), OPERATIONS)

        for kind, vector in sorted(representatives.items()):
            with self.subTest(operation=kind):
                with candidate_execution_guard(
                    self.entries, fault=True,
                ) as opened:
                    with self.assertRaisesRegex(
                        EvaluatorMachineFault,
                        "injected evaluator-machine fault",
                    ):
                        self.adapter.semantic(candidate_input(vector))
                self.assertTrue(opened, f"{kind}: evaluator not entered")

    def test_evaluator_verdict_controls_semantic_result(self):
        representatives = {}
        for vector, _ in acceptance_vectors(generated_seeds=()):
            kind = vector.expression[0]
            if (
                kind in OPERATIONS and vector.expected == "satisfied"
                and kind not in representatives
            ):
                representatives[kind] = vector
        self.assertEqual(set(representatives), OPERATIONS)

        for kind, vector in sorted(representatives.items()):
            with self.subTest(operation=kind):
                with candidate_execution_guard(
                    self.entries, forced="violated",
                ) as opened:
                    observation = self.adapter.semantic(candidate_input(vector))
                self.assertTrue(opened, f"{kind}: evaluator not entered")
                self.assertIsInstance(observation, Observation)
                self.assertEqual(observation.outcome, "violated")


if __name__ == "__main__":
    unittest.main()
