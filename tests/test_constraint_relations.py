"""Tests for constraint relations: constraints over several entities."""

import random
import unittest
from typing import Any

from shear import (
    ActivationRejected,
    AllOf,
    CellDeclaration,
    CellContentRejected,
    ConstraintResult,
    EntityID,
    EvaluationContext,
    Evaluator,
    External,
    IntRange,
    IsKind,
    Relation,
    RelationConstraintRejected,
    Role,
    Runtime,
    State,
    Value,
    canonicalize,
    constraint_relations,
    transform_with_mapping,
)

LOW = EntityID("low")
HIGH = EntityID("high")
LIMIT = EntityID("limit")
ORDER = EntityID("order")

SAT = ConstraintResult.SATISFIED
VIO = ConstraintResult.VIOLATED
UNK = ConstraintResult.UNKNOWN


def ordered(subject: Any) -> ConstraintResult:
    """Evaluator comparing two roles of a canonical role map."""

    roles = dict(subject[2])
    return SAT if roles["low"] <= roles["high"] else VIO


CONTEXT = EvaluationContext({"ordered": Evaluator(ordered)})

LOW_NOT_ABOVE_HIGH = Relation(
    "bound",
    {"low": LOW, "high": HIGH},
    payload=AllOf(
        Role("low", IsKind("int")),
        Role("high", IsKind("int")),
        External("ordered"),
    ),
)


def program(low: int = 0, high: int = 10, relation: Any = None) -> State:
    return State.create({
        LOW: Value.create(LOW, CellDeclaration(IsKind("int"), low)),
        HIGH: Value.create(HIGH, CellDeclaration(IsKind("int"), high)),
        ORDER: Value.create(ORDER, relation or LOW_NOT_ABOVE_HIGH),
    })


class ConstraintRelationRecognitionTests(unittest.TestCase):
    def test_a_constraint_payload_makes_a_constraint_relation(self) -> None:
        state = State.create({
            LOW: Value.create(LOW, 1),
            ORDER: Value.create(ORDER, Relation("anything", {"x": LOW}, IsKind("int"))),
            LIMIT: Value.create(LIMIT, Relation("constraint", {"x": LOW}, 5)),
        })

        self.assertEqual(set(constraint_relations(state)), {ORDER})

    def test_a_relation_without_endpoints_keeps_its_constraint_as_data(
        self,
    ) -> None:
        nullary = EntityID("nullary")
        empty = EntityID("empty")
        state = State.create({
            LOW: Value.create(LOW, 1),
            ORDER: Value.create(
                ORDER,
                Relation("anything", {"x": LOW}, Role("x", IsKind("int"))),
            ),
            nullary: Value.create(nullary, Relation("lit", {}, IsKind("int"))),
            empty: Value.create(empty, Relation("quote", {"holes": ()}, IsKind("int"))),
        })

        self.assertEqual(set(constraint_relations(state)), {ORDER})
        Runtime(state)

    def test_a_constraint_kept_as_data_beside_endpoints_must_be_wrapped(
        self,
    ) -> None:
        # relation_model.md §7: with an endpoint, a bare constraint payload
        # is enforced; wrapped in a tuple or a map it is a description.
        def state(payload: Any) -> State:
            return State.create({
                LOW: Value.create(LOW, 1),
                ORDER: Value.create(ORDER, Relation("described", {"x": LOW}, payload)),
            })

        with self.assertRaises(RelationConstraintRejected):
            Runtime(state(IsKind("str")))

        for payload in ((IsKind("str"),), {"type": IsKind("str")}):
            with self.subTest(payload=payload):
                self.assertEqual(dict(constraint_relations(state(payload))), {})
                Runtime(state(payload))


class LoadTests(unittest.TestCase):
    def test_satisfied_relation_loads(self) -> None:
        runtime = Runtime(program(), CONTEXT)

        self.assertEqual((runtime.read(LOW), runtime.read(HIGH)), (0, 10))

    def test_violated_relation_is_rejected_on_load(self) -> None:
        with self.assertRaises(RelationConstraintRejected) as raised:
            Runtime(program(low=11, high=10), CONTEXT)

        self.assertEqual(raised.exception.relation, ORDER)
        self.assertIs(raised.exception.result, VIO)

    def test_unknown_relation_is_rejected_on_load(self) -> None:
        with self.assertRaises(RelationConstraintRejected) as raised:
            Runtime(program())

        self.assertIs(raised.exception.result, UNK)

    def test_relation_over_ordinary_values_is_checked(self) -> None:
        state = State.create({
            LIMIT: Value.create(LIMIT, "not an int"),
            ORDER: Value.create(
                ORDER,
                Relation("typed", {"value": LIMIT}, Role("value", IsKind("int"))),
            ),
        })

        with self.assertRaises(RelationConstraintRejected):
            Runtime(state)


