"""Plan-owned candidate-facing boundary acceptance for Task 24.

Scripts specify setup and operations. Expected observations are stored
separately and are never passed to candidate adapters.

Execute supplies adapters that exercise the candidate through actual
runtime and language boundaries. Independent Review must instrument
execution routes, incumbent fallback and effects.
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
    live_cells: tuple[tuple[str, Any], ...] | None = None
    trial_cells: tuple[tuple[str, Any], ...] | None = None
    active_version_changed: bool | None = None
    trial_version_matches_staged: bool | None = None


@dataclass(frozen=True)
class BoundaryObservation:
    status: str
    results: tuple[str, ...] = ()
    state_unchanged: bool | None = None
    caught: bool | None = None
    effect_count: int = 0
    observed_subject: Any = None
    identity_preserved: bool | None = None
    live_cells: tuple[tuple[str, Any], ...] | None = None
    trial_cells: tuple[tuple[str, Any], ...] | None = None
    active_version_changed: bool | None = None
    trial_version_matches_staged: bool | None = None
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
    live_cells: tuple[tuple[str, Any], ...] | None = None,
    trial_cells: tuple[tuple[str, Any], ...] | None = None,
    active_version_changed: bool | None = None,
    trial_version_matches_staged: bool | None = None,
) -> BoundaryCase:
    return BoundaryCase(
        name,
        BoundaryInput(script),
        BoundaryExpected(
            status=status,
            results=results,
            state_unchanged=state_unchanged,
            caught=caught,
            effect_count=effect_count,
            observed_subject=observed_subject,
            identity_preserved=identity_preserved,
            live_cells=live_cells,
            trial_cells=trial_cells,
            active_version_changed=active_version_changed,
            trial_version_matches_staged=trial_version_matches_staged,
        ),
    )


# Script conventions:
#
# - Script entity names denote EntityID values with those exact strings.
# - load_cell/load_graph check initial content before admitting a runtime.
# - write, activate_constraint and trial_constraint invoke the actual
#   candidate-integrated runtime boundaries, not direct predicates.
# - preserve_content means one-to-one continuation of the existing cell.
# - run_catch executes a SHEAR function containing language catch.
# - External tables map canonical subjects to outcomes or host failures.
# - record_subject captures the canonical subject passed to an external.
# - results records semantic observations in script operation order.
# - state_unchanged compares the live runtime before and after the
#   final operation; it includes active version and live cell content.
# - live_cells contains the named live cell content after that operation.
# - trial_cells contains content in the newly staged trial runtime,
#   never content inferred from the main runtime alone.
# - active_version_changed compares active versions immediately before
#   and after the final operation. Writes and trials must not switch it.
# - trial_version_matches_staged checks the trial's admitted destination
#   state against the actual transformation destination.
# - effect_count excludes legitimate setup operations and counts only
#   unauthorized side effects originating in candidate evaluation.
# - identity_preserved concerns semantic identity, not artifact identity.
# - A host failure or execution limit is not a semantic verdict.
#
# Candidate adapters receive scripts but never expected observations.
# They must report unsupported operations rather than silently fall back.


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
        # Independently specified canonical form of:
        # {"root": {"value": 1, "owned": {EntityID("child"): 2}}}
        observed_subject=(
            "__type__", "map", (
                (
                    "root",
                    ("__type__", "map", (
                        (
                            "owned",
                            ("__type__", "map", (
                                (
                                    ("__type__", "entity_id", "child"),
                                    2,
                                ),
                            )),
                        ),
                        ("value", 1),
                    )),
                ),
            ),
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
    _case(
        "write_satisfied",
        (
            ("load_cell", "c", ("int_range", 0, 10), 0),
            ("write", "c", 7),
        ),
        "completed",
        results=("satisfied",),
        state_unchanged=False,
        live_cells=(("c", 7),),
        active_version_changed=False,
    ),
    _case(
        "activation_satisfied",
        (
            ("load_cell", "c", ("int_range", 0, 10), 0),
            ("write", "c", 4),
            ("activate_constraint", "c",
             ("int_range", 0, 100), "preserve_content"),
        ),
        "completed",
        results=("satisfied",),
        state_unchanged=False,
        live_cells=(("c", 4),),
        active_version_changed=True,
    ),
    _case(
        "trial_satisfied",
        (
            ("load_cell", "c", ("int_range", 0, 10), 0),
            ("write", "c", 4),
            ("trial_constraint", "c",
             ("int_range", 0, 100), "preserve_content"),
        ),
        "completed",
        results=("satisfied",),
        state_unchanged=True,
        live_cells=(("c", 4),),
        trial_cells=(("c", 4),),
        active_version_changed=False,
        trial_version_matches_staged=True,
    ),
)


# The original 14 witnesses remain intact. The three positive
# admission cases extend, rather than replace, their inventory.
assert tuple(
    case.name for case in BOUNDARY_CASES[:len(BOUNDARIES)]
) == tuple(witness.name for witness in BOUNDARIES)
assert tuple(case.name for case in BOUNDARY_CASES[len(BOUNDARIES):]) == (
    "write_satisfied",
    "activation_satisfied",
    "trial_satisfied",
)
assert len({case.name for case in BOUNDARY_CASES}) == len(BOUNDARY_CASES)


BoundaryCandidate = Callable[[BoundaryInput], BoundaryObservation]


def _canonical_subject_tree(value: Any) -> tuple[Any, ...]:
    """Normalize tagged tuples without production canonicalization.

    CanonicalNode is a tuple subclass. Preserve the complete
    tagged structure, ordering and primitive types while ignoring
    only that subclass distinction.
    """
    if isinstance(value, tuple):
        return (
            "tuple",
            tuple(_canonical_subject_tree(item) for item in value),
        )
    return (type(value).__name__, value)


def assess_boundaries(
    name: str,
    evaluate: BoundaryCandidate,
    cases: Iterable[BoundaryCase] = BOUNDARY_CASES,
) -> BoundaryReport:
    """Grade candidate execution against frozen expected outcomes.

    Diagnostic subsets are allowed, but cannot qualify.
    Complete qualification requires the exact frozen inventory,
    including scripts, expectations, names and order.
    """
    if not name:
        raise ValueError("candidate name must not be empty")

    failures: list[BoundaryFailure] = []
    selected = tuple(cases)
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

            if field.name == "observed_subject" and expected is not None:
                matches = (
                    _canonical_subject_tree(actual)
                    == _canonical_subject_tree(expected)
                )
            else:
                matches = (
                    type(actual) is type(expected)
                    and actual == expected
                )

            if not matches:
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
