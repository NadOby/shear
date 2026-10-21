"""T5 semantic constraint identity acceptance for SHEAR #123.

Execute supplies:
    reconstruct_constraint(expression)
        -> (original_canonical, reconstructed_canonical)

Both outputs must originate from admitted SHEAR computation and
retain canonical semantic identity.

Every supported constraint form requires independent evidence
of dependency on actual authenticated VM results.

No fixed invocation count or machine-return shape is assumed.
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

# Two valid, canonically distinct expressions for each of the
# nine normative constraint forms.
#
# Same-form controls are preferred over arbitrary cross-form
# substitutions to avoid conflating different semantic contracts.

CAUSAL_FORMS = {
    "is_kind": (
        ("is_kind", "int"),
        ("is_kind", "bool"),
    ),
    "int_range": (
        ("int_range", 0, 10),
        ("int_range", 1, 10),
    ),
    "length": (
        ("length", 1, 3),
        ("length", 2, 3),
    ),
    "one_of": (
        ("one_of", (True, 1, "x")),
        ("one_of", (False, 2, "y")),
    ),
    "all_of": (
        ("all_of", ("is_kind", "int"),
         ("int_range", 0, 10)),
        ("all_of", ("is_kind", "str"),
         ("length", 0, 5)),
    ),
    "any_of": (
        ("any_of", ("is_kind", "int"),
         ("is_kind", "str")),
        ("any_of", ("is_kind", "bool"),
         ("is_kind", "str")),
    ),
    "not": (
        ("not", ("is_kind", "int")),
        ("not", ("is_kind", "bool")),
    ),
    "role": (
        ("role", "item", ("is_kind", "int")),
        ("role", "item", ("is_kind", "str")),
    ),
    "external": (
        ("external", "policy"),
        ("external", "alternative"),
    ),
}


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

        Substitution:
            (ordinal, entry, original_vm_output, replacement)

        Ordinals count admitted evaluator returns only.
        The genuine machine invocation always executes first.
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
                    "substitution changes machine return type",
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
                "selected machine result was not substituted",
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
            "rejection identifies the wrong substituted VM output",
        )
        self.assertTrue(
            str(rejected).strip(),
            "reconstruction rejection lacks an explanation",
        )

    def compatible_substitutions(self, baseline_returns, control_returns):
        """Yield same-entry, same-kind, distinct valid VM returns."""
        for ordinal, (entry, original) in enumerate(baseline_returns):
            for control_entry, replacement in control_returns:
                if entry != control_entry:
                    continue
                if type(original) is not type(replacement):
                    continue

                try:
                    compatible = (
                        kind_of(original) == kind_of(replacement)
                    )
                    distinct = encoded(original) != encoded(replacement)
                except (TypeError, ValueError):
                    continue

                if compatible and distinct:
                    yield (
                        ordinal, entry, original, replacement
                    )

    def test_reconstruction_depends_on_valid_machine_output(self):
        """Establish per-form VM execution dependency.

        Actual machine results may have distinct evaluator entries,
        schemas or invocation counts. No arbitrary machine-result
        substitution is assumed to satisfy a hidden return contract.

        Each form must:
        - yield two distinct correct reconstructed constraints;
        - expose distinct authenticated machine observations;
        - propagate a test-owned VM-return fault without host fallback.

        These are necessary execution-dependency discriminators.
        The mandatory source-path audit must additionally establish
        that the admitted computation performs reconstruction.
        """
        forms = frozenset({
            "is_kind", "int_range", "length", "one_of",
            "all_of", "any_of", "not", "role", "external",
        })
        self.assertEqual(set(CAUSAL_FORMS), forms)

        class InjectedVMReturnFault(RuntimeError):
            pass

        established = set()

        for form, expressions in CAUSAL_FORMS.items():
            with self.subTest(form=form):
                self.assertEqual(len(expressions), 2)
                self.assertTrue(
                    all(
                        expression[0] == form
                        for expression in expressions
                    )
                )

                observations = []

                for expression in expressions:
                    result, returns, rejected = (
                        self.observed_reconstruction(expression)
                    )
                    self.assertIsNone(rejected)

                    original, rebuilt = result
                    self.assertEqual(kind_of(original), "constraint")
                    self.assertEqual(kind_of(rebuilt), "constraint")
                    self.assertEqual(
                        encoded(original), encoded(rebuilt),
                    )

                    observations.append(
                        (expression, result, returns)
                    )

                self.assertNotEqual(
                    encoded(observations[0][1]),
                    encoded(observations[1][1]),
                    "control expressions are not semantically distinct",
                )

                # Require actual machine results to differ between
                # the two controls. Do not require the same entry
                # to produce both results.
                first_returns = {
                    encoded(value)
                    for _, value in observations[0][2]
                }
                second_returns = {
                    encoded(value)
                    for _, value in observations[1][2]
                }

                self.assertNotEqual(
                    first_returns, second_returns,
                    "distinct reconstruction expressions produced "
                    "indistinguishable machine-return observations",
                )

                # Suppress the first admitted machine return with a
                # unique exception after genuine restricted execution.
                # Returning a host-generated reconstruction despite
                # this fault is prohibited.
                for expression in expressions:
                    sentinel = InjectedVMReturnFault(
                        f"controlled VM return fault: {form}"
                    )
                    intercepted = []

                    with candidate_execution_guard(
                        self.entries
                    ) as opened:
                        guarded_run = RestrictedExecutor.run

                        def fault_run(
                            executor, deployment, entry,
                            *args, **kwargs
                        ):
                            result = guarded_run(
                                executor, deployment, entry,
                                *args, **kwargs
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
                                self.adapter.reconstruct_constraint(
                                    expression
                                )
                            except BaseException as exc:
                                caught = exc

                    self.assertTrue(
                        opened,
                        f"{form}: no authenticated evaluator entry",
                    )
                    self.assertTrue(
                        intercepted,
                        f"{form}: no authenticated machine result "
                        "was intercepted",
                    )
                    self.assertIs(
                        caught, sentinel,
                        f"{form}: VM-return fault was swallowed, "
                        "translated or bypassed",
                    )

                established.add(form)

        self.assertEqual(established, forms)


if __name__ == "__main__":
    unittest.main()
