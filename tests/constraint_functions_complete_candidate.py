"""GH-123 candidate adapter for authenticated ordinary SHEAR evaluation.

Python constructs semantic declarations and admitted programs, but never
computes semantic verdicts, equality or inspection results.

Registered External continuation and runtime integration remain separate.
Unsupported cases fail explicitly.
"""

from __future__ import annotations

from functools import lru_cache

from shear import (
    AllOf,
    AnyOf,
    CellDeclaration,
    EntityID,
    External,
    IntRange,
    IsKind,
    Length,
    Not,
    OneOf,
    Relation,
    Role,
    StateID,
    VersionID,
)
from shear.closures import Closure
from shear.constraints import Constraint
from shear.examples._support import program
from shear.examples.constraint_evaluator import (
    BOUND_ENTRY,
    VALUE_EQUAL,
    bound_evaluator_entities,
    evaluator_entities,
)
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from shear.lang import Function, links, load
from tests.constraint_function_acceptance import CandidateInput, Observation
from tests.constraint_function_oracle import KindSample


PROJECT_INSPECT = EntityID("constraint.project.inspect")
PROJECT_EQUAL = EntityID("constraint.project.equal")
PROJECT_SELECT = EntityID("constraint.project.select")
PROJECT_LENGTH = EntityID("constraint.project.length")
PROJECT_SLICE = EntityID("constraint.project.slice")

EVALUATOR_ENTRIES = frozenset({
    BOUND_ENTRY,
    PROJECT_INSPECT,
    PROJECT_EQUAL,
    PROJECT_SELECT,
    PROJECT_LENGTH,
    PROJECT_SLICE,
})


def _constraint(expression: tuple) -> Constraint:
    """Construct a semantic declaration without evaluating its subject."""
    if not isinstance(expression, tuple) or not expression:
        raise TypeError("constraint expression must be a nonempty tuple")

    form, *arguments = expression

    if form == "is_kind":
        return IsKind(*arguments)
    if form == "int_range":
        return IntRange(*arguments)
    if form == "length":
        return Length(*arguments)
    if form == "one_of":
        if len(arguments) != 1:
            raise ValueError("one_of requires one collection")
        return OneOf(*arguments[0])
    if form == "all_of":
        return AllOf(*(_constraint(part) for part in arguments))
    if form == "any_of":
        return AnyOf(*(_constraint(part) for part in arguments))
    if form == "not":
        if len(arguments) != 1:
            raise ValueError("not requires one component")
        return Not(_constraint(arguments[0]))
    if form == "role":
        if len(arguments) != 2:
            raise ValueError("role requires a name and component")
        return Role(arguments[0], _constraint(arguments[1]))
    if form == "external":
        return External(*arguments)

    raise ValueError(f"unknown constraint form: {form!r}")


def _materialize_subject(subject: object) -> object:
    """Resolve symbolic kind descriptors, never expected observations."""
    if not isinstance(subject, KindSample):
        return subject

    kind = subject.kind
    if kind == "entity_id":
        return EntityID("sample")
    if kind == "version_id":
        return VersionID("sample")
    if kind == "state_id":
        return StateID("sample")
    if kind == "cell":
        return CellDeclaration(IsKind("int"), 3)
    if kind == "constraint":
        return IsKind("int")
    if kind == "relation":
        return Relation("sample", {"item": EntityID("sample")})
    if kind == "closure":
        return Closure(
            EntityID("sample.owner"),
            EntityID("sample.body"),
            (),
            (("captured", 3),),
        )

    raise ValueError(f"unsupported symbolic subject kind: {kind!r}")


def prepare_semantic(
    expression: tuple,
    budget: int | None,
    externals: tuple,
) -> tuple[RestrictedExecutor, object, EntityID]:
    """Prepare one subject-independent, authenticated evaluator."""
    constraint = _constraint(expression)

    if externals:
        raise NotImplementedError(
            "registered External continuation is not implemented"
        )

    source = load(program(
        bound_evaluator_entities(constraint, budget)
    ))
    executor = RestrictedExecutor()
    deployment = executor.deploy(source)
    return executor, deployment, BOUND_ENTRY


