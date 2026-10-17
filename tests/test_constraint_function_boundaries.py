"""Independent runtime-boundary witnesses for the Task 24 experiment.

These tests pin existing externally visible semantics. Candidate-specific
execution and effect-isolation tests remain Execute obligations.
"""

from __future__ import annotations

import unittest

from shear import (
    ActivationRejected,
    CellContentRejected,
    CellDeclaration,
    ConstraintResult,
    EntityID,
    EvaluationContext,
    Evaluator,
    External,
    IntRange,
    IsKind,
    Relation,
    RelationConstraintRejected,
    Runtime,
    State,
    Value,
    canonicalize,
    transform_with_mapping,
)


CELL = EntityID("task24.cell")
GUARD = EntityID("task24.guard")
OWNER = EntityID("task24.owner")
CHILD = EntityID("task24.child")

SAT = ConstraintResult.SATISFIED
UNK = ConstraintResult.UNKNOWN


def cell_state(constraint) -> State:
    return State.create({
        CELL: Value.create(
            CELL,
            CellDeclaration(constraint, 0),
        ),
    })


def relation_state() -> State:
    return State.create({
        CELL: Value.create(
            CELL,
            CellDeclaration(IsKind("int"), 0),
        ),
        GUARD: Value.create(
            GUARD,
            Relation(
                "policy",
                {"item": CELL},
                External("policy"),
            ),
        ),
    })


class AdmissionBoundaryTests(unittest.TestCase):
    def test_unknown_initial_content_is_rejected(self) -> None:
        state = cell_state(External("missing"))

        with self.assertRaises(CellContentRejected) as raised:
            Runtime(state)

        self.assertEqual(raised.exception.cell, CELL)
        self.assertIs(raised.exception.result, UNK)

    def test_unknown_write_preserves_live_content(self) -> None:
        context = EvaluationContext({
            "policy": Evaluator(
                lambda value: SAT if value == 0 else UNK
            ),
        })
        state = cell_state(External("policy"))
        runtime = Runtime(state, context)
        before = runtime.active

        with self.assertRaises(CellContentRejected) as raised:
            runtime.write(CELL, 1)

        self.assertIs(raised.exception.result, UNK)
        self.assertEqual(runtime.read(CELL), 0)
        self.assertIs(runtime.active, before)
        self.assertEqual(runtime.active.id, state.id)

    def test_unknown_relation_rejects_initial_load(self) -> None:
        with self.assertRaises(RelationConstraintRejected) as raised:
            Runtime(relation_state())

        self.assertEqual(raised.exception.relation, GUARD)
        self.assertIs(raised.exception.result, UNK)

    def test_unknown_relation_rejects_write_atomically(self) -> None:
        def policy(subject):
            value = dict(subject[2])["item"]
            return SAT if value == 0 else UNK

        runtime = Runtime(
            relation_state(),
            EvaluationContext({
                "policy": Evaluator(policy),
            }),
        )
        before = runtime.active

        with self.assertRaises(RelationConstraintRejected) as raised:
            runtime.write(CELL, 1)

        self.assertEqual(raised.exception.relation, GUARD)
        self.assertIs(raised.exception.result, UNK)
        self.assertEqual(runtime.read(CELL), 0)
        self.assertIs(runtime.active, before)

    def test_activation_and_trial_reject_unknown_staged_content(
        self,
    ) -> None:
        source = cell_state(IsKind("int"))
        runtime = Runtime(source)
        runtime.write(CELL, 4)

        result = transform_with_mapping(
            source,
            {
                CELL: CellDeclaration(
                    External("missing"), 0
                ),
            },
            {CELL: CELL},
        )
        before = (
            runtime.active,
            dict(runtime.active.cells),
        )

        with self.assertRaises(ActivationRejected) as raised:
            runtime.activate(result)

        self.assertEqual(raised.exception.cell, CELL)
        self.assertIs(raised.exception.result, UNK)
        self.assertEqual(
            (runtime.active, dict(runtime.active.cells)),
            before,
        )

        with self.assertRaises(ActivationRejected) as raised:
            runtime.trial(result)

        self.assertEqual(raised.exception.cell, CELL)
        self.assertIs(raised.exception.result, UNK)
        self.assertEqual(
            (runtime.active, dict(runtime.active.cells)),
            before,
        )

    def test_owned_subtree_is_part_of_relation_subject(self) -> None:
        seen = []

        def capture(subject):
            seen.append(subject)
            return SAT

        state = State.create(
            {
                OWNER: Value.create(OWNER, 1),
                CHILD: Value.create(CHILD, 2),
                GUARD: Value.create(
                    GUARD,
                    Relation(
                        "whole",
                        {"root": OWNER},
                        External("capture"),
                    ),
                ),
            },
            {OWNER: (CHILD,)},
        )

        Runtime(
            state,
            EvaluationContext({
                "capture": Evaluator(capture),
            }),
        )

        self.assertEqual(
            seen,
            [canonicalize({
                "root": {
                    "value": 1,
                    "owned": {CHILD: 2},
                },
            })],
        )


class EvaluationBoundaryTests(unittest.TestCase):
    def test_external_cost_is_not_bounded_by_node_budget(
        self,
    ) -> None:
        calls = []

        def expensive(_subject):
            calls.extend(range(1000))
            return SAT

        context = EvaluationContext(
            {"expensive": Evaluator(expensive)},
            budget=1,
        )

        self.assertIs(
            External("expensive").evaluate(0, context),
            SAT,
        )
        self.assertEqual(len(calls), 1000)

        calls.clear()
        exhausted = EvaluationContext(
            {"expensive": Evaluator(expensive)},
            budget=0,
        )

        self.assertIs(
            External("expensive").evaluate(0, exhausted),
            UNK,
        )
        self.assertEqual(calls, [])

    def test_constraint_identity_ignores_evaluator_context(
        self,
    ) -> None:
        first = External("policy")
        second = External("policy")

        satisfied = EvaluationContext({
            "policy": Evaluator(lambda _: SAT),
        })
        unknown = EvaluationContext()

        self.assertEqual(first, second)
        self.assertIs(first.evaluate(0, satisfied), SAT)
        self.assertIs(second.evaluate(0, unknown), UNK)

        left = State.create({
            GUARD: Value.create(GUARD, first),
        })
        right = State.create({
            GUARD: Value.create(GUARD, second),
        })

        self.assertEqual(left.id, right.id)

    def test_decisive_result_does_not_follow_from_exhaustion(
        self,
    ) -> None:
        constraint = IntRange(0, 10)

        self.assertIs(
            constraint.evaluate(
                5, EvaluationContext(budget=0)
            ),
            UNK,
        )
        self.assertIs(
            constraint.evaluate(
                5, EvaluationContext(budget=1)
            ),
            SAT,
        )


if __name__ == "__main__":
    unittest.main()
