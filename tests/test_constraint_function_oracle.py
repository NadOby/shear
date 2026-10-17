"""Validate Task 24's independent oracle against fixed semantic facts.

Expected results originate in constraint_function_oracle, never from
the production evaluator being tested. The control adapter constructs
subjects and constraints but does not calculate expected results.
"""

from __future__ import annotations

from itertools import product
import unittest

from shear import (
    CellDeclaration,
    EntityID,
    Relation,
    StateID,
    VersionID,
)
from shear.closures import Closure
from shear.constraints import (
    AllOf,
    AnyOf,
    Constraint,
    ConstraintResult,
    EvaluationContext,
    Evaluator,
    External,
    IntRange,
    IsKind,
    KINDS,
    Length,
    Not,
    OneOf,
    Role,
    kind_of,
)
from tests.constraint_function_oracle import (
    BOUNDARIES,
    BUDGETS,
    CONSTANTS,
    KIND_SAMPLES,
    KIND_VECTORS,
    LOGICAL,
    PRIMITIVES,
    RESULTS,
    SAT,
    UNK,
    VIO,
    KindSample,
    all_fixed_vectors,
    conjunction,
    disjunction,
    generated_budget_vector,
    generated_vector,
    negate,
    shrink_tree,
    truth_of,
)
from tests.generation import seeds


def materialize(subject):
    """Turn a symbolic kind descriptor into a semantic record.

    This is a control adapter, not part of the independent oracle.
    Candidate adapters must implement their own appropriate conversion.
    """
    if not isinstance(subject, KindSample):
        return subject

    samples = {
        "entity_id": lambda: EntityID("kind.sample"),
        "version_id": lambda: VersionID("kind.sample"),
        "state_id": lambda: StateID("kind.sample"),
        "cell": lambda: CellDeclaration(IsKind("int"), 0),
        "constraint": lambda: IntRange(0, 1),
        "relation": lambda: Relation(
            "sample", {"subject": EntityID("kind.sample")}
        ),
        "closure": lambda: Closure(
            EntityID("owner"), EntityID("body"), (), ()
        ),
    }

    if subject.kind not in samples:
        raise ValueError(f"unknown symbolic kind: {subject.kind}")

    return samples[subject.kind]()


def build(expression: tuple) -> Constraint:
    """Translate descriptive expression input into public constraint API."""
    name, *args = expression

    if name == "is_kind":
        return IsKind(args[0])
    if name == "int_range":
        return IntRange(*args)
    if name == "length":
        return Length(*args)
    if name == "one_of":
        return OneOf(*args[0])
    if name == "role":
        return Role(args[0], build(args[1]))
    if name == "external":
        return External(args[0])
    if name == "not":
        return Not(build(args[0]))
    if name == "all_of":
        return AllOf(*(build(part) for part in args))
    if name == "any_of":
        return AnyOf(*(build(part) for part in args))

    raise ValueError(f"unknown fixture operation: {name}")


def evaluate_control(vector) -> str:
    """Reference-model observation, never used as an expected result."""
    externals = {
        name: Evaluator(
            lambda _subject, value=result: ConstraintResult[
                value.upper()
            ]
        )
        for name, result in vector.externals
    }
    return build(vector.expression).evaluate(
        materialize(vector.subject),
        EvaluationContext(externals, vector.budget),
    ).value


