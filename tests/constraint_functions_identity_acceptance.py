"""T5 semantic constraint identity acceptance for SHEAR #123.

Execute supplies:
    reconstruct_constraint(expression)
        -> (original_canonical, reconstructed_canonical)

Both outputs must originate from admitted SHEAR computation and
retain canonical semantic identity.

Machine-output perturbation targets an actual authenticated VM
return, not an assumed adapter return shape or invocation count.

Host-generated expected values and forged execution do not qualify.
Independent source-path and fallback audit remains mandatory.

This module is outside ordinary Plan-time discovery.
"""

from importlib import import_module
from unittest.mock import patch
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
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
)


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
            opened,
            "constraint reconstruction bypassed admitted SHEAR",
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

    def observed_reconstruction(self, expression, substitution=None):
        """Observe actual admitted machine returns.

        A substitution is:
            (ordinal, entry, original_vm_output, replacement)

        The ordinal counts admitted evaluator returns only.
        Every original VM invocation still executes and passes
        through the existing authenticated execution guard.
        """
        returns = []
        substituted = False
        observation = None
        rejection = None

        with candidate_execution_guard(self.entries) as opened:
            guarded_run = RestrictedExecutor.run

            def observe_run(
                executor, deployment, entry, *args, **kwargs
            ):
                nonlocal substituted

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

                target, expected_entry, original, replacement = (
                    substitution
                )

                if ordinal != target:
                    return result

                self.assertEqual(entry, expected_entry)
                self.assertEqual(
                    encoded(result), encoded(original),
                    "selected VM return changed between executions",
                )
                self.assertIs(
                    type(result), type(replacement),
                    "substitution changes the machine return type",
                )

                substituted = True
                return replacement

            with patch.object(
                RestrictedExecutor, "run", new=observe_run
            ):
                try:
                    observation = (
                        self.adapter.reconstruct_constraint(expression)
                    )
                except (
                    ValueError, TypeError, AdmissionRejected
                ) as exc:
                    rejection = exc

        self.assertTrue(
            opened,
            "reconstruction bypassed authenticated SHEAR execution",
        )
        self.assertTrue(
            returns,
            "no admitted evaluator returned a machine result",
        )

        if substitution is not None:
            self.assertTrue(
                substituted,
                "selected machine return was not substituted",
            )

        if rejection is None:
            self.assertIsInstance(observation, tuple)
            self.assertEqual(len(observation), 2)

        return observation, tuple(returns), rejection

    def assert_rejection_provenance(self, rejected, replacement):
        self.assertEqual(
            getattr(rejected, "projection_operation", None),
            "reconstruct_constraint",
            "rejection lacks reconstruction-operation provenance",
        )
        self.assertTrue(
            hasattr(rejected, "rejected_vm_output"),
            "rejection lacks rejected-VM-output provenance",
        )
        self.assertEqual(
            encoded(rejected.rejected_vm_output),
            encoded(replacement),
            "rejection identifies the wrong VM output",
        )
        self.assertTrue(
            str(rejected).strip(),
            "reconstruction rejection lacks an explanation",
        )

    def test_reconstruction_depends_on_valid_machine_output(self):
        expressions = (
            ("is_kind", "int"),
            ("is_kind", "bool"),
            ("int_range", 0, 10),
            ("int_range", 1, 10),
            ("length", 1, 3),
            ("length", 2, 3),
        )

        observations = []
        for expression in expressions:
            result, returns, rejected = (
                self.observed_reconstruction(expression)
            )
            self.assertIsNone(rejected)
            self.assertEqual(
                encoded(result[0]), encoded(result[1]),
            )
            observations.append((expression, result, returns))

        # Select alternatives actually returned by authenticated
        # executions. Never use the assembled adapter pair as an
        # assumed RestrictedExecutor.run() result.
        candidates = []

        for expression, baseline, returns in observations:
            for control, alternative, control_returns in observations:
                if expression == control:
                    continue
                if encoded(baseline) == encoded(alternative):
                    continue

                for ordinal, (entry, original) in enumerate(returns):
                    for control_entry, replacement in control_returns:
                        if entry != control_entry:
                            continue
                        if type(original) is not type(replacement):
                            continue

                        try:
                            same_kind = (
                                kind_of(original)
                                == kind_of(replacement)
                            )
                            distinct = (
                                encoded(original)
                                != encoded(replacement)
                            )
                        except TypeError:
                            continue

                        if same_kind and distinct:
                            candidates.append((
                                expression,
                                baseline,
                                ordinal,
                                entry,
                                original,
                                replacement,
                            ))

        self.assertTrue(
            candidates,
            "no distinct compatible authenticated VM returns "
            "were observed; reconstruction dependency cannot "
            "be established",
        )

        for (
            expression, baseline, ordinal,
            entry, original, replacement,
        ) in candidates:
            substitution = (
                ordinal, entry, original, replacement
            )

            # An unchanged genuine return must reproduce the
            # original observation. This controls for the
            # interception mechanism itself.
            unchanged, _, unchanged_error = (
                self.observed_reconstruction(
                    expression,
                    (ordinal, entry, original, original),
                )
            )
            self.assertIsNone(unchanged_error)
            self.assertEqual(
                encoded(unchanged), encoded(baseline),
                "unchanged VM-output control altered reconstruction",
            )

            actual, _, rejected = self.observed_reconstruction(
                expression, substitution
            )

            if rejected is not None:
                self.assert_rejection_provenance(
                    rejected, replacement
                )
                return

            if encoded(actual) != encoded(baseline):
                return

        self.fail(
            "all compatible controlled VM-output substitutions "
            "were ignored by reconstruction"
        )


if __name__ == "__main__":
    unittest.main()
