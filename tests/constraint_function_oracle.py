"""Independent semantic oracle and frozen Task 24 experiment vectors.

No imports from shear. Expected outcomes are specified independently
of production evaluation, canonicalization and candidate execution.

KindSample is a symbolic fixture descriptor for semantic record kinds.
The control and candidate adapters must materialize it as the named
semantic kind before evaluating a constraint.
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
class KindSample:
    """Descriptor, not a canonical value or a predicted answer."""

    kind: str


@dataclass(frozen=True)
class Vector:
    """Expression is descriptive input, not canonical program content."""

    name: str
    expression: tuple[Any, ...]
    subject: Any
    expected: str
    budget: int | None = None
    externals: tuple[tuple[str, str], ...] = ()


# Explicitly pinned kind inventory. The implementation currently
# supports fifteen kinds, rather than the sixteen in the review text.
#
# This inventory is not derived from the production KINDS registry.
KIND_SAMPLES = (
    ("none", None),
    ("bool", True),
    ("int", 5),
    ("str", "text"),
    ("bytes", b"data"),
    ("entity_id", KindSample("entity_id")),
    ("version_id", KindSample("version_id")),
    ("state_id", KindSample("state_id")),
    ("tuple", (1,)),
    ("list", [1]),
    ("map", {"item": 1}),
    ("cell", KindSample("cell")),
    ("constraint", KindSample("constraint")),
    ("relation", KindSample("relation")),
    ("closure", KindSample("closure")),
)

KIND_VECTORS = tuple(
    Vector(
        f"kind_{kind}",
        ("is_kind", kind),
        subject,
        SAT,
    )
    for kind, subject in KIND_SAMPLES
)


# Primitive expectations are fixed without running the model.
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
    Vector(
        "role_present",
        ("role", "x", ("int_range", 0, 5)),
        {"x": 3},
        SAT,
    ),
    Vector(
        "role_violated",
        ("role", "x", ("int_range", 0, 5)),
        {"x": 8},
        VIO,
    ),
    Vector(
        "role_missing",
        ("role", "x", ("is_kind", "int")),
        {"y": 3},
        VIO,
    ),
    Vector(
        "role_not_map",
        ("role", "x", ("is_kind", "int")),
        (3,),
        VIO,
    ),
    Vector("external_absent", ("external", "missing"), 1, UNK),
    Vector(
        "external_satisfied",
        ("external", "sat"),
        1, SAT,
        externals=CONSTANTS,
    ),
    Vector(
        "external_unknown",
        ("external", "unk"),
        1, UNK,
        externals=CONSTANTS,
    ),
)


def _external(result: str) -> tuple[str, str]:
    return ("external", {
        SAT: "sat",
        VIO: "vio",
        UNK: "unk",
    }[result])


# Every binary row of strong-Kleene AND/OR, both operand orders,
# all three NOT rows, and canonical repetition/order witnesses.
LOGICAL = tuple(
    Vector(
        f"{operation}_{left}_{right}",
        (operation, _external(left), _external(right)),
        0,
        (
            conjunction(left, right)
            if operation == "all_of"
            else disjunction(left, right)
        ),
        externals=CONSTANTS,
    )
    for operation in ("all_of", "any_of")
    for left, right in product(RESULTS, repeat=2)
) + tuple(
    Vector(
        f"not_{result}",
        ("not", _external(result)),
        0,
        negate(result),
        externals=CONSTANTS,
    )
    for result in RESULTS
) + (
    Vector("empty_and", ("all_of",), 0, SAT),
    Vector("empty_or", ("any_of",), 0, VIO),
    Vector(
        "and_duplicate",
        ("all_of", _external(SAT), _external(SAT)),
        0, SAT, externals=CONSTANTS,
    ),
    Vector(
        "or_duplicate",
        ("any_of", _external(VIO), _external(VIO)),
        0, VIO, externals=CONSTANTS,
    ),
    Vector(
        "and_mixed_duplicate",
        ("all_of", _external(UNK), _external(SAT),
         _external(UNK)),
        0, UNK, externals=CONSTANTS,
    ),
    Vector(
        "and_swapped_first",
        ("all_of", _external(SAT), _external(VIO)),
        0, VIO, externals=CONSTANTS,
    ),
    Vector(
        "and_swapped_second",
        ("all_of", _external(VIO), _external(SAT)),
        0, VIO, externals=CONSTANTS,
    ),
    Vector(
        "or_swapped_first",
        ("any_of", _external(VIO), _external(SAT)),
        0, SAT, externals=CONSTANTS,
    ),
    Vector(
        "or_swapped_second",
        ("any_of", _external(SAT), _external(VIO)),
        0, SAT, externals=CONSTANTS,
    ),
)


# Node budgets count the root and each evaluated child.
_PAIR = ("all_of", ("is_kind", "int"), ("int_range", 0, 10))
_DOUBLE_NOT = ("not", ("not", ("is_kind", "int")))

_SHORT_EXTERNALS = (
    ("a_vio", VIO),
    ("z_sat", SAT),
    ("a_sat", SAT),
    ("z_vio", VIO),
)

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
        "deduplicated_or",
        ("any_of", ("is_kind", "bool"), ("is_kind", "bool")),
        5, VIO, 2,
    ),
    Vector(
        "external_no_budget",
        ("external", "sat"), 5, UNK, 0, CONSTANTS,
    ),
    Vector(
        "external_one_step",
        ("external", "sat"), 5, SAT, 1, CONSTANTS,
    ),
    Vector(
        "external_missing_with_budget",
        ("external", "missing"), 5, UNK, 1, CONSTANTS,
    ),
    Vector(
        "and_short_circuit_first",
        ("all_of", ("external", "a_vio"),
         ("external", "z_sat")),
        0, VIO, 2, _SHORT_EXTERNALS,
    ),
    Vector(
        "and_short_circuit_reordered",
        ("all_of", ("external", "z_sat"),
         ("external", "a_vio")),
        0, VIO, 2, _SHORT_EXTERNALS,
    ),
    Vector(
        "or_short_circuit_first",
        ("any_of", ("external", "a_sat"),
         ("external", "z_vio")),
        0, SAT, 2, _SHORT_EXTERNALS,
    ),
    Vector(
        "or_short_circuit_reordered",
        ("any_of", ("external", "z_vio"),
         ("external", "a_sat")),
        0, SAT, 2, _SHORT_EXTERNALS,
    ),
    Vector(
        "and_late_violation_exhausted",
        ("all_of", ("external", "a_sat"),
         ("external", "z_vio")),
        0, UNK, 2, _SHORT_EXTERNALS,
    ),
    Vector(
        "or_late_satisfaction_exhausted",
        ("any_of", ("external", "a_vio"),
         ("external", "z_sat")),
        0, UNK, 2, _SHORT_EXTERNALS,
    ),
)


def truth_of(expression: tuple[Any, ...]) -> str:
    """Independent unbudgeted mathematical oracle.

    Leaves are registered constant propositions. This does not
    execute a SHEAR operation or canonicalize semantic content.
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
        *(
            generated_tree(rng, depth - 1)
            for _ in range(rng.randrange(4))
        ),
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


