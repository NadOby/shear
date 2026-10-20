"""Frozen T5 constraint identity acceptance for SHEAR #123.

Execute supplies:
    reconstruct_constraint(expression)
        -> (original_canonical, reconstructed_canonical)

The two outputs must originate from actual candidate constraint
construction and reconstruction. Both preserve the canonical
semantic constraint representation.

The candidate must execute admitted ordinary SHEAR computation.
Returning host-generated expected values does not qualify.
Independent source-path audit remains mandatory.

This module is outside ordinary Plan-time discovery.
"""

from importlib import import_module
import unittest

from shear import (
    AllOf,
    AnyOf,
    External,
    IntRange,
    IsKind,
    Length,
    Not,
    OneOf,
    Role,
    canonical_serialize,
)
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
)


# Expressions follow the existing Task 24 adapter representation.
# Expected values are constructed independently using normative
# semantic constructors, never by invoking the candidate.
WITNESSES = (
    (("is_kind", "int"), IsKind("int")),
    (("int_range", None, 10), IntRange(None, 10)),
    (("length", 1, 3), Length(1, 3)),
    (("one_of", (True, 1, "x")), OneOf(True, 1, "x")),
    (("all_of",), AllOf()),
    (("any_of",), AnyOf()),
    (
        ("not", ("is_kind", "bool")),
        Not(IsKind("bool")),
    ),
    (
        ("role", "item", ("int_range", 0, 10)),
        Role("item", IntRange(0, 10)),
    ),
    (("external", "policy"), External("policy")),
    (
        ("all_of", ("is_kind", "int"),
         ("int_range", 0, 10)),
        AllOf(IsKind("int"), IntRange(0, 10)),
    ),
    (
        ("any_of", ("is_kind", "bool"),
         ("one_of", (None, "x"))),
        AnyOf(IsKind("bool"), OneOf(None, "x")),
    ),
    (
        ("all_of", ("is_kind", "int"),
         ("is_kind", "int")),
        AllOf(IsKind("int"), IsKind("int")),
    ),
    (
        ("one_of", ({"b": 2, "a": 1},)),
        OneOf({"a": 1, "b": 2}),
    ),
    (
        ("not", ("not", ("external", "missing"))),
        Not(Not(External("missing"))),
    ),
)


# Canonical equality must ignore composition input order and
# duplicate members while preserving operation type.
EQUIVALENT = (
    (
        ("all_of", ("is_kind", "int"),
         ("int_range", 0, 10)),
        ("all_of", ("int_range", 0, 10),
         ("is_kind", "int"), ("is_kind", "int")),
    ),
    (
        ("one_of", (1, True, "x")),
        ("one_of", ("x", True, 1, 1)),
    ),
    (
        ("any_of", ("external", "a"),
         ("external", "b")),
        ("any_of", ("external", "b"),
         ("external", "a"), ("external", "a")),
    ),
    (
        ("one_of", ({"a": 1, "b": 2},)),
        ("one_of", ({"b": 2, "a": 1},)),
    ),
)

DISTINCT = (
    (("is_kind", "bool"), ("is_kind", "int")),
    (("one_of", (True,)), ("one_of", (1,))),
    (("one_of", ((1, 2),)), ("one_of", ([1, 2],))),
    (
        ("all_of", ("is_kind", "int")),
        ("any_of", ("is_kind", "int")),
    ),
    (("external", "a"), ("external", "b")),
)


def encoded(value):
    return canonical_serialize(value)


class FrozenConstraintIdentityAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.adapter = import_module(
                "tests.constraint_functions_complete_candidate"
            )

        cls.entries = cls.adapter.EVALUATOR_ENTRIES
        if not callable(
            getattr(cls.adapter, "reconstruct_constraint", None)
        ):
            raise AssertionError(
                "candidate lacks reconstruct_constraint"
            )

    def reconstruct(self, expression):
        with candidate_execution_guard(self.entries) as opened:
            result = self.adapter.reconstruct_constraint(expression)

        self.assertTrue(
            opened, "constraint reconstruction bypassed admitted SHEAR"
        )
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        original, rebuilt = result

        for value in (original, rebuilt):
            self.assertIsInstance(value, tuple)
            self.assertEqual(value[0], "__type__")
            self.assertEqual(value[1], "constraint")

        self.assertEqual(encoded(original), encoded(rebuilt))
        return encoded(original)

    def test_reconstruct_all_constraint_families(self):
        self.assertEqual(len(WITNESSES), 14)

        for expression, expected in WITNESSES:
            with self.subTest(expression=expression):
                self.assertEqual(
                    self.reconstruct(expression),
                    encoded(expected.canonical_node()),
                )

    def test_canonical_equivalence(self):
        for left, right in EQUIVALENT:
            with self.subTest(left=left, right=right):
                self.assertEqual(
                    self.reconstruct(left),
                    self.reconstruct(right),
                )

    def test_canonical_distinctions(self):
        for left, right in DISTINCT:
            with self.subTest(left=left, right=right):
                self.assertNotEqual(
                    self.reconstruct(left),
                    self.reconstruct(right),
                )


if __name__ == "__main__":
    unittest.main()
