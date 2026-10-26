"""Adversarial regression for GH-123 recursive semantic-record reconstruction.

The approved D123-8 experiment requires every nested constraint to be
reconstructed by ordinary authenticated SHEAR, not reused from the input.
Canonical equality of the outer record alone cannot establish this.
"""

from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from shear import IsKind, Not, canonical_serialize, canonicalize, machine_semantics
from tests import constraint_functions_complete_candidate as candidate
from tests.constraint_functions_complete_acceptance import candidate_execution_guard


def _encoded(value: object) -> bytes:
    return canonical_serialize(canonicalize(value))


class RecursiveConstraintReconstructionTests(TestCase):
    def test_reconstructs_every_nested_constraint_with_admitted_record(self):
        # Counts describe the canonical constraint tree, not the source
        # expression's unnormalized order or number of duplicates.
        cases = (
            (("is_kind", "int"), 1),
            (("not", ("not", ("is_kind", "int"))), 3),
            (("role", "x", ("not", ("is_kind", "int"))), 3),
            (("all_of", ("is_kind", "int"),
              ("not", ("is_kind", "bool"))), 4),
            (("any_of", ("int_range", 0, 5),
              ("not", ("length", 1, 3))), 4),
            (("all_of",), 1),
            (("any_of",), 1),
        )
        native_execute = machine_semantics.execute

        for expression, expected_records in cases:
            with self.subTest(expression=expression):
                recorded_kinds = []

                def observe_record(operation, *operands):
                    result = native_execute(operation, *operands)
                    if operation == "RECORD":
                        recorded_kinds.append(operands[0])
                    return result

                with patch.object(machine_semantics, "execute", observe_record):
                    with candidate_execution_guard(candidate.EVALUATOR_ENTRIES) as opened:
                        original, rebuilt = candidate.reconstruct_constraint(expression)

                self.assertTrue(opened, "no authenticated SHEAR invocation")
                self.assertEqual(_encoded(original), _encoded(rebuilt))
                self.assertEqual(
                    recorded_kinds,
                    ["constraint"] * expected_records,
                    "nested records were reused instead of reconstructed",
                )

    def test_rebuilt_child_result_controls_rebuilt_parent(self):
        expression = ("not", ("not", ("is_kind", "int")))
        native_execute = machine_semantics.execute
        calls = []

        def perturb_innermost_record(operation, *operands):
            result = native_execute(operation, *operands)
            if operation == "RECORD":
                calls.append(result)
                if len(calls) == 1:
                    # Mutate the first SHEAR-constructed leaf. The outer
                    # reconstruction must consume this value through SHEAR.
                    return canonicalize(IsKind("str"))
            return result

        with patch.object(
            machine_semantics, "execute", perturb_innermost_record,
        ):
            with candidate_execution_guard(candidate.EVALUATOR_ENTRIES) as opened:
                original, rebuilt = candidate.reconstruct_constraint(expression)

        self.assertTrue(opened, "no authenticated SHEAR invocation")
        self.assertEqual(len(calls), 3, "not all nested records were built")
        self.assertEqual(_encoded(original), _encoded(Not(Not(IsKind("int")))))
        self.assertEqual(_encoded(rebuilt), _encoded(Not(Not(IsKind("str")))))
        self.assertNotEqual(_encoded(original), _encoded(rebuilt))
