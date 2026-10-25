"""GH-123 candidate adapter for authenticated ordinary SHEAR evaluation.

Python constructs semantic declarations and admitted programs, but never
computes semantic verdicts, equality or inspection results.

Named External constants run directly inside SHEAR. Dynamic callbacks
suspend SHEAR at an External node and resume its authenticated continuation.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable, Mapping

from shear import (
    AllOf,
    AnyOf,
    CellDeclaration,
    ConstraintResult,
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
    canonicalize,
)
from shear.closures import Closure
from shear.constraints import Constraint, _record_host_failure
from shear.examples._support import program
from shear.examples.constraint_continuation import (
    START as CONTINUATION_START,
    RESUME as CONTINUATION_RESUME,
    continuation_entities,
)
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
    CONTINUATION_START,
    CONTINUATION_RESUME,
    PROJECT_INSPECT,
    PROJECT_EQUAL,
    PROJECT_SELECT,
    PROJECT_LENGTH,
    PROJECT_SLICE,
})

_VERDICTS = frozenset(("satisfied", "violated", "unknown"))


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


def _validate_budget(budget: int | None) -> None:
    if budget is not None and (
        type(budget) is not int or budget < 0
    ):
        raise ValueError("budget must be a non-negative integer")


def _deploy_continuation(
    constraint: Constraint,
    budget: int | None,
    registrations: tuple[tuple[str, str], ...] | None,
    compiler_generation: int = 1,
) -> tuple[RestrictedExecutor, object, EntityID]:
    """Admit subject-independent SHEAR; never precompute a verdict."""
    source = load(program(
        continuation_entities(constraint, budget, registrations)
    ))
    executor = RestrictedExecutor()
    deployment = executor.deploy(
        source, compiler_generation=compiler_generation,
    )
    return executor, deployment, CONTINUATION_START


def prepare_semantic(
    expression: tuple,
    budget: int | None,
    externals: tuple,
) -> tuple[RestrictedExecutor, object, EntityID]:
    """Prepare a subject-independent evaluator returning a direct verdict.

    Registered constant Externals are SHEAR code, not host callbacks.
    Unregistered Externals retain the ordinary Unknown semantics.
    """
    constraint = _constraint(expression)
    _validate_budget(budget)

    if externals:
        return _deploy_continuation(
            constraint, budget, tuple(externals)
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
            "registered Externals use separate static preparations"
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


@lru_cache(maxsize=None)
def _private_registered_preparation(
    constraint: Constraint,
    budget: int | None,
    registrations: tuple[tuple[str, str], ...],
    compiler_generation: int,
    authority: object,
) -> tuple[RestrictedExecutor, object, EntityID]:
    """Cache admitted static declarations, never evaluation outcomes."""
    if authority is not _PRIVATE_SEMANTIC_AUTHORITY:
        raise ValueError("incompatible semantic authority")
    return _deploy_continuation(
        constraint, budget, registrations, compiler_generation,
    )


@lru_cache(maxsize=None)
def _private_dynamic_preparation(
    constraint: Constraint,
    budget: int | None,
    compiler_generation: int,
    authority: object,
) -> tuple[RestrictedExecutor, object, EntityID]:
    """Keep dynamic continuation authority local and invalidatable."""
    if authority is not _PRIVATE_SEMANTIC_AUTHORITY:
        raise ValueError("incompatible semantic authority")
    return _deploy_continuation(
        constraint, budget, None, compiler_generation,
    )


def _observation(result: object) -> Observation:
    if type(result) is not str or result not in _VERDICTS:
        raise ValueError("admitted evaluator returned an invalid verdict")
    return Observation(
        outcome=result,
        route="compiled",
        incumbent_calls=0,
    )


def semantic(case: CandidateInput) -> Observation:
    """Return the actual admitted SHEAR result for the supplied subject."""
    # Preserve test-controlled public preparation interception.
    if prepare_semantic is not _ORIGINAL_PREPARE_SEMANTIC:
        executor, deployment, entry = prepare_semantic(
            case.expression,
            case.budget,
            case.externals,
        )
    else:
        constraint = _constraint(case.expression)
        _validate_budget(case.budget)

        if case.externals:
            executor, deployment, entry = _private_registered_preparation(
                constraint,
                case.budget,
                tuple(case.externals),
                _PRIVATE_COMPILER_GENERATION,
                _PRIVATE_SEMANTIC_AUTHORITY,
            )
        else:
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
    return _observation(result)


def _run_external_continuation(
    constraint: Constraint,
    subject: object,
    budget: int | None,
    callbacks: Mapping[str, Callable[[object], ConstraintResult]],
) -> Observation:
    """Run SHEAR until completion, dispatching only requested callbacks.

    Host code never interprets a constraint or continuation frame; each
    response re-enters authenticated SHEAR using its unchanged token.
    """
    _validate_budget(budget)
    executor, deployment, entry = _private_dynamic_preparation(
        constraint,
        budget,
        _PRIVATE_COMPILER_GENERATION,
        _PRIVATE_SEMANTIC_AUTHORITY,
    )
    result = executor.run(deployment, entry, _materialize_subject(subject))

    while isinstance(result, tuple):
        if (
            len(result) != 4
            or result[0] != "external"
            or type(result[1]) is not str
            or not result[1]
            or not isinstance(result[3], tuple)
            or len(result[3]) != 2
        ):
            raise ValueError("malformed External continuation from SHEAR")

        _, name, canonical_subject, continuation = result
        callback = callbacks.get(name)
        if callback is None:
            verdict = ConstraintResult.UNKNOWN
        else:
            try:
                verdict = callback(canonicalize(canonical_subject))
            except BaseException as exc:
                _record_host_failure(exc)
                raise
            if not isinstance(verdict, ConstraintResult):
                raise TypeError(
                    "external callback must return ConstraintResult"
                )

        result = executor.run(
            deployment,
            CONTINUATION_RESUME,
            continuation,
            verdict.value,
        )

    return _observation(result)


def evaluate_external(
    name: str,
    subject: object,
    budget: int | None,
    callback: Callable[[object], ConstraintResult] | None = None,
) -> Observation:
    """Evaluate a named External through authenticated SHEAR continuation.

    Missing callbacks yield Unknown; callback failures escape by identity.
    Budget exhaustion is handled by SHEAR before any host dispatch.
    """
    if callback is not None and not callable(callback):
        raise TypeError("external callback must be callable")
    callbacks = {} if callback is None else {name: callback}
    return _run_external_continuation(
        External(name), subject, budget, callbacks,
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
