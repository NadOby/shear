"""Independent generic canonical-projection acceptance for SHEAR #123.

Execute supplies these candidate functions:
    inspect_projection(value) -> (kind, length_or_none, reconstructed)
    equal_projection(left, right) -> bool

Both must use ordinary admitted SHEAR functions to inspect generic
canonical data. Host-only inspection does not qualify.

This module is deliberately outside ordinary test discovery.
Execute registers it only after implementing the candidate.
"""

from importlib import import_module
import unittest

from shear import (
    CellDeclaration,
    EntityID,
    StateID,
    VersionID,
    IsKind,
    Relation,
    canonicalize,
    canonical_serialize,
    kind_of,
)
from shear.closures import Closure
from tests.constraint_functions_complete_acceptance import (
    EvaluatorMachineFault,
    candidate_execution_guard,
    forbid_incumbent,
)


KINDS = (
    ("none", None),
    ("bool", True),
    ("int", 5),
    ("str", "e\u0301"),
    ("bytes", b"a\x00b"),
    ("entity_id", EntityID("sample")),
    ("version_id", VersionID("version")),
    ("state_id", StateID("state")),
    ("tuple", (1, "a")),
    ("list", [1, "a"]),
    ("map", {"b": 2, "a": 1}),
    ("cell", CellDeclaration(IsKind("int"), 3)),
    ("constraint", IsKind("int")),
    ("relation", Relation(
        "sample",
        {"item": EntityID("sample")},
        {"metadata": [1, 2]},
    )),
    ("closure", Closure(
        EntityID("owner"),
        EntityID("body"),
        ("parameter",),
        (("captured", 7),),
    )),
)

NESTED = (
    {"root": {
        "value": 1,
        "owned": {EntityID("child"): 2},
    }},
    (["x", b"\x00"], {"b": (True, 1), "a": [None]}),
    CellDeclaration(IsKind("map"), {"b": 2, "a": 1}),
    Relation("nested", {}, {"items": [1, ("a", b"b")]}),
)

EQUALITY = (
    (1, 1, True),
    (True, 1, False),
    (1, "1", False),
    ("a", b"a", False),
    ((1, 2), [1, 2], False),
    ({"a": 1, "b": 2}, {"b": 2, "a": 1}, True),
    (EntityID("x"), EntityID("x"), True),
    (EntityID("x"), VersionID("x"), False),
    (StateID("x"), VersionID("x"), False),
    ({"x": True}, {"x": 1}, False),
)

COUNTABLE = frozenset({"str", "bytes", "tuple", "list", "map"})


def canonical_bytes(value):
    return canonical_serialize(canonicalize(value))


class GenericProjectionAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.candidate = import_module(
                "tests.constraint_functions_complete_candidate"
            )

        cls.entries = cls.candidate.EVALUATOR_ENTRIES
        for name in ("inspect_projection", "equal_projection"):
            if not callable(getattr(cls.candidate, name, None)):
                raise AssertionError(
                    f"candidate does not implement {name}"
                )

    def inspect(self, value):
        before = canonical_bytes(value)
        with candidate_execution_guard(self.entries) as opened:
            result = self.candidate.inspect_projection(value)

        self.assertTrue(opened, "projection did not execute SHEAR")
        self.assertEqual(canonical_bytes(value), before)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)

        kind, length, reconstructed = result
        self.assertEqual(canonical_bytes(reconstructed), before)
        return kind, length

    def test_all_fifteen_kinds(self):
        self.assertEqual(len(KINDS), 15)
        self.assertEqual(len({kind for kind, _ in KINDS}), 15)

        for kind, value in KINDS:
            with self.subTest(kind=kind):
                self.assertEqual(kind_of(value), kind)
                observed_kind, observed_length = self.inspect(value)
                self.assertEqual(observed_kind, kind)

                expected_length = (
                    len(value)
                    if kind in COUNTABLE
                    else None
                )
                self.assertEqual(observed_length, expected_length)

    def test_nested_roundtrip(self):
        for value in NESTED:
            with self.subTest(value=repr(value)):
                observed_kind, _ = self.inspect(value)
                self.assertEqual(observed_kind, kind_of(value))

    def test_canonical_map_order(self):
        first = {"a": 1, "b": 2}
        second = {"b": 2, "a": 1}
        self.assertEqual(canonical_bytes(first), canonical_bytes(second))

        self.assertEqual(self.inspect(first), self.inspect(second))

    def test_type_sensitive_equality(self):
        for left, right, expected in EQUALITY:
            with self.subTest(left=repr(left), right=repr(right)):
                independent = canonical_bytes(left) == canonical_bytes(right)
                self.assertIs(independent, expected)

                with candidate_execution_guard(self.entries) as opened:
                    actual = self.candidate.equal_projection(left, right)

                self.assertTrue(opened, "equality did not execute SHEAR")
                self.assertIs(type(actual), bool)
                self.assertIs(actual, expected)

    def test_projection_depends_on_machine_execution(self):
        for _, value in KINDS:
            with self.subTest(value=repr(value)):
                with candidate_execution_guard(
                    self.entries, fault=True,
                ) as opened:
                    with self.assertRaises(EvaluatorMachineFault):
                        self.candidate.inspect_projection(value)
                self.assertTrue(opened)


if __name__ == "__main__":
    unittest.main()
