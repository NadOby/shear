"""Independent semantic oracle and frozen Task 24 experiment vectors.

No imports from shear. These expected outcomes must not be derived
from production Constraint.evaluate, machine execution, or candidate code.

This is Plan-owned evidence, not an alternative production evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from random import Random
from typing import Any, Callable


SAT = "satisfied"
VIO = "violated"
UNK = "unknown"
RESULTS = (SAT, VIO, UNK)

_POSSIBLE = {
    SAT: frozenset((True,)),
    VIO: frozenset((False,)),
    UNK: frozenset((True, False)),
}
_BY_POSSIBLE = {value: key for key, value in _POSSIBLE.items()}

# Deliberately independent of ConstraintResult and its ordering.
CONSTANTS = (
    ("sat", SAT),
    ("vio", VIO),
    ("unk", UNK),
)


def negate(result: str) -> str:
    outcomes = frozenset(not value for value in _POSSIBLE[result])
    return _BY_POSSIBLE[outcomes]


def conjunction(*results: str) -> str:
    outcomes = frozenset(
        all(assignment)
        for assignment in product(
            *(_POSSIBLE[result] for result in results)
        )
    )
    return _BY_POSSIBLE[outcomes]


def disjunction(*results: str) -> str:
    outcomes = frozenset(
        any(assignment)
        for assignment in product(
            *(_POSSIBLE[result] for result in results)
        )
    )
    return _BY_POSSIBLE[outcomes]


@dataclass(frozen=True)
class Vector:
    """Expression is descriptive input, not production canonical content."""

    name: str
    expression: tuple[Any, ...]
    subject: Any
    expected: str
    budget: int | None = None
    externals: tuple[tuple[str, str], ...] = ()


# Primitive expectations are fixed directly, not calculated by a
# duplicate of the production primitive implementations.
PRIMITIVES = (
    Vector("int_kind", ("is_kind", "int"), 3, SAT),
    Vector("bool_not_int", ("is_kind", "int"), True, VIO),
    Vector("boolean_kind", ("is_kind", "bool"), False, SAT),
    Vector("none_kind", ("is_kind", "none"), None, SAT),
    Vector("bytes_kind", ("is_kind", "bytes"), b"x", SAT),
    Vector("map_kind", ("is_kind", "map"), {"x": 1}, SAT),
    Vector("list_kind", ("is_kind", "list"), [1], SAT),
    Vector("tuple_kind", ("is_kind", "tuple"), (1,), SAT),
    Vector("range_lower", ("int_range", 0, 10), 0, SAT),
    Vector("range_upper", ("int_range", 0, 10), 10, SAT),
    Vector("range_outside", ("int_range", 0, 10), 11, VIO),
    Vector("range_wrong_kind", ("int_range", 0, 10), "5", VIO),
    Vector("range_bool", ("int_range", 0, 10), True, VIO),
    Vector("range_unbounded", ("int_range", None, None), -20, SAT),
    Vector("length_tuple", ("length", 2, 2), (1, 2), SAT),
    Vector("length_list", ("length", 2, 2), [1], VIO),
    Vector("length_map", ("length", 1, 1), {"x": 1}, SAT),
    Vector("length_bytes", ("length", 2, 2), b"ab", SAT),
    Vector("length_codepoints", ("length", 2, 2), "e\u0301", SAT),
    Vector("length_unsupported", ("length", 0, None), 42, VIO),
    Vector("one_of_present", ("one_of", (1, "a")), "a", SAT),
    Vector("one_of_absent", ("one_of", (1, "a")), 2, VIO),
    Vector("one_of_bool_distinct", ("one_of", (1,)), True, VIO),
    Vector("one_of_empty", ("one_of", ()), 0, VIO),
    Vector(
        "one_of_map_order",
        ("one_of", ({"a": 1, "b": 2},)),
        {"b": 2, "a": 1},
        SAT,
    ),
    Vector("role_present", ("role", "x", ("int_range", 0, 5)),
           {"x": 3}, SAT),
    Vector("role_violated", ("role", "x", ("int_range", 0, 5)),
           {"x": 8}, VIO),
    Vector("role_missing", ("role", "x", ("is_kind", "int")),
           {"y": 3}, VIO),
    Vector("role_not_map", ("role", "x", ("is_kind", "int")),
           (3,), VIO),
    Vector("external_absent", ("external", "missing"), 1, UNK),
    Vector(
        "external_satisfied",
        ("external", "sat"),
        1,
        SAT,
        externals=CONSTANTS,
    ),
    Vector(
        "external_unknown",
        ("external", "unk"),
        1,
        UNK,
        externals=CONSTANTS,
    ),
)


# Node budgets count the root as well as evaluated children.
# Composite operands are canonically deduplicated. These cases
# avoid dependence on the order of two unequal decisive children.
_PAIR = ("all_of", ("is_kind", "int"), ("int_range", 0, 10))
_DOUBLE_NOT = ("not", ("not", ("is_kind", "int")))

BUDGETS = (
    Vector("leaf_zero", ("is_kind", "int"), 5, UNK, 0),
    Vector("leaf_one", ("is_kind", "int"), 5, SAT, 1),
    Vector("pair_zero", _PAIR, 5, UNK, 0),
    Vector("pair_one", _PAIR, 5, UNK, 1),
    Vector("pair_two", _PAIR, 5, UNK, 2),
    Vector("pair_three", _PAIR, 5, SAT, 3),
    Vector("pair_unbounded", _PAIR, 5, SAT),
    Vector("not_zero", ("not", ("is_kind", "int")), 5, UNK, 0),
    Vector("not_one", ("not", ("is_kind", "int")), 5, UNK, 1),
    Vector("not_two", ("not", ("is_kind", "int")), 5, VIO, 2),
    Vector("double_not_two", _DOUBLE_NOT, 5, UNK, 2),
    Vector("double_not_three", _DOUBLE_NOT, 5, SAT, 3),
    Vector("empty_and_zero", ("all_of",), 0, UNK, 0),
    Vector("empty_and_one", ("all_of",), 0, SAT, 1),
    Vector("empty_or_zero", ("any_of",), 0, UNK, 0),
    Vector("empty_or_one", ("any_of",), 0, VIO, 1),
    Vector(
        "deduplicated_and",
        ("all_of", ("is_kind", "int"), ("is_kind", "int")),
        5, SAT, 2,
    ),
    Vector(
        "external_no_budget",
        ("external", "sat"),
        5, UNK, 0, CONSTANTS,
    ),
    Vector(
        "external_one_step",
        ("external", "sat"),
        5, SAT, 1, CONSTANTS,
    ),
    Vector(
        "external_missing_with_budget",
        ("external", "missing"),
        5, UNK, 1, CONSTANTS,
    ),
)


def truth_of(expression: tuple[Any, ...]) -> str:
    """Mathematical oracle for generated, unbudgeted logical trees.

    Leaves are registered constant propositions. No ordinary SHEAR
    operations, canonicalization or constraint evaluator are used.
    """
    operation, *arguments = expression

    if operation == "external":
        return dict(CONSTANTS)[arguments[0]]
    if operation == "not":
        return negate(truth_of(arguments[0]))
    if operation == "all_of":
        return conjunction(*(truth_of(part) for part in arguments))
    if operation == "any_of":
        return disjunction(*(truth_of(part) for part in arguments))

    raise ValueError(f"unsupported oracle expression: {operation}")


def generated_tree(rng: Random, depth: int = 3) -> tuple[Any, ...]:
    if depth == 0 or rng.randrange(4) == 0:
        return ("external", rng.choice(("sat", "vio", "unk")))

    operation = rng.choice(("all_of", "any_of", "not"))
    if operation == "not":
        return ("not", generated_tree(rng, depth - 1))

    return (
        operation,
        *(generated_tree(rng, depth - 1)
          for _ in range(rng.randrange(4))),
    )


def generated_vector(seed: int) -> Vector:
    rng = Random(seed)
    tree = generated_tree(rng)
    return Vector(
        name=f"generated_{seed}",
        expression=tree,
        subject=0,
        expected=truth_of(tree),
        externals=CONSTANTS,
    )


def shrink_tree(
    expression: tuple[Any, ...],
    fails: Callable[[tuple[Any, ...]], bool],
) -> tuple[Any, ...]:
    """Return a deterministic smaller failing subtree when available."""
    if not fails(expression):
        raise ValueError("original expression does not fail")

    current = expression

    while True:
        children = tuple(
            part for part in current[1:] if isinstance(part, tuple)
        )
        smaller = next((part for part in children if fails(part)), None)

        if smaller is None:
            return current

        current = smaller


@dataclass(frozen=True)
class BoundaryWitness:
    name: str
    expected: str


# Integration witnesses whose expected behaviour must be pinned by
# Plan-owned tests, using independently specified runtime fixtures.
BOUNDARIES = (
    BoundaryWitness("external_raises", "host_failure_not_unknown"),
    BoundaryWitness("external_under_catch", "host_failure_not_catchable"),
    BoundaryWitness("missing_external", "unknown_not_violation"),
    BoundaryWitness("load_unknown", "reject_initial_version"),
    BoundaryWitness("write_unknown", "reject_without_mutation"),
    BoundaryWitness("relation_unknown", "reject_without_mutation"),
    BoundaryWitness("activation_unknown", "reject_without_switch"),
    BoundaryWitness("trial_unknown", "reject_without_trial_execution"),
    BoundaryWitness("owned_subtree", "evaluate_canonical_subtree"),
    BoundaryWitness("constraint_identity", "independent_of_evaluation"),
    BoundaryWitness("call_depth_limit", "limit_not_verdict"),
    BoundaryWitness("tail_recursion", "depth_limit_not_step_budget"),
    BoundaryWitness("candidate_effect", "no_new_mutation_authority"),
    BoundaryWitness("candidate_version", "identity_independent_of_version"),
)


def all_fixed_vectors() -> tuple[Vector, ...]:
    return PRIMITIVES + BUDGETS
