"""Task 24 candidate C: bounded compilation to ordinary SHEAR functions.

This is an experiment, not a replacement for constraint evaluation.
The compiler handles canonical OneOf, Not, AllOf and AnyOf only.
Budgets and external evaluators remain explicitly unsupported.

Run with: python3 -m tests.constraint_function_c_probe
"""

from __future__ import annotations

from itertools import count
import unittest
from unittest.mock import patch

from shear import (
    AllOf,
    AnyOf,
    Constraint,
    EntityID,
    Not,
    OneOf,
    Runtime,
    State,
    Value,
    canonical_serialize,
)
from shear.lang import Function, load, run
from tests.constraint_function_acceptance import (
    CandidateInput,
    Observation,
    assess,
)
from tests.constraint_function_oracle import all_fixed_vectors


ENTRY = EntityID("task24.c.probe")
SAT = "satisfied"
VIO = "violated"
UNK = "unknown"


class UnsupportedCandidateC(ValueError):
    """A missing capability, never a semantic Unknown result."""


def materialize(expression: tuple) -> Constraint:
    """Construct semantic data without interpreting its truth value."""
    if not isinstance(expression, tuple) or not expression:
        raise UnsupportedCandidateC("malformed constraint expression")

    operation, *operands = expression

    if operation == "one_of" and len(operands) == 1:
        return OneOf(*operands[0])
    if operation == "not" and len(operands) == 1:
        return Not(materialize(operands[0]))
    if operation == "all_of":
        return AllOf(*(materialize(item) for item in operands))
    if operation == "any_of":
        return AnyOf(*(materialize(item) for item in operands))

    raise UnsupportedCandidateC(f"no code generator for {operation!r}")


class Compiler:
    """Translate a constrained subset into ordinary graph-form input code."""

    def __init__(self) -> None:
        self.names = count()

    def fresh(self) -> str:
        return f"c_{next(self.names)}"

    @staticmethod
    def lit(value: object) -> tuple:
        return ("lit", value)

    @staticmethod
    def arg(name: str) -> tuple:
        return ("arg", name)

    def compile(self, constraint: Constraint) -> tuple:
        if isinstance(constraint, OneOf):
            body = self.lit(VIO)
            for value in reversed(constraint.values):
                body = (
                    "if",
                    ("eq", self.arg("subject"), self.lit(value)),
                    self.lit(SAT),
                    body,
                )
            return body

        if isinstance(constraint, Not):
            name = self.fresh()
            result = self.arg(name)
            return (
                "let", name, self.compile(constraint.part),
                (
                    "if", ("eq", result, self.lit(SAT)),
                    self.lit(VIO),
                    (
                        "if", ("eq", result, self.lit(VIO)),
                        self.lit(SAT), self.lit(UNK),
                    ),
                ),
            )

        if isinstance(constraint, AllOf):
            return self._fold(constraint.parts, conjunctive=True)

        if isinstance(constraint, AnyOf):
            return self._fold(constraint.parts, conjunctive=False)

        raise UnsupportedCandidateC(
            f"no code generator for {type(constraint).__name__}"
        )

    def _fold(self, parts: tuple, *, conjunctive: bool) -> tuple:
        default = SAT if conjunctive else VIO
        decisive = VIO if conjunctive else SAT
        neutral = SAT if conjunctive else VIO

        if not parts:
            return self.lit(default)

        if len(parts) == 1:
            return self.compile(parts[0])

        current = self.fresh()
        remaining = self.fresh()
        first = self.arg(current)
        rest = self.arg(remaining)

        return (
            "let", current, self.compile(parts[0]),
            (
                "if", ("eq", first, self.lit(decisive)),
                self.lit(decisive),
                (
                    "let", remaining,
                    self._fold(parts[1:], conjunctive=conjunctive),
                    (
                        "if", ("eq", first, self.lit(neutral)),
                        rest,
                        (
                            "if", ("eq", rest, self.lit(decisive)),
                            self.lit(decisive), self.lit(UNK),
                        ),
                    ),
                ),
            ),
        )


def compile_runtime(expression: tuple) -> Runtime:
    """Compile semantic data and load actual SHEAR executable code."""
    constraint = materialize(expression)
    body = Compiler().compile(constraint)
    state = State.create({
        ENTRY: Value.create(
            ENTRY, Function(("subject",), body),
        ),
    })
    return Runtime(load(state))


