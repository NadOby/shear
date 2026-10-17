"""Task 24 candidate A: direct-callable identity and bootstrap witnesses.

These are obstacles to callable substitution, not a candidate adapter.
Run with: python3 -m tests.constraint_function_a_probe
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from shear import (
    CellDeclaration,
    Constraint,
    ConstraintResult,
    EntityID,
    EvaluationContext,
    Evaluator,
    External,
    IsKind,
    Runtime,
    State,
    Value,
    canonical_serialize,
)
from shear.lang import Function, load, run


ENTRY = EntityID("task24.a.function")
CELL = EntityID("task24.a.cell")
REF = EntityID("task24.a.reference")
SAT = ConstraintResult.SATISFIED
UNK = ConstraintResult.UNKNOWN


def simple_function() -> Function:
    return Function(("subject",), ("lit", "satisfied"))


class CandidateAWitnessTests(unittest.TestCase):
    def test_python_callables_are_not_semantic_values(self) -> None:
        predicate = lambda _: SAT
        with self.assertRaises(TypeError):
            canonical_serialize(predicate)
        with self.assertRaises(TypeError):
            Value.create(ENTRY, predicate)

    def test_function_values_and_entity_references_are_not_constraints(
        self,
    ) -> None:
        for candidate in (simple_function(), ENTRY):
            with self.subTest(candidate=candidate):
                with self.assertRaises(TypeError):
                    CellDeclaration(candidate, 7)

    def test_deployment_reference_changes_state_identity(self) -> None:
        left = State.create({REF: Value.create(REF, EntityID("a.impl"))})
        right = State.create({REF: Value.create(REF, EntityID("b.impl"))})
        self.assertNotEqual(left.id, right.id)

        first = Value.create(CELL, CellDeclaration(External("policy"), 7))
        second = Value.create(CELL, CellDeclaration(External("policy"), 7))
        self.assertEqual(first.version_id, second.version_id)
        self.assertEqual(
            canonical_serialize(first.content),
            canonical_serialize(second.content),
        )

    def test_function_body_changes_identity_independently_of_result(
        self,
    ) -> None:
        straight = simple_function()
        conditional = Function(
            ("subject",),
            (
                "if", ("lit", True),
                ("lit", "satisfied"),
                ("lit", "violated"),
            ),
        )
        first = State.create({ENTRY: Value.create(ENTRY, straight)})
        second = State.create({ENTRY: Value.create(ENTRY, conditional)})
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(run(Runtime(load(first)), ENTRY, 7), "satisfied")
        self.assertEqual(run(Runtime(load(second)), ENTRY, 7), "satisfied")

    def test_callable_requires_a_loaded_runtime(self) -> None:
        with self.assertRaises(KeyError):
            run(Runtime(State.create({})), ENTRY, 7)
        loaded = Runtime(load(State.create({
            ENTRY: Value.create(ENTRY, simple_function()),
        })))
        self.assertEqual(run(loaded, ENTRY, 7), "satisfied")

    def test_initial_admission_precedes_user_function_execution(self) -> None:
        state = State.create({
            ENTRY: Value.create(ENTRY, simple_function()),
            CELL: Value.create(CELL, CellDeclaration(IsKind("int"), 7)),
        })
        visits = []
        original = Constraint.evaluate

        def witnessed(self, subject, context=None):
            visits.append((type(self).__name__, subject))
            return original(self, subject, context)

        with patch.object(Constraint, "evaluate", witnessed):
            runtime = Runtime(load(state))
            self.assertEqual(visits, [("IsKind", 7)])

        self.assertEqual(run(runtime, ENTRY, 7), "satisfied")
        self.assertEqual(runtime.active.holds, frozenset())

    def test_constraint_identity_ignores_external_authority(self) -> None:
        constraint = External("policy")
        expected_identity = canonical_serialize(constraint)
        context = EvaluationContext({
            "policy": Evaluator(lambda _: SAT),
        })
        self.assertIs(constraint.evaluate(7, context), SAT)
        self.assertIs(constraint.evaluate(7, EvaluationContext()), UNK)
        self.assertEqual(canonical_serialize(constraint), expected_identity)


if __name__ == "__main__":
    unittest.main()