# These templates have no decisive early exit: all components
# must be evaluated to reach the stated outcome. Counts include
# the outer operator, nested operators and deduplicated children.
#
# Expected outcomes and complete costs are pinned independently.
_BUDGET_TEMPLATES = (
    ("conjunction", _PAIR, 5, 3, SAT),
    (
        "disjunction",
        ("any_of", ("is_kind", "bool"), ("int_range", 0, 10)),
        12, 3, VIO,
    ),
    (
        "role_negation",
        ("not", ("role", "item", ("int_range", 0, 10))),
        {"item": 5}, 3, VIO,
    ),
    (
        "dedup_conjunction",
        ("all_of", ("is_kind", "int"), ("is_kind", "int")),
        5, 2, SAT,
    ),
    (
        "dedup_disjunction",
        ("any_of", ("is_kind", "bool"), ("is_kind", "bool")),
        5, 2, VIO,
    ),
    (
        "nested_conjunction",
        ("all_of", ("not", ("is_kind", "bool")),
         ("int_range", 0, 10)),
        5, 4, SAT,
    ),
    (
        "nested_disjunction",
        ("any_of", ("not", ("is_kind", "int")),
         ("is_kind", "bool")),
        5, 4, VIO,
    ),
)


def generated_budget_vector(seed: int) -> Vector:
    """Deterministic primitive/composition budget discriminator.

    Under the pinned templates, a partial evaluation cannot
    establish a definitive verdict. Exhaustion therefore yields
    Unknown, independently of child evaluation order.
    """
    rng = Random(seed ^ 0x24B0D)
    name, expression, subject, cost, complete = rng.choice(
        _BUDGET_TEMPLATES
    )
    budget = rng.randrange(cost + 2)

    return Vector(
        name=f"generated_budget_{seed}_{name}",
        expression=expression,
        subject=subject,
        expected=complete if budget >= cost else UNK,
        budget=budget,
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


# Named Plan-level integration obligations. Candidate-facing
# executable scenarios are supplied by a separate Plan file.
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
    return KIND_VECTORS + PRIMITIVES + LOGICAL + BUDGETS
