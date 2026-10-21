"""T5 semantic constraint identity acceptance for SHEAR #123.

Execute supplies:
    reconstruct_constraint(expression)
        -> (original_canonical, reconstructed_canonical)

Both outputs must originate from actual admitted SHEAR constraint
construction and reconstruction and retain canonical semantic identity.

Machine-output substitution must affect the adapter's observation or
trigger explicit fail-closed validation with operation and exact rejected
VM-output provenance.

Host-generated expected values and forged execution do not qualify.
Independent source-path and fallback audit remains mandatory.

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
    kind_of,
)
from shear.hosted_bootstrap import AdmissionRejected
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


# Canonical equality ignores composition input order and duplicate
# members while preserving the semantic constraint operation kind.
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

    def execute_reconstruction(self, expression):
        with candidate_execution_guard(self.entries) as opened:
            result = self.adapter.reconstruct_constraint(expression)

        self.assertTrue(
            opened, "constraint reconstruction bypassed admitted SHEAR"
        )
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        return result

    def reconstruct(self, expression):
        original, rebuilt = self.execute_reconstruction(expression)

        for value in (original, rebuilt):
            self.assertEqual(kind_of(value), "constraint")

        self.assertEqual(encoded(original), encoded(rebuilt))
        return encoded(original)

    def test_reconstruct_all_constraint_families(self):
        self.assertEqual(len(WITNESSES), 14)

        for expression, expected in WITNESSES:
            with self.subTest(expression=expression):
                self.assertEqual(
                    self.reconstruct(expression),
                    encoded(expected),
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

    def test_reconstruction_depends_on_valid_machine_output(self):
        operation = "reconstruct_constraint"
        expression = ("is_kind", "int")
        control = ("int_range", 0, 10)

        baseline = self.execute_reconstruction(expression)
        alternative = self.execute_reconstruction(control)

        self.assertNotEqual(
            encoded(baseline),
            encoded(alternative),
            "reconstruction controls must have distinct results",
        )

        # Both valid outputs must survive an unchanged machine-output
        # substitution for their corresponding inputs.
        for source, expected in (
            (expression, baseline),
            (control, alternative),
        ):
            with candidate_execution_guard(
                self.entries, forced=expected,
            ) as opened:
                actual = self.adapter.reconstruct_constraint(source)

            self.assertTrue(opened)
            self.assertEqual(encoded(actual), encoded(expected))

        # Substitute a different but well-formed reconstruction result.
        # The adapter may accept it as authoritative machine output
        # or reject it explicitly. It must not silently replace it
        # with a host-computed answer.
        rejected = None
        with candidate_execution_guard(
            self.entries, forced=alternative,
        ) as opened:
            try:
                actual = self.adapter.reconstruct_constraint(expression)
            except (ValueError, TypeError, AdmissionRejected) as exc:
                rejected = exc

        self.assertTrue(
            opened, "reconstruction perturbation bypassed admitted SHEAR"
        )

        if rejected is None:
            self.assertEqual(
                encoded(actual),
                encoded(alternative),
                "reconstruction ignored controlled VM output",
            )
            return

        self.assertEqual(
            getattr(rejected, "projection_operation", None),
            operation,
            "rejection lacks reconstruction-operation provenance",
        )
        self.assertTrue(
            hasattr(rejected, "rejected_vm_output"),
            "rejection lacks rejected-VM-output provenance",
        )
        self.assertEqual(
            encoded(rejected.rejected_vm_output),
            encoded(alternative),
            "rejection misidentifies the substituted VM output",
        )
        self.assertTrue(
            str(rejected).strip(),
            "reconstruction rejection lacks an explanation",
        )


if __name__ == "__main__":
    unittest.main()