# Public preparation remains separately issued and invalidatable.
# Only the ordinary semantic path reuses private deployments.
_ORIGINAL_PREPARE_SEMANTIC = prepare_semantic
_PRIVATE_SEMANTIC_AUTHORITY = object()
_PRIVATE_COMPILER_GENERATION = 1


@lru_cache(maxsize=None)
def _private_semantic_preparation(
    constraint: Constraint,
    budget: int | None,
    compiler_generation: int,
    externals: tuple,
    authority: object,
) -> tuple[RestrictedExecutor, object, EntityID]:
    """Reuse private authenticated deployments, never verdicts.

    Canonical Constraint equality and hashing define cache identity.
    No eviction can conceal invalidation by issuing a replacement.
    """
    if externals:
        raise NotImplementedError(
            "registered External continuation is not implemented"
        )
    if authority is not _PRIVATE_SEMANTIC_AUTHORITY:
        raise ValueError("incompatible semantic authority")

    source = load(program(
        bound_evaluator_entities(constraint, budget)
    ))
    executor = RestrictedExecutor()
    deployment = executor.deploy(
        source, compiler_generation=compiler_generation,
    )
    return executor, deployment, BOUND_ENTRY


def semantic(case: CandidateInput) -> Observation:
    """Return the actual admitted SHEAR result for the supplied subject."""
    # Preserve test-controlled interception and External isolation.
    if (
        prepare_semantic is not _ORIGINAL_PREPARE_SEMANTIC
        or case.externals
    ):
        executor, deployment, entry = prepare_semantic(
            case.expression,
            case.budget,
            case.externals,
        )
    else:
        constraint = _constraint(case.expression)
        if case.budget is not None and (
            type(case.budget) is not int or case.budget < 0
        ):
            raise ValueError("budget must be a non-negative integer")

        executor, deployment, entry = _private_semantic_preparation(
            constraint,
            case.budget,
            _PRIVATE_COMPILER_GENERATION,
            (),
            _PRIVATE_SEMANTIC_AUTHORITY,
        )

    result = executor.run(
        deployment,
        entry,
        _materialize_subject(case.subject),
    )

    if result not in ("satisfied", "violated", "unknown"):
        raise ValueError("admitted evaluator returned an invalid verdict")

    return Observation(
        outcome=result,
        route="compiled",
        incumbent_calls=0,
    )


def _projection_inspection() -> tuple:
    """Build a SHEAR expression that reports kind, length and value."""
    value = ("arg", "value")
    inspected = ("arg", "inspected")
    kind = ("item", inspected, ("lit", 0))

    size = ("lit", None)
    for name in reversed(("str", "bytes", "tuple", "list", "map")):
        size = (
            "if",
            ("eq", kind, ("lit", name)),
            ("len", value),
            size,
        )

    return (
        "let", "inspected", ("inspect", value),
        (
            "tuple",
            kind,
            size,
            ("item", inspected, ("lit", 1)),
        ),
    )


def _projection_selection() -> tuple:
    """Walk public semantic paths entirely through ordinary SHEAR."""
    value = ("arg", "value")
    path = ("arg", "path")
    index = ("arg", "index")

    return (
        "if",
        ("lt", index, ("len", path)),
        (
            "call",
            "next",
            ("item", value, ("item", path, index)),
            path,
            ("add", index, ("lit", 1)),
        ),
        value,
    )


def _projection_entities() -> dict:
    """Define admitted generic operations with explicit static links."""
    entities = evaluator_entities()

    entities[PROJECT_INSPECT] = Function(
        ("value",),
        _projection_inspection(),
    )
    entities[PROJECT_EQUAL] = Function(
        ("left", "right"),
        (
            "call",
            "equal",
            ("arg", "left"),
            ("arg", "right"),
        ),
    )
    entities[PROJECT_SELECT] = Function(
        ("value", "path", "index"),
        _projection_selection(),
    )
    entities[PROJECT_LENGTH] = Function(
        ("value",),
        ("len", ("arg", "value")),
    )
    entities[PROJECT_SLICE] = Function(
        ("value", "start", "stop"),
        (
            "slice",
            ("arg", "value"),
            ("arg", "start"),
            ("arg", "stop"),
        ),
    )

    entities[EntityID(f"{PROJECT_EQUAL.value}.links")] = links(
        PROJECT_EQUAL,
        equal=VALUE_EQUAL,
    )
    entities[EntityID(f"{PROJECT_SELECT.value}.links")] = links(
        PROJECT_SELECT,
        next=PROJECT_SELECT,
    )

    return entities