class OracleMathematicsTests(unittest.TestCase):
    def test_independent_truth_tables(self) -> None:
        and_table = (
            (SAT, SAT, SAT),
            (SAT, VIO, VIO),
            (SAT, UNK, UNK),
            (VIO, SAT, VIO),
            (VIO, VIO, VIO),
            (VIO, UNK, VIO),
            (UNK, SAT, UNK),
            (UNK, VIO, VIO),
            (UNK, UNK, UNK),
        )
        or_table = (
            (SAT, SAT, SAT),
            (SAT, VIO, SAT),
            (SAT, UNK, SAT),
            (VIO, SAT, SAT),
            (VIO, VIO, VIO),
            (VIO, UNK, UNK),
            (UNK, SAT, SAT),
            (UNK, VIO, UNK),
            (UNK, UNK, UNK),
        )

        for left, right, expected in and_table:
            with self.subTest(op="and", left=left, right=right):
                self.assertEqual(
                    conjunction(left, right), expected
                )

        for left, right, expected in or_table:
            with self.subTest(op="or", left=left, right=right):
                self.assertEqual(
                    disjunction(left, right), expected
                )

        self.assertEqual(negate(SAT), VIO)
        self.assertEqual(negate(VIO), SAT)
        self.assertEqual(negate(UNK), UNK)
        self.assertEqual(conjunction(), SAT)
        self.assertEqual(disjunction(), VIO)

    def test_all_three_results_are_distinct(self) -> None:
        self.assertEqual(len(set(RESULTS)), 3)

        for value in RESULTS:
            self.assertEqual(
                negate(negate(value)), value
            )

    def test_de_morgan_for_every_result_pair(self) -> None:
        for left, right in product(RESULTS, repeat=2):
            with self.subTest(left=left, right=right):
                self.assertEqual(
                    negate(conjunction(left, right)),
                    disjunction(negate(left), negate(right)),
                )
                self.assertEqual(
                    negate(disjunction(left, right)),
                    conjunction(negate(left), negate(right)),
                )

    def test_unknown_is_not_ordinary_false(self) -> None:
        self.assertEqual(conjunction(UNK, VIO), VIO)
        self.assertEqual(disjunction(UNK, SAT), SAT)
        self.assertEqual(conjunction(UNK, SAT), UNK)
        self.assertEqual(disjunction(UNK, VIO), UNK)


class FrozenVectorTests(unittest.TestCase):
    def test_vectors_have_unique_names(self) -> None:
        vectors = all_fixed_vectors()
        names = [vector.name for vector in vectors]

        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(CONSTANTS), 3)
        self.assertEqual(len(KIND_SAMPLES), 15)
        self.assertGreater(len(PRIMITIVES), 25)
        self.assertGreaterEqual(len(LOGICAL), 30)
        self.assertGreater(len(BUDGETS), 20)
        self.assertEqual(
            len(vectors),
            len(KIND_VECTORS)
            + len(PRIMITIVES)
            + len(LOGICAL)
            + len(BUDGETS),
        )

    def test_all_canonical_kinds_are_frozen(self) -> None:
        expected_kinds = {
            kind for kind, _subject in KIND_SAMPLES
        }
        self.assertEqual(expected_kinds, set(KINDS))
        self.assertEqual(
            {vector.expression[1] for vector in KIND_VECTORS},
            expected_kinds,
        )

        for kind, subject in KIND_SAMPLES:
            with self.subTest(kind=kind):
                self.assertEqual(kind_of(materialize(subject)), kind)

    def test_kind_fixtures_match_control(self) -> None:
        for vector in KIND_VECTORS:
            with self.subTest(vector=vector.name):
                self.assertEqual(
                    evaluate_control(vector), vector.expected
                )

    def test_primitive_fixtures_match_control(self) -> None:
        for vector in PRIMITIVES:
            with self.subTest(vector=vector.name):
                self.assertEqual(
                    evaluate_control(vector), vector.expected
                )

    def test_complete_operator_matrix_matches_control(self) -> None:
        for vector in LOGICAL:
            with self.subTest(vector=vector.name):
                self.assertEqual(
                    evaluate_control(vector), vector.expected
                )

    def test_budget_fixtures_match_control(self) -> None:
        for vector in BUDGETS:
            with self.subTest(vector=vector.name):
                self.assertEqual(
                    evaluate_control(vector), vector.expected
                )

    def test_budget_can_preserve_a_decisive_short_circuit(
        self,
    ) -> None:
        context = EvaluationContext(
            {
                "a_vio": Evaluator(
                    lambda _: ConstraintResult.VIOLATED
                ),
                "z_sat": Evaluator(
                    lambda _: ConstraintResult.SATISFIED
                ),
            },
            budget=2,
        )
        result = AllOf(
            External("a_vio"),
            External("z_sat"),
        ).evaluate(0, context)

        self.assertEqual(result, ConstraintResult.VIOLATED)

        context = EvaluationContext(
            {
                "a_sat": Evaluator(
                    lambda _: ConstraintResult.SATISFIED
                ),
                "z_vio": Evaluator(
                    lambda _: ConstraintResult.VIOLATED
                ),
            },
            budget=2,
        )
        result = AnyOf(
            External("a_sat"),
            External("z_vio"),
        ).evaluate(0, context)

        self.assertEqual(result, ConstraintResult.SATISFIED)

    def test_missing_external_is_not_false(self) -> None:
        self.assertEqual(
            External("missing").evaluate(0),
            ConstraintResult.UNKNOWN,
        )

    def test_external_exception_is_not_unknown(self) -> None:
        class HostFailure(Exception):
            pass

        def fail(_subject):
            raise HostFailure("sentinel")

        context = EvaluationContext({
            "broken": Evaluator(fail),
        })

        with self.assertRaisesRegex(
            HostFailure, "sentinel"
        ):
            External("broken").evaluate(0, context)

    def test_boundary_witnesses_are_uniquely_named(self) -> None:
        names = [witness.name for witness in BOUNDARIES]
        self.assertEqual(len(names), len(set(names)))


