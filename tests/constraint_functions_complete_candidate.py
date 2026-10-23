"""GH-123 candidate adapter for authenticated ordinary SHEAR evaluation.

This adapter translates constraint declarations into canonical values and
prepares admitted SHEAR code. It never computes constraint truth in Python.

Registered External continuation and runtime-boundary integration remain
separate implementation work. Unsupported cases fail explicitly.
"""

from __future__ import annotations

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
    bound_evaluator_entities,
)
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from shear.lang import load
from tests.constraint_function_acceptance import CandidateInput, Observation
from tests.constraint_function_oracle import KindSample


EVALUATOR_ENTRIES = frozenset({BOUND_ENTRY})


def _constraint(expression: tuple) -> Constraint:
    """Construct a semantic declaration, without evaluating its subject."""
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


def semantic(case: CandidateInput) -> Observation:
    """Return the actual admitted SHEAR result for the supplied subject."""
    executor, deployment, entry = prepare_semantic(
        case.expression,
        case.budget,
        case.externals,
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
