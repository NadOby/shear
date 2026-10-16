"""Plan-owned candidate-facing boundary acceptance for Task 24.

A script specifies setup and operations. The expected observation is
stored separately and is never passed to a candidate adapter.

Execute supplies implementations of the scripts using each candidate
and the affected runtime/language entry points. Adapters do not select
which outcomes are acceptable.

This harness grades observations; independent Review must also
instrument execution routes, authority boundaries and side effects.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields
from typing import Any, Callable, Iterable

from tests.constraint_function_acceptance import ROUTES
from tests.constraint_function_oracle import BOUNDARIES


@dataclass(frozen=True)
class BoundaryInput:
    script: tuple[tuple[Any, ...], ...]


@dataclass(frozen=True)
class BoundaryExpected:
    status: str
    results: tuple[str, ...] = ()
    state_unchanged: bool | None = None
    caught: bool | None = None
    effect_count: int = 0
    observed_subject: Any = None
    identity_preserved: bool | None = None


@dataclass(frozen=True)
class BoundaryObservation:
    status: str
    results: tuple[str, ...] = ()
    state_unchanged: bool | None = None
    caught: bool | None = None
    effect_count: int = 0
    observed_subject: Any = None
    identity_preserved: bool | None = None
    route: str = ""
    incumbent_calls: int = 0


@dataclass(frozen=True)
class BoundaryCase:
    name: str
    input: BoundaryInput
    expected: BoundaryExpected


@dataclass(frozen=True)
class BoundaryFailure:
    name: str
    field: str
    expected: Any
    actual: Any


@dataclass(frozen=True)
class BoundaryReport:
    candidate: str
    checked: int
    failures: tuple[BoundaryFailure, ...]
    complete_contract: bool = False

    @property
    def passed(self) -> bool:
        return (
            self.complete_contract
            and self.checked == len(BOUNDARY_CASES)
            and not self.failures
        )


def _case(
    name: str,
    script: tuple[tuple[Any, ...], ...],
    status: str,
    *,
    results: tuple[str, ...] = (),
    state_unchanged: bool | None = None,
    caught: bool | None = None,
    effect_count: int = 0,
    observed_subject: Any = None,
    identity_preserved: bool | None = None,
) -> BoundaryCase:
    return BoundaryCase(
        name,
        BoundaryInput(script),
        BoundaryExpected(
            status,
            results,
            state_unchanged,
            caught,
            effect_count,
            observed_subject,
            identity_preserved,
        ),
    )


# Script conventions:
#
# - load_cell/load_graph create a runtime, checking initial constraints.
# - write, activate_constraint and trial_constraint use the public
#   runtime boundaries, never a direct Constraint.evaluate substitute.
# - run_catch runs an ordinary SHEAR function containing catch.
# - An external table maps canonical subjects to outcomes; "raise"
#   means an escaping host exception rather than a semantic Unknown.
# - record_subject captures the canonical subject seen by the external.
# - effect_count counts unauthorized side effects originating from
#   constraint computation, not legitimate setup operations.
# - state_unchanged compares live state before and after the final
#   requested action; for rejected initial load, it means no runtime
#   version became active.
# - identity_preserved compares canonical semantic identity, not
#   Python object identity or derived executable artifact identity.
# - A limit result and a host exception are not semantic verdicts.
#
# These rules define the frozen adapter protocol. An implementation
# incapable of executing a script reports unsupported and fails.
# It must not silently fall back to the incumbent evaluator.


BOUNDARY_CASES = (
    _case(
        "external_raises",
        (
            ("external", "bomb", "raise", "HostFault"),
            ("evaluate", ("external", "bomb"), 0),
        ),
        "host_failure",
    ),
    _case(
        "external_under_catch",
        (
            ("external", "bomb", "table", (
                (0, "satisfied"),
                (1, ("raise", "HostFault")),
            )),
            ("load_cell", "c", ("external", "bomb"), 0),
            ("run_catch", ("write", "c", 1)),
        ),
        "host_failure",
        state_unchanged=True,
        caught=False,
    ),
    _case(
        "missing_external",
        (
            ("evaluate", ("external", "missing"), 0),
        ),
        "completed",
        results=("unknown",),
    ),
    _case(
        "load_unknown",
        (
            ("load_cell", "c", ("external", "missing"), 0),
        ),
        "cell_rejected",
        results=("unknown",),
        state_unchanged=True,
    ),
    _case(
        "write_unknown",
        (
            ("external", "policy", "table", (
                (0, "satisfied"),
                (1, "unknown"),
            )),
            ("load_cell", "c", ("external", "policy"), 0),
            ("write", "c", 1),
        ),
        "cell_rejected",
        results=("unknown",),
        state_unchanged=True,
    ),
    _case(
        "relation_unknown",
        (
            ("external", "policy", "role_table", (
                ("item", 0, "satisfied"),
                ("item", 1, "unknown"),
            )),
            ("load_graph", (
                ("cell", "c", ("is_kind", "int"), 0),
                ("relation", "r", ("item", "c"),
                 ("external", "policy")),
            )),
            ("write", "c", 1),
        ),
        "relation_rejected",
        results=("unknown",),
        state_unchanged=True,
    ),
    _case(
        "activation_unknown",
        (
            ("load_cell", "c", ("is_kind", "int"), 0),
            ("write", "c", 4),
            ("activate_constraint", "c",
             ("external", "missing"), "preserve_content"),
        ),
        "activation_rejected",
        results=("unknown",),
        state_unchanged=True,
    ),
    _case(
        "trial_unknown",
        (
            ("load_cell", "c", ("is_kind", "int"), 0),
            ("write", "c", 4),
            ("trial_constraint", "c",
             ("external", "missing"), "preserve_content"),
        ),
        "activation_rejected",
        results=("unknown",),
        state_unchanged=True,
    ),
    _case(
        "owned_subtree",
        (
            ("external", "capture", "record_subject",
             "satisfied"),
            ("load_graph", (
                ("value", "root", 1),
                ("value", "child", 2),
                ("owns", "root", "child"),
                ("relation", "r", ("root", "root"),
                 ("external", "capture")),
            )),
        ),
        "completed",
        results=("satisfied",),
        observed_subject=(
            ("root", (
                ("value", 1),
                ("owned", (("child", 2),)),
            )),
        ),
    ),
    _case(
        "constraint_identity",
        (
            ("compare_constraint_identity",
             ("external", "policy"),
             ("external", "policy")),
            ("evaluate_in_context",
             ("external", "policy"),
             (("policy", "satisfied"),)),
            ("evaluate_in_context",
             ("external", "policy"), ()),
        ),
        "completed",
        results=("satisfied", "unknown"),
        identity_preserved=True,
    ),
    _case(
        "call_depth_limit",
        (
            ("run_recursive_function",
             "non_tail", "depth_limit_plus_10"),
        ),
        "limit",
    ),
    _case(
        "tail_recursion",
        (
            ("run_recursive_function",
             "tail", "depth_limit_plus_10"),
        ),
        "completed",
        results=("end",),
    ),
    _case(
        "candidate_effect",
        (
            ("load_cell", "target", ("is_kind", "int"), 0),
            ("candidate_constraint",
             ("attempt_write", "target", 1)),
            ("evaluate_during_admission",),
        ),
        "effect_rejected",
        state_unchanged=True,
        effect_count=0,
    ),
    _case(
        "candidate_version",
        (
            ("construct_constraint", ("is_kind", "int")),
            ("change_active_version", "unrelated_entity"),
            ("reconstruct_constraint", ("is_kind", "int")),
            ("compare_constraint_identity",),
            ("evaluate_in_both_versions", 5),
        ),
        "completed",
        results=("satisfied", "satisfied"),
        identity_preserved=True,
    ),
)


# Every originally registered boundary witness must now be executable.
assert tuple(case.name for case in BOUNDARY_CASES) == tuple(
    witness.name for witness in BOUNDARIES
)


BoundaryCandidate = Callable[[BoundaryInput], BoundaryObservation]


def assess_boundaries(
    name: str,
    evaluate: BoundaryCandidate,
    cases: Iterable[BoundaryCase] = BOUNDARY_CASES,
) -> BoundaryReport:
    """Grade candidate execution against Plan-owned expected outcomes.

    Case names and expected fields never enter the adapter argument.

    Subsets can be run for diagnosis, but only the exact frozen
    inventory, including the original scripts and expectations in
    their original order, qualifies as a full acceptance run.

    Exceptions and unsupported scripts fail.
    """
    if not name:
        raise ValueError("candidate name must not be empty")

    failures: list[BoundaryFailure] = []
    selected = tuple(cases)

    # Dataclass equality checks the name, input script and every
    # expected field. Replacing, duplicating, omitting, reordering
    # or modifying even one case invalidates full qualification.
    complete_contract = selected == BOUNDARY_CASES

    for case in selected:
        try:
            observed = evaluate(deepcopy(case.input))
        except Exception as exc:
            failures.append(BoundaryFailure(
                case.name, "execution", "BoundaryObservation",
                type(exc).__name__,
            ))
            continue

        if not isinstance(observed, BoundaryObservation):
            failures.append(BoundaryFailure(
                case.name, "observation", "BoundaryObservation",
                repr(observed),
            ))
            continue

        if observed.route not in ROUTES:
            failures.append(BoundaryFailure(
                case.name, "route", tuple(sorted(ROUTES)),
                observed.route,
            ))

        if (
            type(observed.incumbent_calls) is not int
            or observed.incumbent_calls != 0
        ):
            failures.append(BoundaryFailure(
                case.name, "incumbent_calls", 0,
                observed.incumbent_calls,
            ))

        for field in fields(BoundaryExpected):
            expected = getattr(case.expected, field.name)
            actual = getattr(observed, field.name)

            if type(actual) is not type(expected) or actual != expected:
                failures.append(BoundaryFailure(
                    case.name,
                    field.name,
                    expected,
                    actual,
                ))

    return BoundaryReport(
        candidate=name,
        checked=len(selected),
        failures=tuple(failures),
        complete_contract=complete_contract,
    )
