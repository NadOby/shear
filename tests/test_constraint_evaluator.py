"""Authenticated execution tests for ordinary SHEAR constraint helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from shear import bytecode, canonical_serialize, canonicalize, machine
from shear import (
    AllOf,
    AnyOf,
    CellDeclaration,
    EntityID,
    External,
    IntRange,
    IsKind,
    Length,
    Not,
    OneOf,
    Relation,
    Role,
)
from shear.examples._support import program
from shear.examples.constraint_evaluator import (
    BOUND_ENTRY,
    BUDGET_STEP,
    EVALUATE,
    INT_RANGE,
    IS_KIND,
    LENGTH,
    LOGIC_ALL,
    LOGIC_ANY,
    LOGIC_NOT,
    ONE_OF,
    VALUE_EQUAL,
    bound_evaluator_entities,
    evaluator_entities,
)
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from shear.lang import load
from tests.constraint_functions_complete_acceptance import forbid_incumbent


SAT = "satisfied"
VIO = "violated"
UNK = "unknown"


def _no_lowering(*args, **kwargs):
    raise AssertionError("unauthenticated host lowering")


def _canonical(value):
    return canonical_serialize(canonicalize(value))


class ConstraintEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = load(program(evaluator_entities()))
        cls.executor = RestrictedExecutor()
        cls.deployment = cls.executor.deploy(cls.source)

    def execute(self, entry, *arguments, executor=None, deployment=None):
        executor = self.executor if executor is None else executor
        deployment = self.deployment if deployment is None else deployment
        state = deployment._target.state
        opened = []
        original_open = machine._open

        def observe(activation, args, *rest, **kwargs):
            chunk, env, node = original_open(
                activation, args, *rest, **kwargs
            )
            self.assertEqual(
                activation.hold.version.state.id,
                deployment.source_state_id,
            )
            key = (node, state.values[node].version_id)
            artifact = deployment.artifacts.get(key)
            self.assertIsNotNone(artifact)
            self.assertIs(chunk, artifact.chunk)
            self.assertEqual(artifact.owner, activation.entity)
            self.assertEqual(
                artifact.produced_by,
                deployment.compiler_generation,
            )
            artifact.verify()
            opened.append(activation.entity)
            return chunk, env, node

        with (
            forbid_incumbent(),
            patch.object(machine, "_open", side_effect=observe),
            patch.object(bytecode, "chunk_of", side_effect=_no_lowering),
            patch.object(bytecode, "lower_value", side_effect=_no_lowering),
        ):
            result = executor.run(deployment, entry, *arguments)

        self.assertIn(entry, opened, "evaluator was not executed")
        return result

    def assert_execution(self, entry, arguments, expected):
        actual = self.execute(entry, *arguments)
        self.assertEqual(_canonical(actual), _canonical(expected))

    def test_strong_kleene_logic(self):
        conjunction = {
            (SAT, SAT): SAT,
            (SAT, VIO): VIO,
            (SAT, UNK): UNK,
            (VIO, SAT): VIO,
            (VIO, VIO): VIO,
            (VIO, UNK): VIO,
            (UNK, SAT): UNK,
            (UNK, VIO): VIO,
            (UNK, UNK): UNK,
        }
        disjunction = {
            (SAT, SAT): SAT,
            (SAT, VIO): SAT,
            (SAT, UNK): SAT,
            (VIO, SAT): SAT,
            (VIO, VIO): VIO,
            (VIO, UNK): UNK,
            (UNK, SAT): SAT,
            (UNK, VIO): UNK,
            (UNK, UNK): UNK,
        }
        for arguments, expected in conjunction.items():
            with self.subTest(operation="all", arguments=arguments):
                self.assert_execution(LOGIC_ALL, arguments, expected)
        for arguments, expected in disjunction.items():
            with self.subTest(operation="any", arguments=arguments):
                self.assert_execution(LOGIC_ANY, arguments, expected)
        for value, expected in (
            (SAT, VIO), (VIO, SAT), (UNK, UNK)
        ):
            with self.subTest(operation="not", value=value):
                self.assert_execution(LOGIC_NOT, (value,), expected)

    def test_exact_budget_step(self):
        for remaining, expected in (
            (None, (True, None)),
            (0, (False, 0)),
            (1, (True, 0)),
            (2, (True, 1)),
            (100, (True, 99)),
        ):
            with self.subTest(remaining=remaining):
                self.assert_execution(
                    BUDGET_STEP, (remaining,), expected
                )

    def test_kind_and_integer_boundaries(self):
        cases = (
            (IS_KIND, (True, "bool"), SAT),
            (IS_KIND, (True, "int"), VIO),
            (IS_KIND, (1, "int"), SAT),
            (IS_KIND, (None, "none"), SAT),
            (IS_KIND, (EntityID("x"), "entity_id"), SAT),
            (INT_RANGE, (0, 0, 10), SAT),
            (INT_RANGE, (10, 0, 10), SAT),
            (INT_RANGE, (11, 0, 10), VIO),
            (INT_RANGE, (-1, 0, None), VIO),
            (INT_RANGE, (-1, None, 0), SAT),
            (INT_RANGE, (True, None, None), VIO),
            (INT_RANGE, ("5", None, None), VIO),
        )
        for entry, arguments, expected in cases:
            with self.subTest(entry=entry, arguments=repr(arguments)):
                self.assert_execution(entry, arguments, expected)

    def test_semantic_lengths(self):
        cases = (
            ("e\u0301", 2, 2, SAT),
            ("\U0001f600", 1, 1, SAT),
            (b"\x00\xff", 2, 2, SAT),
            ((1, True), 2, 2, SAT),
            ([1, True], 2, 2, SAT),
            ({"z": 1, "a": 2}, 2, 2, SAT),
            ("a", 2, None, VIO),
            (b"\x00", 2, None, VIO),
            (123, 0, None, VIO),
            (None, 0, None, VIO),
        )
        for subject, minimum, maximum, expected in cases:
            with self.subTest(subject=repr(subject)):
                self.assert_execution(
                    LENGTH, (subject, minimum, maximum), expected
                )

    def test_recursive_type_sensitive_equality(self):
        original = {
            "z": [1, True],
            "a": (b"\x00", {"inner": False}),
        }
        reordered = {
            "a": (b"\x00", {"inner": False}),
            "z": [1, True],
        }
        changed = {
            "a": (b"\x00", {"inner": False}),
            "z": [1, 1],
        }
        record = CellDeclaration(
            IsKind("map"), {"nested": [1, True]}
        )
        equivalent = CellDeclaration(
            IsKind("map"), {"nested": [1, True]}
        )
        relation = Relation(
            "example", {"endpoint": EntityID("target")}, [1, True]
        )
        cases = (
            (1, True, False),
            (1, 1, True),
            ("1", 1, False),
            (b"a", "a", False),
            ("é", "e\u0301", False),
            ((1, True), (1, 1), False),
            ([1, 2], (1, 2), False),
            (original, reordered, True),
            (original, changed, False),
            (record, equivalent, True),
            (relation, relation, True),
        )
        for left, right, expected in cases:
            with self.subTest(left=repr(left), right=repr(right)):
                self.assert_execution(
                    VALUE_EQUAL, (left, right), expected
                )

    def test_one_of_recursive_matching(self):
        original = {
            "z": [1, True],
            "a": (b"\x00", {"inner": False}),
        }
        reordered = {
            "a": (b"\x00", {"inner": False}),
            "z": [1, True],
        }
        cases = (
            (1, (), VIO),
            (1, (True, "1"), VIO),
            (1, (True, 1), SAT),
            (reordered, (None, original), SAT),
            ({"a": [1, 1]}, (original,), VIO),
            ("é", ("e\u0301",), VIO),
        )
        for subject, values, expected in cases:
            with self.subTest(subject=repr(subject)):
                self.assert_execution(
                    ONE_OF, (subject, values), expected
                )

    def test_recursive_primitives(self):
        cases = (
            ("é", IsKind("str"), None, (SAT, None)),
            ("é", IsKind("str"), 1, (SAT, 0)),
            ("é", IsKind("str"), 0, (UNK, 0)),
            (True, IntRange(0, 10), 1, (VIO, 0)),
            ("e\u0301", Length(2, 2), 1, (SAT, 0)),
            (b"\x00\xff", Length(2, 2), 1, (SAT, 0)),
            ({"a": 1, "b": 2}, Length(2, 2), 1, (SAT, 0)),
            ((1, True), OneOf([1, True], (1, True)), 1, (SAT, 0)),
            (True, OneOf(1, "true"), 1, (VIO, 0)),
            (IsKind("int"), IsKind("constraint"), 1, (SAT, 0)),
            (EntityID("item"), IsKind("entity_id"), 1, (SAT, 0)),
            (5, External("missing"), 1, (UNK, 0)),
            (5, External("missing"), 0, (UNK, 0)),
        )
        for subject, constraint, budget, expected in cases:
            with self.subTest(
                subject=repr(subject),
                constraint=repr(constraint),
                budget=budget,
            ):
                self.assert_execution(
                    EVALUATE, (subject, constraint, budget), expected
                )

    def test_recursive_composition_and_budgets(self):
        both = AllOf(IsKind("int"), IntRange(0, 10))
        either = AnyOf(IsKind("int"), IntRange(0, 10))
        cases = (
            (5, AllOf(), 1, (SAT, 0)),
            (5, AnyOf(), 1, (VIO, 0)),
            (5, both, 0, (UNK, 0)),
            (5, both, 1, (UNK, 0)),
            (5, both, 2, (UNK, 0)),
            (5, both, 3, (SAT, 0)),
            (True, both, 2, (VIO, 0)),
            (True, both, 3, (VIO, 1)),
            (5, either, 2, (SAT, 0)),
            (5, either, 3, (SAT, 1)),
            (True, either, 2, (UNK, 0)),
            (True, either, 3, (VIO, 0)),
            (5, Not(IsKind("bool")), 1, (UNK, 0)),
            (5, Not(IsKind("bool")), 2, (SAT, 0)),
            (5, Not(Not(IsKind("int"))), 3, (SAT, 0)),
            (5, Not(Not(IsKind("int"))), 2, (UNK, 0)),
        )
        for subject, constraint, budget, expected in cases:
            with self.subTest(
                subject=repr(subject),
                constraint=repr(constraint),
                budget=budget,
            ):
                self.assert_execution(
                    EVALUATE, (subject, constraint, budget), expected
                )

    def test_role_traversal_and_nested_composition(self):
        role = Role("x", IsKind("int"))
        nested = AllOf(
            Not(IsKind("bool")),
            AnyOf(IsKind("int"), IntRange(0, 10)),
        )
        cases = (
            ({"x": 5}, role, 2, (SAT, 0)),
            ({"x": True}, role, 2, (VIO, 0)),
            ({"x": 5}, role, 1, (UNK, 0)),
            ({}, role, 2, (VIO, 1)),
            ({"other": 5}, role, 2, (VIO, 1)),
            (5, role, 2, (VIO, 1)),
            (5, nested, 5, (SAT, 0)),
            (5, nested, 4, (UNK, 0)),
            (5, nested, None, (SAT, None)),
        )
        for subject, constraint, budget, expected in cases:
            with self.subTest(
                subject=repr(subject),
                constraint=repr(constraint),
                budget=budget,
            ):
                self.assert_execution(
                    EVALUATE, (subject, constraint, budget), expected
                )

    def test_bound_entry_reuses_admitted_preparation(self):
        cases = (
            (
                OneOf(1, "1"),
                None,
                ((1, SAT), (True, VIO), ("1", SAT), (2, VIO)),
            ),
            (
                AllOf(IsKind("int"), IntRange(0, 10)),
                3,
                ((5, SAT), (20, VIO), ("5", VIO)),
            ),
            (
                Role("x", IsKind("int")),
                2,
                (({"x": 3}, SAT), ({"x": True}, VIO),
                 ({"y": 3}, VIO)),
            ),
            (
                IsKind("int"),
                0,
                ((5, UNK), (True, UNK)),
            ),
        )
        for constraint, budget, witnesses in cases:
            with self.subTest(constraint=repr(constraint), budget=budget):
                source = load(program(
                    bound_evaluator_entities(constraint, budget)
                ))
                executor = RestrictedExecutor()
                deployment = executor.deploy(source)
                snapshot = tuple(sorted(
                    (
                        node.value,
                        version.value,
                        artifact.artifact_id,
                    )
                    for (node, version), artifact
                    in deployment.artifacts.items()
                ))

                for subject, expected in witnesses:
                    actual = self.execute(
                        BOUND_ENTRY,
                        subject,
                        executor=executor,
                        deployment=deployment,
                    )
                    self.assertEqual(actual, expected)
                    self.assertEqual(
                        snapshot,
                        tuple(sorted(
                            (
                                node.value,
                                version.value,
                                artifact.artifact_id,
                            )
                            for (node, version), artifact
                            in deployment.artifacts.items()
                        )),
                    )


if __name__ == "__main__":
    unittest.main()