class WriteTests(unittest.TestCase):
    def test_write_breaking_the_relation_is_rejected(self) -> None:
        runtime = Runtime(program(), CONTEXT)

        with self.assertRaises(RelationConstraintRejected) as raised:
            runtime.write(LOW, 11)

        self.assertEqual(raised.exception.relation, ORDER)
        self.assertEqual(runtime.read(LOW), 0)

    def test_write_keeping_the_relation_is_accepted(self) -> None:
        runtime = Runtime(program(), CONTEXT)

        runtime.write(HIGH, 20)
        runtime.write(LOW, 15)

        self.assertEqual((runtime.read(LOW), runtime.read(HIGH)), (15, 20))

    def test_cell_constraint_is_checked_before_the_relation(self) -> None:
        runtime = Runtime(program(), CONTEXT)

        with self.assertRaises(CellContentRejected):
            runtime.write(LOW, "text")

    def test_untouched_cells_do_not_evaluate_the_relation(self) -> None:
        calls = []

        def counting(subject: Any) -> ConstraintResult:
            calls.append(subject)
            return ordered(subject)

        state = State.create({
            LOW: Value.create(LOW, CellDeclaration(IsKind("int"), 0)),
            HIGH: Value.create(HIGH, CellDeclaration(IsKind("int"), 10)),
            LIMIT: Value.create(LIMIT, CellDeclaration(IsKind("int"), 0)),
            ORDER: Value.create(ORDER, LOW_NOT_ABOVE_HIGH),
        })
        runtime = Runtime(
            state,
            EvaluationContext({"ordered": Evaluator(counting)}),
        )
        calls.clear()

        runtime.write(LIMIT, 99)

        self.assertEqual(calls, [])


class ActivationTests(unittest.TestCase):
    def test_activation_checks_relations_against_staged_content(self) -> None:
        source = program()
        runtime = Runtime(source, CONTEXT)
        runtime.write(LOW, 5)
        narrowed = Relation(
            "bound",
            {"low": LOW, "high": HIGH},
            payload=AllOf(External("ordered"), Role("low", IntRange(0, 3))),
        )
        result = transform_with_mapping(
            source,
            {ORDER: narrowed},
            {LOW: LOW, HIGH: HIGH},
        )
        before = (runtime.active, dict(runtime.active.cells))

        with self.assertRaises(ActivationRejected) as raised:
            runtime.activate(result)

        self.assertEqual(raised.exception.relation, ORDER)
        self.assertEqual((runtime.active, dict(runtime.active.cells)), before)

        with self.assertRaises(ActivationRejected):
            runtime.trial(result)

    def test_relation_following_a_rename_keeps_holding(self) -> None:
        source = program()
        runtime = Runtime(source, CONTEXT)
        renamed = EntityID("upper")

        runtime.activate(
            transform_with_mapping(
                source,
                {renamed: CellDeclaration(IsKind("int"), 0)},
                {LOW: LOW, HIGH: renamed},
            )
        )

        self.assertEqual(runtime.read(renamed), 10)

        with self.assertRaises(RelationConstraintRejected):
            runtime.write(LOW, 11)


OWNER = EntityID("owner")
PART = EntityID("part")
GAUGE = EntityID("gauge")
WHOLE = EntityID("whole")


def mentions(content: Any, word: str) -> bool:
    if content == word:
        return True

    return isinstance(content, tuple) and any(
        mentions(item, word) for item in content
    )


# Anything the owner contributes, owned entities included, must not say
# "forbidden"; a gauge cell anywhere in it must stay at most 5.
WHOLE_CONTEXT = EvaluationContext({
    "clean": Evaluator(
        lambda subject: VIO if mentions(subject, "forbidden") else SAT
    ),
})
CLEAN_WHOLE = Relation("whole", {"whole": OWNER}, External("clean"))


