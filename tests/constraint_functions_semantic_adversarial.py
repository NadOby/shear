"""Adversarial semantic acceptance for SHEAR issue #123.

All expected outcomes are derived from independent algebraic witnesses
or the unchanged Task 24 oracle, never from the incumbent evaluator.

Execute supplies tests.constraint_functions_complete_candidate.semantic.
This module is not automatically discovered before Execute.
"""

from importlib import import_module
from random import Random
import unittest

from tests.constraint_function_acceptance import (
    CandidateInput,
    Observation,
    ROUTES,
    acceptance_vectors,
    assess,
)
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
)

SAT = "satisfied"
VIO = "violated"
UNK = "unknown"


def nested_not(depth):
    expression = ("is_kind", "int")
    for _ in range(depth):
        expression = ("not", expression)
    return expression


def nested_role(depth):
    expression = ("is_kind", "int")
    subject = 7
    for index in reversed(range(depth)):
        role = f"role_{index}"
        expression = ("role", role, expression)
        subject = {role: subject}
    return expression, subject


def wide_conjunction(width):
    return (
        "all_of",
        *(
            ("int_range", -index, index + 1)
            for index in range(width)
        ),
    )


def wide_disjunction(width):
    return (
        "any_of",
        *(
            ("int_range", index + 1, index + 1)
            for index in range(width)
        ),
    )


def repeated_expression(kind, count):
    leaf = (
        ("is_kind", "int")
        if kind == "all_of"
        else ("is_kind", "bool")
    )
    return (kind, *(leaf for _ in range(count)))


class AdversarialSemanticAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.candidate = import_module(
                "tests.constraint_functions_complete_candidate"
            )
        cls.entries = cls.candidate.EVALUATOR_ENTRIES

        if not callable(getattr(cls.candidate, "semantic", None)):
            raise AssertionError("candidate lacks semantic adapter")

    def evaluate(self, expression, subject, budget=None, externals=()):
        case = CandidateInput(
            expression=expression,
            subject=subject,
            budget=budget,
            externals=externals,
        )

        with candidate_execution_guard(self.entries) as opened:
            observed = self.candidate.semantic(case)

        self.assertTrue(
            opened,
            "ordinary SHEAR evaluator did not execute",
        )
        self.assertIsInstance(observed, Observation)
        self.assertIn(observed.route, ROUTES)
        self.assertEqual(observed.incumbent_calls, 0)
        return observed.outcome

    def assert_outcome(
        self, expression, subject, expected,
        budget=None, externals=(),
    ):
        actual = self.evaluate(
            expression, subject, budget, externals
        )
        self.assertEqual(
            actual,
            expected,
            f"expression={expression!r}, budget={budget!r}",
        )

    def test_additional_generated_families(self):
        """1024 fresh seeds from each frozen Task 24 generator."""
        seeds = range(1000, 2024)

        with candidate_execution_guard(self.entries) as opened:
            def observed(case):
                before = len(opened)
                result = self.candidate.semantic(case)
                if len(opened) == before:
                    raise AssertionError(
                        "generated vector bypassed evaluator"
                    )
                return result

            report = assess(
                "complete-constraints-adversarial",
                observed,
                generated_seeds=seeds,
            )

        self.assertEqual(
            report.checked,
            len(acceptance_vectors(seeds)),
        )
        self.assertTrue(
            report.vector_passed,
            repr(report.failures[:10]),
        )

    def test_deep_negation_and_exact_budget(self):
        for depth in (8, 9, 64, 65, 127, 128):
            with self.subTest(depth=depth):
                expression = nested_not(depth)
                final = SAT if depth % 2 == 0 else VIO

                self.assert_outcome(expression, 7, final)
                self.assert_outcome(
                    expression, 7, final, budget=depth + 1,
                )
                self.assert_outcome(
                    expression, 7, UNK, budget=depth,
                )
                self.assert_outcome(
                    expression, 7, UNK, budget=0,
                )

    def test_deep_nested_roles_and_exact_budget(self):
        for depth in (8, 64, 128):
            with self.subTest(depth=depth):
                expression, subject = nested_role(depth)

                self.assert_outcome(expression, subject, SAT)
                self.assert_outcome(
                    expression, subject, SAT, budget=depth + 1,
                )
                self.assert_outcome(
                    expression, subject, UNK, budget=depth,
                )
                self.assert_outcome(
                    expression, subject, UNK, budget=0,
                )

    def test_wide_compositions_and_exact_budget(self):
        for width in (8, 64, 256):
            with self.subTest(width=width):
                conjunction = wide_conjunction(width)
                disjunction = wide_disjunction(width)

                self.assert_outcome(conjunction, 0, SAT)
                self.assert_outcome(disjunction, 0, VIO)

                for expression, final in (
                    (conjunction, SAT),
                    (disjunction, VIO),
                ):
                    self.assert_outcome(
                        expression, 0, final, budget=width + 1,
                    )
                    self.assert_outcome(
                        expression, 0, UNK, budget=width,
                    )
                    self.assert_outcome(
                        expression, 0, UNK, budget=0,
                    )

    def test_canonical_deduplication_under_stress(self):
        for width in (8, 64, 256):
            for operation, expected in (
                ("all_of", SAT),
                ("any_of", VIO),
            ):
                with self.subTest(width=width, operation=operation):
                    expression = repeated_expression(operation, width)
                    self.assert_outcome(
                        expression, 0, expected, budget=2,
                    )
                    self.assert_outcome(
                        expression, 0, UNK, budget=1,
                    )
                    self.assert_outcome(
                        expression, 0, expected,
                    )

    def test_permutation_invariance(self):
        satisfied = (
            ("int_range", -5, 5),
            ("int_range", -4, 4),
            ("int_range", -3, 3),
        )
        violated = (
            ("int_range", 10, 20),
            ("int_range", 30, 40),
            ("int_range", 50, 60),
        )

        for seed in range(128):
            rng = Random(seed)
            and_parts = list(satisfied + (("int_range", 100, 101),))
            or_parts = list(violated + (("int_range", -1, 1),))
            rng.shuffle(and_parts)
            rng.shuffle(or_parts)

            with self.subTest(seed=seed):
                self.assert_outcome(
                    ("all_of", *and_parts), 0, VIO,
                )
                self.assert_outcome(
                    ("any_of", *or_parts), 0, SAT,
                )

    def test_type_identity_and_structural_equality(self):
        cases = (
            (("one_of", (1,)), True, VIO),
            (("one_of", (False,)), 0, VIO),
            (("one_of", (b"a",)), "a", VIO),
            (("one_of", ((1, 2),)), [1, 2], VIO),
            (
                ("one_of", ({"a": [1, True], "b": 2},)),
                {"b": 2, "a": [1, True]},
                SAT,
            ),
            (("one_of", ("e\u0301",)), "\u00e9", VIO),
            (("is_kind", "int"), 2 ** 1024, SAT),
            (("is_kind", "int"), True, VIO),
            (("int_range", -(2 ** 1024), 2 ** 1024),
             2 ** 1024, SAT),
            (("int_range", -(2 ** 1024), 2 ** 1024),
             -(2 ** 1024) - 1, VIO),
            (("length", 1, 1), "\U0001f600", SAT),
            (("length", 2, 2), "e\u0301", SAT),
            (("length", 2, 2), "\u00e9", VIO),
            (("length", 1024, 1024), b"x" * 1024, SAT),
            (("length", 1024, 1024), "x" * 1024, SAT),
        )

        for index, (expression, subject, expected) in enumerate(cases):
            with self.subTest(case=index):
                self.assert_outcome(expression, subject, expected)

    def test_empty_compositions_with_budget(self):
        for expression, final in (
            (("all_of",), SAT),
            (("any_of",), VIO),
        ):
            with self.subTest(expression=expression):
                self.assert_outcome(expression, 0, final)
                self.assert_outcome(
                    expression, 0, UNK, budget=0,
                )
                self.assert_outcome(
                    expression, 0, final, budget=1,
                )


if __name__ == "__main__":
    unittest.main()
