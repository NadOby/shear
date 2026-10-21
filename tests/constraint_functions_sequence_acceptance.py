"""Generalized len and slice acceptance for SHEAR GH-123.

Plan-owned candidate tests; outside ordinary CI discovery.
Operations must execute through authenticated ordinary SHEAR.

Machine-result dependency is required separately for every
supported indexable semantic kind and each operation.

Perturbation uses genuine authenticated VM returns without
assuming a single invocation or a fixed adapter return shape.

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


INDEXABLE_KINDS = frozenset({
    "str", "bytes", "tuple", "list", "map",
    "cell", "constraint", "relation",
})


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
                    self.assert_result(
                        value, "slice",
                        (start, stop), value[start:stop],
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
        for value in (
            None, True, 42, EntityID("opaque"),
        ):
            with self.subTest(kind=kind_of(value)):
                self.assert_error(value, "len")
                self.assert_error(value, "slice", 0, 0)

    def observed_operation(
        self, value, operation, arguments, substitution=None
    ):
        """Observe actual authenticated machine results.

        substitution:
            (ordinal, entry, original_output, replacement)

        Only the selected evaluator return is replaced.
        The original machine invocation always executes.
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

    def dependency_cases(self, operation):
        """Two distinct inputs per semantic kind.

        Controls from other kinds may supply compatible VM
        returns when a kind has a fixed public field count.
        """
        samples = (
            ("str", "abc", "abcdef"),
            ("bytes", b"abc", b"abcdef"),
            ("tuple", (1, 2), (1, 2, 3, 4)),
            ("list", [1, 2], [1, 2, 3, 4]),
            ("map", {"a": 1}, {"a": 1, "b": 2, "c": 3}),
            (
                "cell",
                CellDeclaration(IsKind("int"), 5),
                CellDeclaration(IsKind("bool"), True),
            ),
            (
                "constraint",
                IntRange(0, 9),
                IsKind("int"),
            ),
            (
                "relation",
                Relation("first", {"a": EntityID("a")}),
                Relation(
                    "second",
                    {"b": EntityID("b")},
                    [1, 2],
                ),
            ),
        )

        cases = []

        for label, first, second in samples:
            self.assertEqual(kind_of(first), label)
            self.assertEqual(kind_of(second), label)

            for value, position in ((first, 0), (second, 1)):
                if operation == "len":
                    arguments = ()
                elif label in ("cell", "constraint"):
                    arguments = (
                        (0, 1) if position == 0 else (1, 2)
                    )
                elif label == "relation":
                    arguments = (
                        (0, 2) if position == 0 else (1, 3)
                    )
                else:
                    arguments = (
                        (0, 1) if position == 0 else (1, 2)
                    )

                cases.append((label, value, arguments))

        self.assertEqual(
            {case[0] for case in cases},
            INDEXABLE_KINDS,
        )
        return tuple(cases)

    def assert_machine_dependency(self, operation):
        observations = []

        for label, value, arguments in self.dependency_cases(
            operation
        ):
            result, returns, rejected = self.observed_operation(
                value, operation, arguments
            )
            self.assertIsNone(rejected)
            observations.append((
                label, value, arguments, result, returns
            ))

        # Every kind must establish its own causal witness.
        # Success for str cannot qualify bytes, maps or records.
        established = set()

        for semantic_kind in sorted(INDEXABLE_KINDS):
            subjects = [
                item for item in observations
                if item[0] == semantic_kind
            ]
            self.assertEqual(len(subjects), 2)

            compatible_count = 0
            successful = False

            for _, value, arguments, baseline, returns in subjects:
                if successful:
                    break

                for _, _, _, alternative, control_returns in observations:
                    if successful:
                        break

                    if canonical_bytes(baseline) == canonical_bytes(
                        alternative
                    ):
                        continue

                    for ordinal, (entry, original) in enumerate(returns):
                        if successful:
                            break

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

                            if not compatible or not distinct:
                                continue

                            compatible_count += 1
                            substitution = (
                                ordinal, entry, original, replacement
                            )

                            unchanged, _, unchanged_error = (
                                self.observed_operation(
                                    value, operation, arguments,
                                    (ordinal, entry, original, original),
                                )
                            )

                            self.assertIsNone(unchanged_error)
                            self.assertEqual(
                                canonical_bytes(unchanged),
                                canonical_bytes(baseline),
                                "unchanged VM result changed observation",
                            )

                            actual, _, rejected = self.observed_operation(
                                value, operation, arguments,
                                substitution,
                            )

                            if rejected is not None:
                                self.assert_rejection_provenance(
                                    rejected, operation, replacement
                                )
                                successful = True
                                break

                            if canonical_bytes(actual) != canonical_bytes(
                                baseline
                            ):
                                successful = True
                                break

            with self.subTest(
                operation=operation, kind=semantic_kind
            ):
                self.assertGreater(
                    compatible_count, 0,
                    "no compatible authenticated VM control; "
                    "dependency evidence is missing",
                )
                self.assertTrue(
                    successful,
                    f"{operation} for {semantic_kind} ignores "
                    "all compatible machine-result substitutions",
                )

            if successful:
                established.add(semantic_kind)

        self.assertEqual(established, INDEXABLE_KINDS)

    def test_len_depends_on_machine_output(self):
        self.assert_machine_dependency("len")

    def test_slice_depends_on_machine_output(self):
        self.assert_machine_dependency("slice")


if __name__ == "__main__":
    unittest.main()
