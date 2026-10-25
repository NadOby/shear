"""GH-123 candidate adapter for authenticated ordinary SHEAR evaluation.

Python constructs semantic declarations and admitted programs, but never
computes semantic verdicts, equality or inspection results.

Ordinary and registered constraints use shared generic authenticated code.
Dynamic callbacks suspend SHEAR and resume its authenticated continuation.
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
    BUDGET_STEP,
    INT_RANGE as PRIMITIVE_INT_RANGE,
    IS_KIND as PRIMITIVE_IS_KIND,
    LENGTH as PRIMITIVE_LENGTH,
    LOGIC_NOT,
    ONE_OF as PRIMITIVE_ONE_OF,
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
RECONSTRUCT_ENTRY = EntityID("constraint.reconstruct")
REGISTERED_ENTRY = EntityID("constraint.registered.entry")
REGISTERED_EVALUATE = EntityID("constraint.registered.evaluate")
REGISTERED_NODE = EntityID("constraint.registered.node")
REGISTERED_ALL = EntityID("constraint.registered.all")
REGISTERED_ANY = EntityID("constraint.registered.any")
REGISTERED_ROLE = EntityID("constraint.registered.role")
REGISTERED_FIND = EntityID("constraint.registered.find")
REGISTERED_LOOKUP = EntityID("constraint.registered.lookup")

EVALUATOR_ENTRIES = frozenset({
    BOUND_ENTRY,
    CONTINUATION_START,
    CONTINUATION_RESUME,
    RECONSTRUCT_ENTRY,
    REGISTERED_ENTRY,
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


def _validate_registrations(registrations: tuple) -> None:
    """Reject malformed static inputs before entering the deployment cache.

    A rejected registration is never admitted and never changes the cache's
    hit/miss counters or creates an otherwise unreachable entry.
    """
    names = set()
    for name, verdict in registrations:
        if type(name) is not str or not name or name in names:
            raise ValueError("registrations need unique nonempty names")
        if type(verdict) is not str or verdict not in _VERDICTS:
            raise ValueError("invalid registered External verdict")
        names.add(name)


def _registered_entities() -> dict[EntityID, Function | Relation]:
    """Generic runtime-parameterized SHEAR interpreter for all nine forms.

    Neither constraint, budget, subject nor registered outcomes appear in
    compiled function bodies. Every evaluation, including short circuit and
    remaining-node budget, is computed by the admitted machine.
    """
    def arg(name: str) -> tuple:
        return ("arg", name)

    def lit(value: object) -> tuple:
        return ("lit", value)

    def item(value: tuple, index: int | str) -> tuple:
        return ("item", value, lit(index))

    def call(name: str, *args: tuple) -> tuple:
        return ("call", name, *args)

    def outcome(verdict: tuple, remaining: tuple) -> tuple:
        return ("tuple", verdict, remaining)

    subject = arg("subject")
    constraint = arg("constraint")
    remaining = arg("remaining")
    registrations = arg("registrations")
    arguments = arg("arguments")
    parts = arg("parts")
    index = arg("index")
    child = arg("child")
    verdict = item(child, 0)
    child_remaining = item(child, 1)
    seen = arg("seen_unknown")

    def evaluate(subject: tuple, constraint: tuple, remaining: tuple,
                 registrations: tuple) -> tuple:
        return call("evaluate", subject, constraint, remaining, registrations)

    step = arg("step")
    evaluate_body = (
        "let", "step", call("budget", remaining),
        (
            "if", item(step, 0),
            call("node", subject, constraint, item(step, 1), registrations),
            outcome(lit("unknown"), item(step, 1)),
        ),
    )

    negated = (
        "let", "child", evaluate(subject, item(arguments, 0), remaining,
                                registrations),
        outcome(call("negate", item(child, 0)), item(child, 1)),
    )

    alternatives = (
        ("is_kind", outcome(
            call("is_kind", subject, item(arguments, 0)), remaining)),
        ("int_range", outcome(call(
            "int_range", subject, item(arguments, 0), item(arguments, 1)),
            remaining)),
        ("length", outcome(call(
            "length", subject, item(arguments, 0), item(arguments, 1)),
            remaining)),
        ("one_of", outcome(
            call("one_of", subject, item(arguments, 0)), remaining)),
        ("all_of", call(
            "all", subject, item(arguments, 0), lit(0),
            remaining, lit(False), registrations)),
        ("any_of", call(
            "any", subject, item(arguments, 0), lit(0),
            remaining, lit(False), registrations)),
        ("not", negated),
        ("role", call(
            "role", subject, item(arguments, 0), item(arguments, 1),
            remaining, registrations)),
        ("external", outcome(call(
            "external", item(arguments, 0), registrations, lit(0)),
            remaining)),
    )
    cases = (
        "raise", lit("constraint_form"), lit("unknown constraint form"),
    )
    for form, body in reversed(alternatives):
        cases = ("if", ("eq", arg("form"), lit(form)), body, cases)
    node_body = (
        "let", "form", item(constraint, "form"),
        ("let", "arguments", item(constraint, "arguments"), cases),
    )

    def fold(decisive: str, empty: str) -> tuple:
        next_seen = (
            "if", ("eq", verdict, lit("unknown")), lit(True), seen,
        )
        return (
            "if", ("lt", index, ("len", parts)),
            (
                "let", "child", evaluate(
                    subject, ("item", parts, index), remaining, registrations),
                (
                    "if", ("eq", verdict, lit(decisive)), child,
                    call("next", subject, parts, ("add", index, lit(1)),
                         child_remaining, next_seen, registrations),
                ),
            ),
            outcome(("if", seen, lit("unknown"), lit(empty)), remaining),
        )

    role_body = (
        "if", ("eq", item(("inspect", subject), 0), lit("map")),
        call("find", subject, arg("name"), arg("part"), lit(0),
             remaining, registrations),
        outcome(lit("violated"), remaining),
    )
    entry = arg("entry")
    find_body = (
        "if", ("lt", index, ("len", subject)),
        (
            "let", "entry", ("item", subject, index),
            (
                "if", ("eq", item(entry, 0), arg("name")),
                evaluate(item(entry, 1), arg("part"), remaining,
                         registrations),
                call("next", subject, arg("name"), arg("part"),
                     ("add", index, lit(1)), remaining, registrations),
            ),
        ),
        outcome(lit("violated"), remaining),
    )

    registration = arg("registration")
    lookup_body = (
        "if", ("lt", index, ("len", registrations)),
        (
            "let", "registration", ("item", registrations, index),
            (
                "if", ("eq", item(registration, 0), arg("name")),
                item(registration, 1),
                call("next", arg("name"), registrations,
                     ("add", index, lit(1))),
            ),
        ),
        lit("unknown"),
    )

    entities = evaluator_entities()
    entities.update({
        REGISTERED_ENTRY: Function(
            ("subject", "constraint", "remaining", "registrations"),
            item(evaluate(subject, constraint, remaining, registrations), 0),
        ),
        REGISTERED_EVALUATE: Function(
            ("subject", "constraint", "remaining", "registrations"),
            evaluate_body,
        ),
        REGISTERED_NODE: Function(
            ("subject", "constraint", "remaining", "registrations"),
            node_body,
        ),
        REGISTERED_ALL: Function(
            ("subject", "parts", "index", "remaining", "seen_unknown",
             "registrations"), fold("violated", "satisfied"),
        ),
        REGISTERED_ANY: Function(
            ("subject", "parts", "index", "remaining", "seen_unknown",
             "registrations"), fold("satisfied", "violated"),
        ),
        REGISTERED_ROLE: Function(
            ("subject", "name", "part", "remaining", "registrations"),
            role_body,
        ),
        REGISTERED_FIND: Function(
            ("subject", "name", "part", "index", "remaining",
             "registrations"), find_body,
        ),
        REGISTERED_LOOKUP: Function(
            ("name", "registrations", "index"), lookup_body,
        ),
        EntityID(f"{REGISTERED_ENTRY.value}.links"): links(
            REGISTERED_ENTRY, evaluate=REGISTERED_EVALUATE),
        EntityID(f"{REGISTERED_EVALUATE.value}.links"): links(
            REGISTERED_EVALUATE, budget=BUDGET_STEP, node=REGISTERED_NODE),
        EntityID(f"{REGISTERED_NODE.value}.links"): links(
            REGISTERED_NODE,
            is_kind=PRIMITIVE_IS_KIND,
            int_range=PRIMITIVE_INT_RANGE,
            length=PRIMITIVE_LENGTH,
            one_of=PRIMITIVE_ONE_OF,
            all=REGISTERED_ALL,
            any=REGISTERED_ANY,
            negate=LOGIC_NOT,
            evaluate=REGISTERED_EVALUATE,
            role=REGISTERED_ROLE,
            external=REGISTERED_LOOKUP,
        ),
        EntityID(f"{REGISTERED_ALL.value}.links"): links(
            REGISTERED_ALL, evaluate=REGISTERED_EVALUATE,
            next=REGISTERED_ALL),
        EntityID(f"{REGISTERED_ANY.value}.links"): links(
            REGISTERED_ANY, evaluate=REGISTERED_EVALUATE,
            next=REGISTERED_ANY),
        EntityID(f"{REGISTERED_ROLE.value}.links"): links(
            REGISTERED_ROLE, find=REGISTERED_FIND),
        EntityID(f"{REGISTERED_FIND.value}.links"): links(
            REGISTERED_FIND, evaluate=REGISTERED_EVALUATE,
            next=REGISTERED_FIND),
        EntityID(f"{REGISTERED_LOOKUP.value}.links"): links(
            REGISTERED_LOOKUP, next=REGISTERED_LOOKUP),
    })
    return _projection_static_closure(entities, REGISTERED_ENTRY)


@lru_cache(maxsize=None)
def _generic_registered_deployment(
    registrations: tuple[tuple[str, str], ...],
    compiler_generation: int,
    authority: object,
) -> tuple[RestrictedExecutor, object, EntityID]:
    """One authenticated program per registration authority, not per tree.

    Values, constraints and node budgets are runtime operands, not literals
    embedded in the compiled deployment. Cache hits never bypass VM entry.
    """
    if authority is not _PRIVATE_SEMANTIC_AUTHORITY:
        raise ValueError("incompatible semantic authority")
    source = load(program(_registered_entities()))
    executor = RestrictedExecutor()
    deployment = executor.deploy(
        source, compiler_generation=compiler_generation,
    )
    return executor, deployment, REGISTERED_ENTRY


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
        _validate_registrations(tuple(externals))
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
def _generic_ordinary_deployment(
    compiler_generation: int,
    authority: object,
) -> tuple[RestrictedExecutor, object, EntityID]:
    """Admit one generic evaluator for all ordinary constraints and budgets.

    No semantic input is embedded in compiled code. The underlying generic
    deployment is issued and authenticated exactly once per authority and
    compiler generation; every call still re-enters restricted execution.
    """
    if authority is not _PRIVATE_SEMANTIC_AUTHORITY:
        raise ValueError("incompatible semantic authority")
    return _generic_registered_deployment(
        (), compiler_generation, authority,
    )


def _private_semantic_preparation(
    constraint: Constraint,
    budget: int | None,
    compiler_generation: int,
    externals: tuple,
    authority: object,
) -> tuple[RestrictedExecutor, object, EntityID]:
    """Legacy private preparation interface, with generic VM execution.

    Constraint and budget are validated by the caller and passed as live
    runtime operands. They must not become part of deployment identity.
    """
    if externals:
        raise NotImplementedError(
            "registered Externals use separate static preparations"
        )
    if authority is not _PRIVATE_SEMANTIC_AUTHORITY:
        raise ValueError("incompatible semantic authority")
    return _generic_ordinary_deployment(
        compiler_generation, authority,
    )


_private_semantic_preparation.cache_info = (
    _generic_ordinary_deployment.cache_info
)
_private_semantic_preparation.cache_clear = (
    _generic_ordinary_deployment.cache_clear
)


def _private_registered_preparation(
    constraint: Constraint,
    budget: int | None,
    registrations: tuple[tuple[str, str], ...],
    compiler_generation: int,
    authority: object,
) -> tuple[RestrictedExecutor, object, EntityID]:
    """Reuse one admitted program across distinct normalized constraints.

    Keep the established caller signature and cache API. Neither constraint
    nor budget determines the executable code: both are runtime operands.
    """
    return _generic_registered_deployment(
        registrations, compiler_generation, authority,
    )


_private_registered_preparation.cache_info = (
    _generic_registered_deployment.cache_info
)
_private_registered_preparation.cache_clear = (
    _generic_registered_deployment.cache_clear
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
            _validate_registrations(tuple(case.externals))
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

    subject = _materialize_subject(case.subject)
    if entry == REGISTERED_ENTRY:
        # Ordinary and registered invocations use the same generic VM code.
        # No semantic verdict or budget decisions are computed in Python.
        result = executor.run(
            deployment, entry, subject, constraint, case.budget,
            tuple(case.externals),
        )
    else:
        result = executor.run(deployment, entry, subject)
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


@lru_cache(maxsize=1)
def _reconstruction_deployment() -> tuple[RestrictedExecutor, object]:
    """Admit one generic SHEAR reconstruction, independent of its input.

    Record validation and canonical identity are handled by the semantic
    RECORD instruction. No host-side canonical-content reconstruction runs.
    """
    original = ("arg", "original")
    source = load(program({
        RECONSTRUCT_ENTRY: Function(
            ("original",),
            (
                "tuple",
                original,
                (
                    "record",
                    ("lit", "constraint"),
                    (
                        "tuple",
                        ("item", original, ("lit", "form")),
                        ("item", original, ("lit", "arguments")),
                    ),
                ),
            ),
        ),
    }))
    executor = RestrictedExecutor()
    return executor, executor.deploy(source)


def reconstruct_constraint(expression: tuple) -> tuple:
    """Return original and VM-rebuilt typed constraint content.

    Only the admitted SHEAR return supplies the pair. The host may reject a
    malformed machine result, but must not synthesize or repair either value.
    """
    original = _constraint(expression)
    executor, deployment = _reconstruction_deployment()
    result = executor.run(deployment, RECONSTRUCT_ENTRY, original)
    if type(result) is not tuple or len(result) != 2:
        error = ValueError("invalid SHEAR reconstruction result")
        error.projection_operation = "reconstruct_constraint"
        error.rejected_vm_output = result
        raise error
    return result


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
