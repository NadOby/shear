"""Generalized len and slice acceptance for SHEAR GH-123.

Plan-owned candidate tests; outside ordinary CI discovery.
The adapter must use authenticated SHEAR execution, not host
implementations of the requested operations.

Machine perturbation observes actual RestrictedExecutor returns.
No single-invocation or adapter-return-shape assumption is made.
Independent source-path and fallback audit remains mandatory.
"""

from importlib import import_module
from unittest.mock import patch
import unittest

from shear import (
    CellDeclaration,
    EntityID,
    IntRange,
    IsKind,
    Relation,
    kind_of,
)
from shear.hosted_bootstrap import AdmissionRejected
from shear.hosted_bootstrap.restricted import RestrictedExecutor
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

    def observed_operation(
        self, value, operation, arguments, substitution=None
    ):
        """Capture genuine authenticated machine returns.

        substitution is:
            (ordinal, entry, original_output, replacement)

        Only the selected admitted evaluator return is replaced.
        The original machine invocation always executes first.
        """
        returns = []
        replaced = False
        observation = None
        rejection = None

        with candidate_execution_guard(self.entries) as opened:
            guarded_run = RestrictedExecutor.run

            def observe_run(
                executor, deployment, entry, *args, **kwargs
            ):
                nonlocal replaced

                result = guarded_run(
                    executor, deployment, entry,
                    *args, **kwargs
                )

                if entry not in self.entries:
                    return result

                ordinal = len(returns)
                returns.append((entry, result))

                if substitution is None:
                    return result

                target, selected_entry, original, replacement = (
                    substitution
                )

                if ordinal != target:
                    return result

                self.assertEqual(entry, selected_entry)
                self.assertEqual(
                    canonical_bytes(result),
                    canonical_bytes(original),
                    "selected VM output changed unexpectedly",
                )
                self.assertIs(
                    type(result), type(replacement),
                    "replacement changes machine output type",
                )

                replaced = True
                return replacement

            with patch.object(
                RestrictedExecutor, "run", new=observe_run
            ):
                try:
                    observation = self.candidate.sequence_projection(
                        value, operation, *arguments
                    )
                except (
                    ValueError, TypeError, AdmissionRejected
                ) as exc:
                    rejection = exc

        self.assertTrue(
            opened,
            f"{operation}: no authenticated evaluator entered",
        )
        self.assertTrue(
            returns,
            f"{operation}: no authenticated VM result observed",
        )

        if substitution is not None:
            self.assertTrue(
                replaced,
                f"{operation}: selected VM output not substituted",
            )

        return observation, tuple(returns), rejection

    def assert_rejection_provenance(
        self, rejected, operation, replacement
    ):
        self.assertEqual(
            getattr(rejected, "projection_operation", None),
            operation,
            "rejection lacks the requested operation",
        )
        self.assertTrue(
            hasattr(rejected, "rejected_vm_output"),
            "rejection lacks rejected VM-output provenance",
        )
        self.assertEqual(
            canonical_bytes(rejected.rejected_vm_output),
            canonical_bytes(replacement),
            "rejection identifies the wrong VM output",
        )
        self.assertTrue(
            str(rejected).strip(),
            "rejection lacks an explanation",
        )

    def assert_machine_dependency(self, operation, cases):
        observations = []

        for value, arguments in cases:
            result, returns, rejected = self.observed_operation(
                value, operation, arguments
            )
            self.assertIsNone(rejected)
            observations.append((
                value, arguments, result, returns
            ))

        candidates = []

        for value, arguments, baseline, returns in observations:
            for _, _, alternative, control_returns in observations:
                if canonical_bytes(baseline) == canonical_bytes(
                    alternative
                ):
                    continue

                for ordinal, (entry, original) in enumerate(returns):
                    for control_entry, replacement in control_returns:
                        if entry != control_entry:
                            continue
                        if type(original) is not type(replacement):
                            continue

                        try:
                            compatible = (
                                kind_of(original)
                                == kind_of(replacement)
                            )
                            distinct = (
                                canonical_bytes(original)
                                != canonical_bytes(replacement)
                            )
                        except (TypeError, ValueError):
                            continue

                        if compatible and distinct:
                            candidates.append((
                                value, arguments, baseline,
                                ordinal, entry, original, replacement,
                            ))

        self.assertTrue(
            candidates,
            f"{operation}: no distinct compatible authenticated "
            "VM outputs found for controlled substitution",
        )

        for (
            value, arguments, baseline,
            ordinal, entry, original, replacement
        ) in candidates:
            unchanged, _, unchanged_error = self.observed_operation(
                value, operation, arguments,
                (ordinal, entry, original, original),
            )
            self.assertIsNone(unchanged_error)
            self.assertEqual(
                canonical_bytes(unchanged),
                canonical_bytes(baseline),
                "unchanged VM-output control changed observation",
            )

            actual, _, rejected = self.observed_operation(
                value, operation, arguments,
                (ordinal, entry, original, replacement),
            )

            if rejected is not None:
                self.assert_rejection_provenance(
                    rejected, operation, replacement
                )
                return

            if canonical_bytes(actual) != canonical_bytes(baseline):
                return

        self.fail(
            f"{operation}: all controlled VM-output substitutions "
            "were ignored"
        )

    def test_len_depends_on_machine_output(self):
        self.assert_machine_dependency(
            "len",
            (
                ("a", ()),
                ("abcd", ()),
                (b"ab", ()),
                (b"abcdef", ()),
                ((1, 2), ()),
                ((1, 2, 3, 4), ()),
                ({"a": 1}, ()),
                ({"a": 1, "b": 2, "c": 3}, ()),
            ),
        )

    def test_slice_depends_on_machine_output(self):
        self.assert_machine_dependency(
            "slice",
            (
                ("abcdef", (0, 2)),
                ("abcdef", (2, 4)),
                (b"abcdef", (0, 2)),
                (b"abcdef", (2, 4)),
                ((1, 2, 3, 4), (0, 2)),
                ((1, 2, 3, 4), (2, 4)),
                ([1, 2, 3, 4], (0, 2)),
                ([1, 2, 3, 4], (2, 4)),
            ),
        )


if __name__ == "__main__":
    unittest.main()