class GeneratedOracleTests(unittest.TestCase):
    def test_generated_trees_match_independent_expectations(
        self,
    ) -> None:
        for seed in seeds(100):
            with self.subTest(seed=seed):
                vector = generated_vector(seed)
                self.assertEqual(
                    evaluate_control(vector),
                    vector.expected,
                )

    def test_generated_budget_cases_match_control(self) -> None:
        for seed in seeds(100):
            with self.subTest(seed=seed):
                vector = generated_budget_vector(seed)
                self.assertEqual(
                    evaluate_control(vector),
                    vector.expected,
                )

    def test_generated_expected_result_is_reproducible(
        self,
    ) -> None:
        for seed in seeds(100):
            with self.subTest(seed=seed):
                first = generated_vector(seed)
                second = generated_vector(seed)
                self.assertEqual(first, second)
                self.assertEqual(
                    truth_of(first.expression),
                    first.expected,
                )

                budget_first = generated_budget_vector(seed)
                budget_second = generated_budget_vector(seed)
                self.assertEqual(budget_first, budget_second)

    def test_generated_budget_cases_use_primitive_combinations(
        self,
    ) -> None:
        cases = tuple(
            generated_budget_vector(seed)
            for seed in range(200)
        )

        self.assertTrue(all(case.budget is not None for case in cases))
        self.assertTrue(any(case.expected == SAT for case in cases))
        self.assertTrue(any(case.expected == VIO for case in cases))
        self.assertTrue(any(case.expected == UNK for case in cases))
        self.assertTrue(
            any(case.expression[0] == "all_of" for case in cases)
        )
        self.assertTrue(
            any(case.expression[0] == "any_of" for case in cases)
        )
        self.assertTrue(
            any(case.expression[0] == "not" for case in cases)
        )

    def test_shrinker_finds_a_smaller_counterexample(
        self,
    ) -> None:
        target = ("external", "unk")
        expression = (
            "all_of",
            ("external", "sat"),
            ("not", target),
        )

        def contains_unknown(tree: tuple) -> bool:
            if tree == target:
                return True
            return any(
                contains_unknown(part)
                for part in tree[1:]
                if isinstance(part, tuple)
            )

        reduced = shrink_tree(expression, contains_unknown)
        self.assertEqual(reduced, target)

    def test_shrinker_rejects_a_nonfailure(self) -> None:
        with self.assertRaises(ValueError):
            shrink_tree(
                ("external", "sat"),
                lambda _: False,
            )


if __name__ == "__main__":
    unittest.main()
