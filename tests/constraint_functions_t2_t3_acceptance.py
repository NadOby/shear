"""Frozen T2/T3 acceptance for SHEAR issue #123.

Execute supplies:
    prepare_semantic(expression, budget, externals)
    semantic(CandidateInput)
    trace_budget(CandidateInput) -> (verdict, visited_nodes)

trace_budget must obtain both results from admitted SHEAR computation.
Python-side simulation or incumbent accounting does not qualify.

This module remains outside ordinary CI discovery until Execute.
"""

from dataclasses import dataclass
from importlib import import_module
import unittest

from tests.constraint_function_acceptance import (
    CandidateInput,
    Observation,
)
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
)


SAT = "satisfied"
VIO = "violated"
UNK = "unknown"


@dataclass(frozen=True)
class BudgetWitness:
    expression: tuple
    subject: object
    budget: int | None
    externals: tuple
    outcome: str
    visited: int


# Visited counts are semantic constraint nodes, not VM instructions.
# For exhausted budgets, failed attempts to visit nodes do not count.
# Composite examples avoid order-dependent early termination.
BUDGET_WITNESSES = (
    BudgetWitness(("is_kind", "int"), 5, 0, (), UNK, 0),
    BudgetWitness(("is_kind", "int"), 5, 1, (), SAT, 1),
    BudgetWitness(("is_kind", "int"), True, 1, (), VIO, 1),
    BudgetWitness(("is_kind", "int"), 5, None, (), SAT, 1),
    BudgetWitness(
        ("not", ("is_kind", "int")), 5, 0, (), UNK, 0,
    ),
    BudgetWitness(
        ("not", ("is_kind", "int")), 5, 1, (), UNK, 1,
    ),
    BudgetWitness(
        ("not", ("is_kind", "int")), 5, 2, (), VIO, 2,
    ),
    BudgetWitness(
        ("not", ("is_kind", "int")), 5, None, (), VIO, 2,
    ),
    BudgetWitness(
        ("all_of", ("is_kind", "int"), ("int_range", 0, 10)),
        5, 0, (), UNK, 0,
    ),
    BudgetWitness(
        ("all_of", ("is_kind", "int"), ("int_range", 0, 10)),
        5, 1, (), UNK, 1,
    ),
    BudgetWitness(
        ("all_of", ("is_kind", "int"), ("int_range", 0, 10)),
        5, 2, (), UNK, 2,
    ),
    BudgetWitness(
        ("all_of", ("is_kind", "int"), ("int_range", 0, 10)),
        5, 3, (), SAT, 3,
    ),
    BudgetWitness(
        ("all_of", ("is_kind", "int"), ("int_range", 0, 10)),
        5, None, (), SAT, 3,
    ),
    BudgetWitness(
        ("any_of", ("is_kind", "bool"), ("int_range", 10, 20)),
        5, 2, (), UNK, 2,
    ),
    BudgetWitness(
        ("any_of", ("is_kind", "bool"), ("int_range", 10, 20)),
        5, 3, (), VIO, 3,
    ),
    BudgetWitness(
        ("role", "x", ("int_range", 0, 10)),
        {"x": 5}, 1, (), UNK, 1,
    ),
    BudgetWitness(
        ("role", "x", ("int_range", 0, 10)),
        {"x": 5}, 2, (), SAT, 2,
    ),
    BudgetWitness(
        ("all_of", ("is_kind", "int"), ("is_kind", "int")),
        5, 1, (), UNK, 1,
    ),
    BudgetWitness(
        ("all_of", ("is_kind", "int"), ("is_kind", "int")),
        5, 2, (), SAT, 2,
    ),
    BudgetWitness(
        ("external", "missing"), 7, 1, (), UNK, 1,
    ),
    BudgetWitness(
        ("external", "policy"), 7, 0,
        (("policy", SAT),), UNK, 0,
    ),
    BudgetWitness(
        ("external", "policy"), 7, 1,
        (("policy", SAT),), SAT, 1,
    ),
)


# Error classes are normative existing constructor/budget classes.
# Errors must occur in preparation, before candidate VM execution.
MALFORMED = (
    (("is_kind", "float"), None, ValueError),
    (("int_range", 10, 0), None, ValueError),
    (("int_range", 0, True), None, TypeError),
    (("int_range", False, 10), None, TypeError),
    (("length", -1, 2), None, ValueError),
    (("length", 3, 2), None, ValueError),
    (("role", "", ("is_kind", "int")), None, TypeError),
    (("external", ""), None, TypeError),
    (("not", 4), None, TypeError),
    (("all_of", 4), None, TypeError),
    (("is_kind", "int"), -1, ValueError),
    (("is_kind", "int"), True, ValueError),
    (("is_kind", "int"), "2", ValueError),
)


class FrozenPrimitiveBudgetAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.adapter = import_module(
                "tests.constraint_functions_complete_candidate"
            )
        cls.entries = cls.adapter.EVALUATOR_ENTRIES

        for operation in (
            "prepare_semantic", "semantic", "trace_budget",
        ):
            if not callable(getattr(cls.adapter, operation, None)):
                raise AssertionError(
                    f"candidate lacks {operation}"
                )

    def test_malformed_constraint_inputs(self):
        self.assertEqual(len(MALFORMED), 13)

        for expression, budget, exception in MALFORMED:
            with self.subTest(expression=expression, budget=budget):
                with forbid_incumbent():
                    with self.assertRaises(exception):
                        self.adapter.prepare_semantic(
                            expression, budget, (),
                        )

    def test_budget_consumption_trace(self):
        self.assertGreaterEqual(len(BUDGET_WITNESSES), 20)

        for witness in BUDGET_WITNESSES:
            with self.subTest(
                expression=witness.expression,
                budget=witness.budget,
            ):
                case = CandidateInput(
                    witness.expression, witness.subject,
                    witness.budget, witness.externals,
                )

                with candidate_execution_guard(
                    self.entries,
                ) as opened:
                    actual = self.adapter.trace_budget(case)

                self.assertTrue(
                    opened, "budget trace bypassed admitted SHEAR",
                )
                self.assertIsInstance(actual, tuple)
                self.assertEqual(len(actual), 2)
                outcome, visited = actual

                self.assertEqual(outcome, witness.outcome)
                self.assertIs(type(visited), int)
                self.assertEqual(visited, witness.visited)

                with candidate_execution_guard(
                    self.entries,
                ) as opened:
                    observed = self.adapter.semantic(case)

                self.assertTrue(
                    opened, "semantic result bypassed admitted SHEAR",
                )
                self.assertIsInstance(observed, Observation)
                self.assertEqual(
                    observed.outcome, witness.outcome,
                )
                self.assertEqual(observed.incumbent_calls, 0)


if __name__ == "__main__":
    unittest.main()
