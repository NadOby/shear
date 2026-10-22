"""Generalized len and slice acceptance for SHEAR GH-123.

Plan-owned candidate tests, outside ordinary CI discovery.

All eight indexable kinds require independent authenticated
execution-dependency evidence for both len and slice.

No evaluator-entry sharing, machine-return schema, or fixed
invocation count is assumed.

For variable results, authenticated machine observations must
vary with the requested result. For every kind, a controlled
machine-return fault must propagate without host fallback.

These are necessary execution-dependency checks. Independent
source-path review must establish that the admitted computation
actually implements the requested semantic operation.
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

FIXED_LENGTH_KINDS = frozenset({
    "cell", "constraint", "relation",
})


class InjectedVMReturnFault(RuntimeError):
    """Test-owned fault raised after genuine admitted execution."""


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
            canonical_bytes(actual),
            canonical_bytes(expected),
        )
        self.assertEqual(
            kind_of(actual),
            kind_of(expected),
        )

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
                    (0, 0),
                    (0, size),
                    (1, 2),
                    (size, size),
                ):
                    self.assert_result(
                        value,
                        "slice",
                        (start, stop),
                        value[start:stop],
                    )

    def test_map_order_and_result_kind(self):
        entries = (
            ("b", 2),
            ("a", 1),
            ("c", 3),
        )
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
                (0, 0),
                (0, 3),
                (1, 2),
                (2, 3),
            ):
                self.assert_result(
                    value,
                    "slice",
                    (start, stop),
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
                    (
                        "roles",
                        (("target", EntityID("x")),),
                    ),
                    ("payload", [1, 2]),
                ),
            ),
        )
        for value, fields in records:
            with self.subTest(kind=kind_of(value)):
                self.assert_result(
                    value,
                    "len",
                    (),
                    len(fields),
                )
                for start, stop in (
                    (0, 0),
                    (0, len(fields)),
                    (1, 2),
                    (len(fields), len(fields)),
                ):
                    self.assert_result(
                        value,
                        "slice",
                        (start, stop),
                        fields[start:stop],
                    )

    def test_invalid_bounds(self):
        values = (
            "abc",
            b"abc",
            (1, 2, 3),
            [1, 2, 3],
            {"a": 1, "b": 2},
            CellDeclaration(IsKind("int"), 1),
            IntRange(0, 9),
        )
        for value in values:
            size = (
                len(value)
                if isinstance(
                    value, (str, bytes, tuple, list, dict)
                )
                else 2
            )

            # Representable wrong-kind and out-of-range inputs
            # must reach authenticated evaluator execution.
            for bounds in (
                (-1, 1),
                (0, size + 1),
                (2, 1),
                (True, 1),
                (0, False),
                ("0", 1),
            ):
                with self.subTest(
                    kind=kind_of(value),
                    bounds=bounds,
                ):
                    self.assert_error(
                        value,
                        "slice",
                        *bounds,
                    )

            # Floats are outside canonical SHEAR content and
            # cannot be supplied to the admitted VM. Reject
            # before evaluator entry, not as a VM LanguageError.
            with self.subTest(
                kind=kind_of(value),
                bounds=(0, 1.5),
            ):
                with candidate_execution_guard(self.entries) as opened:
                    with self.assertRaises(TypeError):
                        self.candidate.sequence_projection(
                            value,
                            "slice",
                            0,
                            1.5,
                        )
                self.assertFalse(
                    opened,
                    "unsupported float reached admitted evaluator code",
                )

    def test_unsupported_operand_kinds(self):
        for value in (
            None,
            True,
            42,
            EntityID("opaque"),
        ):
            with self.subTest(kind=kind_of(value)):
                self.assert_error(value, "len")
                self.assert_error(value, "slice", 0, 0)

    def dependency_cases(self, operation):
        samples = (
            ("str", "abc", "abcdef"),
            ("bytes", b"abc", b"abcdef"),
            ("tuple", (1, 2), (1, 2, 3, 4)),
            ("list", [1, 2], [1, 2, 3, 4]),
            (
                "map",
                {"a": 1},
                {"a": 1, "b": 2, "c": 3},
            ),
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
                Relation(
                    "first",
                    {"a": EntityID("a")},
                ),
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

            for position, value in enumerate((first, second)):
                if operation == "len":
                    arguments = ()
                elif label == "relation":
                    arguments = (
                        (0, 2) if position == 0 else (1, 3)
                    )
                else:
                    arguments = (
                        (0, 1) if position == 0 else (1, 2)
                    )

                cases.append(
                    (label, value, arguments)
                )

        self.assertEqual(
            {label for label, _, _ in cases},
            INDEXABLE_KINDS,
        )

        return tuple(cases)

    def observe_machine_results(
        self, value, operation, arguments
    ):
        """Capture genuine outputs without modifying execution."""
        returns = []

        with candidate_execution_guard(self.entries) as opened:
            guarded_run = RestrictedExecutor.run

            def observe_run(
                executor, deployment, entry, *args, **kwargs
            ):
                result = guarded_run(
                    executor,
                    deployment,
                    entry,
                    *args,
                    **kwargs,
                )
                if entry in self.entries:
                    returns.append((entry, result))
                return result

            with patch.object(
                RestrictedExecutor,
                "run",
                new=observe_run,
            ):
                observation = self.candidate.sequence_projection(
                    value,
                    operation,
                    *arguments,
                )

        self.assertTrue(
            opened,
            "sequence observation bypassed authenticated execution",
        )
        self.assertTrue(
            returns,
            "no admitted machine result observed",
        )

        return observation, tuple(returns)

    def assert_vm_fault_dependency(
        self, value, operation, arguments
    ):
        """An authenticated VM-result fault must not be bypassed.

        The fault is raised after an actual admitted execution.
        No alternative return shape or evaluator entry is required.
        """
        sentinel = InjectedVMReturnFault(
            f"controlled VM return fault: {operation}"
        )
        intercepted = []

        with candidate_execution_guard(self.entries) as opened:
            guarded_run = RestrictedExecutor.run

            def fault_run(
                executor, deployment, entry, *args, **kwargs
            ):
                result = guarded_run(
                    executor,
                    deployment,
                    entry,
                    *args,
                    **kwargs,
                )

                if entry in self.entries:
                    intercepted.append((entry, result))
                    raise sentinel

                return result

            with patch.object(
                RestrictedExecutor,
                "run",
                new=fault_run,
            ):
                caught = None
                try:
                    self.candidate.sequence_projection(
                        value,
                        operation,
                        *arguments,
                    )
                except BaseException as exc:
                    caught = exc

        self.assertTrue(
            opened,
            "fault injection bypassed authenticated execution",
        )
        self.assertTrue(
            intercepted,
            "no authenticated VM return was intercepted",
        )
        self.assertIs(
            caught,
            sentinel,
            "VM-return fault was swallowed, translated or bypassed",
        )

    def assert_machine_dependency(self, operation):
        observations = {}

        for label, value, arguments in self.dependency_cases(
            operation
        ):
            with self.subTest(
                operation=operation,
                kind=label,
                value=repr(value),
            ):
                result, machine_returns = (
                    self.observe_machine_results(
                        value,
                        operation,
                        arguments,
                    )
                )
                observations.setdefault(label, []).append(
                    (result, machine_returns)
                )

                self.assert_vm_fault_dependency(
                    value,
                    operation,
                    arguments,
                )

        self.assertEqual(
            set(observations),
            INDEXABLE_KINDS,
        )

        for label, cases in observations.items():
            with self.subTest(
                operation=operation,
                kind=label,
            ):
                self.assertEqual(len(cases), 2)

                first_result, first_returns = cases[0]
                second_result, second_returns = cases[1]

                # Fixed-field records may legitimately return the
                # same constant length from specialized evaluators.
                variable_result = (
                    operation == "slice"
                    or label not in FIXED_LENGTH_KINDS
                )

                if variable_result:
                    self.assertNotEqual(
                        canonical_bytes(first_result),
                        canonical_bytes(second_result),
                        "controls lack distinct semantic results",
                    )

                    first_machine = tuple(
                        (entry, canonical_bytes(value))
                        for entry, value in first_returns
                    )
                    second_machine = tuple(
                        (entry, canonical_bytes(value))
                        for entry, value in second_returns
                    )

                    self.assertNotEqual(
                        first_machine,
                        second_machine,
                        "distinct semantic results have "
                        "indistinguishable admitted VM returns",
                    )

    def test_len_depends_on_machine_output(self):
        self.assert_machine_dependency("len")

    def test_slice_depends_on_machine_output(self):
        self.assert_machine_dependency("slice")


if __name__ == "__main__":
    unittest.main()