def candidate_c(case: CandidateInput) -> Observation:
    """Candidate-facing adapter; receives no expected outcomes or seeds."""
    if case.budget is not None:
        raise UnsupportedCandidateC("constraint-node budgets unsupported")
    if case.externals:
        raise UnsupportedCandidateC("external authority unsupported")

    runtime = compile_runtime(case.expression)
    outcome = run(runtime, ENTRY, case.subject)
    if outcome not in (SAT, VIO, UNK):
        raise AssertionError("compiled function returned invalid result")
    if runtime.active.holds:
        raise AssertionError("compiled function retained a version hold")

    # These are adapter claims; independent route auditing is still needed.
    return Observation(outcome, "compiled", 0)


class CandidateCProbeTests(unittest.TestCase):
    def test_one_of_uses_real_vm_without_incumbent_evaluation(self) -> None:
        with patch.object(
            Constraint, "_evaluate",
            side_effect=AssertionError("incumbent fallback"),
        ):
            cases = (
                (("one_of", (1,)), 1, SAT),
                (("one_of", (1,)), True, VIO),
                (("one_of", (1,)), 2, VIO),
                (("one_of", ()), 0, VIO),
                (("one_of", ({"a": 1, "b": 2},)),
                 {"b": 2, "a": 1}, SAT),
            )
            for expression, subject, expected in cases:
                with self.subTest(expression=expression, subject=subject):
                    result = candidate_c(CandidateInput(
                        expression, subject, None, (),
                    ))
                    self.assertEqual(result.outcome, expected)
                    self.assertEqual(result.route, "compiled")
                    self.assertEqual(result.incumbent_calls, 0)

    def test_composition_executes_in_ordinary_functions(self) -> None:
        cases = (
            (("all_of",), 0, SAT),
            (("any_of",), 0, VIO),
            (("not", ("one_of", (7,))), 7, VIO),
            (("not", ("one_of", (7,))), 8, SAT),
            (("all_of", ("one_of", (7,)),
              ("one_of", (7, 8))), 7, SAT),
            (("all_of", ("one_of", (7,)),
              ("one_of", (8,))), 7, VIO),
            (("any_of", ("one_of", (8,)),
              ("one_of", (7,))), 7, SAT),
        )
        with patch.object(
            Constraint, "_evaluate",
            side_effect=AssertionError("incumbent fallback"),
        ):
            for expression, subject, expected in cases:
                with self.subTest(expression=expression):
                    self.assertEqual(
                        candidate_c(CandidateInput(
                            expression, subject, None, (),
                        )).outcome,
                        expected,
                    )

    def test_canonical_constraint_identity_is_preserved(self) -> None:
        first = ("all_of", ("one_of", (7, 8)), ("one_of", (7,)))
        second = ("all_of", ("one_of", (7,)), ("one_of", (8, 7)))
        self.assertEqual(
            canonical_serialize(materialize(first)),
            canonical_serialize(materialize(second)),
        )
        self.assertEqual(
            compile_runtime(first).active.state.id,
            compile_runtime(second).active.state.id,
        )

    def test_budget_external_and_missing_primitives_fail_closed(self) -> None:
        cases = (
            CandidateInput(("one_of", (1,)), 1, 1, ()),
            CandidateInput(("external", "missing"), 1, None, ()),
            CandidateInput(("one_of", (1,)), 1, None,
                           (("policy", SAT),)),
            CandidateInput(("is_kind", "int"), 1, None, ()),
            CandidateInput(("role", "item", ("one_of", (7,))),
                           {"item": 7}, None, ()),
        )
        for case in cases:
            with self.subTest(expression=case.expression):
                with self.assertRaises(UnsupportedCandidateC):
                    candidate_c(case)

    def test_frozen_semantic_matrix_does_not_qualify(self) -> None:
        """Assess all fixed cases plus two generated families, without edits."""
        report = assess("C-bounded", candidate_c, generated_seeds=(0, 1))
        self.assertEqual(report.checked, len(all_fixed_vectors()) + 4)
        self.assertFalse(report.vector_passed)
        self.assertTrue(report.failures)
        self.assertTrue(any(
            item.name.startswith("kind_") for item in report.failures
        ))
        self.assertTrue(any(
            item.name.startswith("external_") for item in report.failures
        ))


if __name__ == "__main__":
    unittest.main()