def _projection_static_closure(
    entities: dict[EntityID, Function | Relation],
    entry: EntityID,
) -> dict[EntityID, Function | Relation]:
    """Retain every statically linked function and links relation.

    Discover links by their function role, not a conventional entity name.
    Include the entire transitive closure, including recursive links.
    """
    linked: dict[EntityID, tuple[EntityID, Relation]] = {}
    for entity, value in entities.items():
        if not isinstance(value, Relation) or value.kind != "links":
            continue
        owner = value.roles.get("function")
        if not isinstance(owner, EntityID) or owner in linked:
            raise ValueError("malformed or duplicate function links")
        linked[owner] = (entity, value)

    selected: dict[EntityID, Function | Relation] = {}
    pending = [entry]
    while pending:
        function = pending.pop()
        if function in selected:
            continue
        definition = entities.get(function)
        if not isinstance(definition, Function):
            raise ValueError(
                f"missing static projection function: {function.value}"
            )
        selected[function] = definition
        link = linked.get(function)
        if link is None:
            continue
        relation_entity, relation = link
        selected[relation_entity] = relation
        for role, target in relation.roles.items():
            if role == "function":
                continue
            if not isinstance(target, EntityID):
                raise ValueError("malformed static projection link")
            pending.append(target)
    return selected


@lru_cache(maxsize=None)
def _projection_deployment(entry: EntityID) -> tuple:
    """Issue one minimal authenticated deployment for each public operation."""
    if entry not in (
        PROJECT_INSPECT, PROJECT_EQUAL, PROJECT_SELECT,
        PROJECT_LENGTH, PROJECT_SLICE,
    ):
        raise ValueError("unknown projection operation")

    source = load(program(
        _projection_static_closure(_projection_entities(), entry)
    ))
    executor = RestrictedExecutor()
    deployment = executor.deploy(source)
    return executor, deployment


def inspect_projection(value: object) -> tuple:
    """Return the inspection result produced by admitted SHEAR code."""
    executor, deployment = _projection_deployment(PROJECT_INSPECT)
    return executor.run(deployment, PROJECT_INSPECT, value)


def equal_projection(left: object, right: object) -> bool:
    """Use recursive, type-sensitive SHEAR equality."""
    executor, deployment = _projection_deployment(PROJECT_EQUAL)
    return executor.run(deployment, PROJECT_EQUAL, left, right)


def select_projection(value: object, path: tuple) -> object:
    """Traverse a public semantic path inside the authenticated VM."""
    executor, deployment = _projection_deployment(PROJECT_SELECT)
    return executor.run(
        deployment,
        PROJECT_SELECT,
        value,
        path,
        0,
    )


def sequence_projection(
    value: object,
    operation: str,
    *arguments: object,
) -> object:
    """Dispatch the requested generic sequence operation to SHEAR.

    Unsupported float operands are rejected before canonical VM entry.
    Representable but invalid operands reach the admitted operation.
    """
    if operation == "len":
        if arguments:
            raise TypeError("len takes no bounds")
        entry = PROJECT_LENGTH
    elif operation == "slice":
        if len(arguments) != 2:
            raise TypeError("slice requires start and stop")
        if any(type(argument) is float for argument in arguments):
            raise TypeError("float bounds are not canonical SHEAR values")
        entry = PROJECT_SLICE
    else:
        raise ValueError(f"unknown sequence operation: {operation!r}")

    executor, deployment = _projection_deployment(entry)
    return executor.run(deployment, entry, value, *arguments)
