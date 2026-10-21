"""Generalized len and slice acceptance for SHEAR GH-123.

Plan-owned candidate tests; not part of ordinary CI discovery.
The adapter must use authenticated SHEAR execution, not host
implementations of the requested operations.
"""

from importlib import import_module
import unittest

from shear import (
    CellDeclaration,
    EntityID,
    IntRange,
    IsKind,
    Relation,
    kind_of,
)
from shear.lang import LanguageError
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
)
from tests.constraint_functions_projection_adversarial import (
    canonical_bytes,
)


class SequenceOperationAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.candidate = import_module(
                "tests.constraint_functions_complete_candidate"
            )
        cls.entries = cls.candidate.EVALUATOR_ENTRIES
        if not callable(
            getattr(cls.candidate, "sequence_projection", None)
        ):
            raise AssertionError(
                "candidate lacks sequence_projection"
            )

    def execute(self, value, operation, *arguments):
        with candidate_execution_guard(self.entries) as opened:
            result = self.candidate.sequence_projection(
                value, operation, *arguments
            )
        self.assertTrue(
            opened,
            f"{operation} bypassed admitted SHEAR execution",
        )
        return result

    def assert_result(self, value, operation, arguments, expected):
        actual = self.execute(value, operation, *arguments)
        self.assertEqual(
            canonical_bytes(actual), canonical_bytes(expected),
        )
        self.assertEqual(kind_of(actual), kind_of(expected))

    def assert_error(self, value, operation, *arguments):
        with candidate_execution_guard(self.entries) as opened:
            with self.assertRaises(LanguageError):
                self.candidate.sequence_projection(
                    value, operation, *arguments
                )
        self.assertTrue(opened)

    def test_sequence_lengths_and_slices(self):
        cases = (
            ("e\u0301\U0001f600", "str", 3),
            (b"\x00\xff\x10", "bytes", 3),
            ((1, True, "x"), "tuple", 3),
            ([1, True, "x"], "list", 3),
        )
        for value, semantic_kind, size in cases:
            with self.subTest(kind=semantic_kind):
                self.assert_result(value, "len", (), size)
                for start, stop in (
                    (0, 0), (0, size),
                    (1, 2), (size, size),
                ):
                    expected = value[start:stop]
                    self.assert_result(
                        value, "slice",
                        (start, stop), expected,
                    )

    def test_map_order_and_result_kind(self):
        entries = (("b", 2), ("a", 1), ("c", 3))
        expected = tuple(sorted(
            entries,
            key=lambda pair: canonical_bytes(pair[0]),
        ))
        for value in (
            dict(entries),
            dict(reversed(entries)),
        ):
            self.assert_result(value, "len", (), 3)
            for start, stop in (
                (0, 0), (0, 3), (1, 2), (2, 3),
            ):
                self.assert_result(
                    value, "slice", (start, stop),
                    expected[start:stop],
                )

    def test_record_field_counts_and_slices(self):
        records = (
            (
                CellDeclaration(IsKind("int"), 5),
                (
                    ("constraint", IsKind("int")),
                    ("initial", 5),
                ),
            ),
            (
                IntRange(0, 9),
                (
                    ("form", "int_range"),
                    ("arguments", (0, 9)),
                ),
            ),
            (
                Relation(
                    "sample",
                    {"target": EntityID("x")},
                    [1, 2],
                ),
                (
                    ("kind", "sample"),
                    ("roles", (("target", EntityID("x")),)),
                    ("payload", [1, 2]),
                ),
            ),
        )
        for value, fields in records:
            with self.subTest(kind=kind_of(value)):
                self.assert_result(
                    value, "len", (), len(fields),
                )
                for start, stop in (
                    (0, 0), (0, len(fields)),
                    (1, 2), (len(fields), len(fields)),
                ):
                    self.assert_result(
                        value, "slice", (start, stop),
                        fields[start:stop],
                    )

    def test_invalid_bounds(self):
        values = (
            "abc", b"abc", (1, 2, 3),
            [1, 2, 3], {"a": 1, "b": 2},
            CellDeclaration(IsKind("int"), 1),
            IntRange(0, 9),
        )
        for value in values:
            size = len(value) if isinstance(
                value, (str, bytes, tuple, list, dict)
            ) else 2
            for bounds in (
                (-1, 1),
                (0, size + 1),
                (2, 1),
                (True, 1),
                (0, False),
                (0, 1.5),
                ("0", 1),
            ):
                with self.subTest(
                    kind=kind_of(value), bounds=bounds
                ):
                    self.assert_error(value, "slice", *bounds)

    def test_unsupported_operand_kinds(self):
        values = (
            None, True, 42, EntityID("opaque"),
        )
        for value in values:
            with self.subTest(kind=kind_of(value)):
                self.assert_error(value, "len")
                self.assert_error(value, "slice", 0, 0)


if __name__ == "__main__":
    unittest.main()