def owned_program(part: Any = "fine", gauge: int = 0) -> State:
    return State.create(
        {
            OWNER: Value.create(OWNER, 1),
            PART: Value.create(PART, part),
            GAUGE: Value.create(GAUGE, CellDeclaration(IsKind("int"), gauge)),
            WHOLE: Value.create(WHOLE, CLEAN_WHOLE),
        },
        {OWNER: (PART,), PART: (GAUGE,)},
    )


class OwnedSubtreeTests(unittest.TestCase):
    """An endpoint that owns entities contributes its owned subtree."""

    def test_an_owner_contributes_its_value_and_owned_subtree(self) -> None:
        seen = []
        context = EvaluationContext({
            "clean": Evaluator(lambda subject: seen.append(subject) or SAT),
        })

        runtime = Runtime(owned_program(gauge=3), context)
        runtime.write(GAUGE, 4)

        expected = canonicalize({
            "whole": {
                "value": 1,
                "owned": {PART: {"value": "fine", "owned": {GAUGE: 3}}},
            },
        })
        self.assertEqual(seen[0], expected)
        self.assertEqual(
            seen[-1],
            canonicalize({
                "whole": {
                    "value": 1,
                    "owned": {PART: {"value": "fine", "owned": {GAUGE: 4}}},
                },
            }),
        )

    def test_an_owned_entity_can_violate_its_owners_relation(self) -> None:
        with self.assertRaises(RelationConstraintRejected) as raised:
            Runtime(owned_program(part="forbidden"), WHOLE_CONTEXT)

        self.assertEqual(raised.exception.relation, WHOLE)

    def test_activation_checks_the_changed_owned_subtree(self) -> None:
        source = owned_program()
        runtime = Runtime(source, WHOLE_CONTEXT)
        result = transform_with_mapping(
            source,
            {PART: "forbidden"},
            {entity: entity for entity in source.values},
        )

        with self.assertRaises(ActivationRejected) as raised:
            runtime.activate(result)

        self.assertEqual(raised.exception.relation, WHOLE)
        self.assertEqual(runtime.active.state, source)

    def test_writing_an_owned_cell_checks_its_owners_relations(self) -> None:
        state = State.create(
            {
                OWNER: Value.create(OWNER, 1),
                PART: Value.create(PART, "fine"),
                GAUGE: Value.create(GAUGE, CellDeclaration(IsKind("int"), 0)),
                WHOLE: Value.create(
                    WHOLE,
                    Relation("whole", {"whole": OWNER}, External("low")),
                ),
            },
            {OWNER: (PART,), PART: (GAUGE,)},
        )

        def low(subject: Any) -> ConstraintResult:
            whole = dict(subject[2])["whole"]
            part = dict(dict(whole[2])["owned"][2])[canonicalize(PART)]
            gauge = dict(dict(part[2])["owned"][2])[canonicalize(GAUGE)]
            return SAT if gauge <= 5 else VIO

        runtime = Runtime(state, EvaluationContext({"low": Evaluator(low)}))
        runtime.write(GAUGE, 5)

        with self.assertRaises(RelationConstraintRejected) as raised:
            runtime.write(GAUGE, 6)

        self.assertEqual(raised.exception.relation, WHOLE)
        self.assertEqual(runtime.read(GAUGE), 5)


class ConstraintRelationProperties(unittest.TestCase):
    def test_random_writes_never_break_the_relation(self) -> None:
        # A write is accepted exactly when both the cell constraint and the
        # relation hold afterwards; the relation holds after every step.
        for seed in range(200):
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                runtime = Runtime(program(), CONTEXT)

                for _ in range(30):
                    cell = rng.choice([LOW, HIGH])
                    content = rng.choice([rng.randrange(-5, 25), "x", True])
                    low, high = runtime.read(LOW), runtime.read(HIGH)
                    after = {LOW: low, HIGH: high, cell: content}
                    valid = (
                        IsKind("int").evaluate(content) is SAT
                        and after[LOW] <= after[HIGH]
                    )

                    if valid:
                        runtime.write(cell, content)
                    else:
                        with self.assertRaises(
                            (CellContentRejected, RelationConstraintRejected)
                        ):
                            runtime.write(cell, content)

                    self.assertLessEqual(runtime.read(LOW), runtime.read(HIGH))
                    self.assertEqual(
                        runtime.read(cell),
                        canonicalize(content) if valid else (low if cell == LOW else high),
                    )


if __name__ == "__main__":
    unittest.main()
