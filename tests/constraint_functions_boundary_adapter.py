"""Task 24/123 script boundary through real SHEAR runtime and admitted code.

Scripts are operations, never oracles. Only typed Runtime exceptions, live
states, authenticated semantic results and observed callbacks supply output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shear import (
    ActivationRejected,
    CellContentRejected,
    CellDeclaration,
    ConstraintResult,
    EntityID,
    EvaluationContext,
    Evaluator,
    Relation,
    RelationConstraintRejected,
    Runtime,
    State,
    Value,
    canonicalize,
    transform_with_mapping,
)
from shear.bytecode import CALL_DEPTH_LIMIT
from shear.canonical import CanonicalNode
from shear.hosted_bootstrap.errors import AdmissionRejected
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from shear.lang import CallDepthExceeded, Function, links, load, run
from shear.relations import relation_of
from tests.constraint_function_boundary_acceptance import (
    BoundaryInput,
    BoundaryObservation,
)
from tests.constraint_functions_runtime_admission import open_candidate_runtime


class HostFault(RuntimeError):
    """Exception supplied by a host External, not a semantic verdict."""


def _candidate():
    from tests import constraint_functions_complete_candidate
    return constraint_functions_complete_candidate


def _entity(name: str) -> EntityID:
    return EntityID(name)


def _constraint(expression: tuple):
    return _candidate()._constraint(expression)


def _cell(name: str, expression: tuple, initial: object) -> Value:
    entity = _entity(name)
    return Value.create(entity, CellDeclaration(_constraint(expression), initial))


def _relation(name: str, role: tuple, expression: tuple) -> Value:
    return Value.create(
        _entity(name),
        Relation("boundary.constraint", {role[0]: _entity(role[1])},
                 _constraint(expression)),
    )


def _make_state(specs: tuple, *, catcher: tuple | None = None) -> State:
    values: dict[EntityID, Value] = {}
    ownership: dict[EntityID, list[EntityID]] = {}
    for spec in specs:
        kind = spec[0]
        if kind == "cell":
            _, name, expr, initial = spec
            value = _cell(name, expr, initial)
        elif kind == "value":
            _, name, raw = spec
            value = Value.create(_entity(name), raw)
        elif kind == "relation":
            _, name, role, expr = spec
            value = _relation(name, role, expr)
        elif kind == "owns":
            _, parent, child = spec
            ownership.setdefault(_entity(parent), []).append(_entity(child))
            continue
        else:
            raise ValueError(f"unsupported graph declaration: {kind}")
        values[value.entity] = value

    if catcher is not None:
        entry = _entity("boundary.run_catch")
        cell = _entity(catcher[1])
        values[entry] = Value.create(
            entry, Function((), (
                "catch", ("write", "target", ("lit", catcher[2])),
                ("cell_rejected",),
            )),
        )
        link = _entity("boundary.run_catch.links")
        values[link] = Value.create(link, links(entry, target=cell))
        return load(State.create(values, ownership))

    return State.create(values, ownership)


def _external(name: str, mode: str, declaration: object, seen: list):
    if mode == "raise":
        def fail(_subject):
            raise HostFault(str(declaration))
        return Evaluator(fail)

    if mode == "record_subject":
        def record(subject):
            seen.append(canonicalize(subject))
            return ConstraintResult(declaration)
        return Evaluator(record)

    if mode not in ("table", "role_table"):
        raise ValueError(f"unsupported external mode {mode!r}")

    cases = tuple(declaration)

    def evaluate(subject):
        if mode == "role_table":
            canonical = canonicalize(subject)
            if not isinstance(canonical, CanonicalNode) or canonical[1] != "map":
                raise ValueError("role-table expected a semantic map")
            members = dict(canonical[2])
            for role, content, verdict in cases:
                if role in members and members[role] == canonicalize(content):
                    return _callback_verdict(verdict)
        else:
            for content, verdict in cases:
                if canonicalize(subject) == canonicalize(content):
                    return _callback_verdict(verdict)
        return ConstraintResult.UNKNOWN

    return Evaluator(evaluate)


def _callback_verdict(value):
    if isinstance(value, tuple) and value[0] == "raise":
        raise HostFault(str(value[1]))
    return ConstraintResult(value)


def _contents(runtime: Runtime) -> tuple[tuple[str, object], ...]:
    return tuple(sorted(
        ((key.value, value) for key, value in runtime.active.cells.items()),
        key=lambda item: item[0],
    ))


def _snapshot(runtime: Runtime):
    return runtime.active.id, _contents(runtime)


def _recursive(kind: str, depth: int):
    entry = _entity("boundary.recurse")
    remaining = ("arg", "n")
    tail = ("call", "recurse", ("sub", remaining, ("lit", 1)))
    body = (
        "if", ("lt", remaining, ("lit", 1)),
        ("lit", "end"),
        tail if kind == "tail" else ("seq", tail, ("lit", "end")),
    )
    state = load(State.create({
        entry: Value.create(entry, Function(("n",), body)),
        _entity("boundary.recurse.links"): Value.create(
            _entity("boundary.recurse.links"), links(entry, recurse=entry),
        ),
    }))
    return run(Runtime(state), entry, depth)


@dataclass
class _Runner:
    script: tuple
    externals: dict = field(default_factory=dict)
    observed_subjects: list = field(default_factory=list)
    external_results: list = field(default_factory=list)
    runtime: Runtime | None = None
    last_trial: Runtime | None = None
    results: list = field(default_factory=list)
    status: str = "completed"
    state_unchanged: bool | None = None
    caught: bool | None = None
    live_cells: tuple | None = None
    trial_cells: tuple | None = None
    active_version_changed: bool | None = None
    trial_version_matches_staged: bool | None = None
    identity_preserved: bool | None = None
    original_constraint: object = None
    rebuilt_constraint: object = None
    identity_source: State | None = None
    effect_count: int = 0
    observed_subject: object = None

    def _context(self):
        return EvaluationContext(self.externals)

    def _admit(self, specs, catcher=None):
        before_count = len(self.observed_subjects)
        state = _make_state(specs, catcher=catcher)
        self.runtime = open_candidate_runtime(state, self._context())
        # An external relation directly constrained the loaded graph. When
        # loading is the terminal operation, report that actual admission.
        if len(self.observed_subjects) > before_count:
            self.observed_subject = self.observed_subjects[-1]
        return self.runtime

    def _before(self):
        if self.runtime is None:
            raise AssertionError("runtime operation requires an admitted state")
        return _snapshot(self.runtime)

    def _after(self, before, *, report_live):
        now = self._before()
        self.state_unchanged = now == before
        # A definite verdict supports reporting the live content and
        # active-version observation. An Unknown rejection establishes only
        # atomic non-mutation, not a decisive admission observation.
        self.active_version_changed = (
            now[0] != before[0] if report_live else None
        )
        self.live_cells = now[1] if report_live else None

    def _result(self, actual):
        self.results.append(actual.value if isinstance(actual, ConstraintResult) else actual)

    def _raise_from_runtime(self, exc, before, *, report_live=False):
        self._after(before, report_live=report_live)
        self._result(exc.result)
        if isinstance(exc, CellContentRejected):
            self.status = "cell_rejected"
        elif isinstance(exc, RelationConstraintRejected):
            self.status = "relation_rejected"
        elif isinstance(exc, ActivationRejected):
            self.status = "activation_rejected"
        else:
            raise AssertionError("unexpected runtime rejection")

    def perform(self, step):
        kind, *args = step
        if kind == "external":
            name, mode, declaration = args
            underlying = _external(
                name, mode, declaration, self.observed_subjects,
            )

            def observed(subject, evaluator=underlying):
                result = evaluator.evaluate(subject)
                self.external_results.append(result)
                return result

            self.externals[name] = Evaluator(observed)
            return
        if kind == "evaluate":
            expression, subject = args
            callback_map = {
                name: evaluator.evaluate
                for name, evaluator in self.externals.items()
            }
            actual = _candidate()._run_external_continuation(
                _constraint(expression), subject, None, callback_map,
            )
            self._result(actual.outcome)
            return
        if kind == "load_cell":
            name, expression, content = args
            catching = next(
                (op[1] for op in self.script if op[0] == "run_catch"),
                None,
            )
            try:
                self._admit((("cell", name, expression, content),), catching)
            except CellContentRejected as exc:
                self.status = "cell_rejected"
                self._result(exc.result)
                self.state_unchanged = True
            return
        if kind == "load_graph":
            self._admit(args[0])
            return
        if kind == "run_catch":
            if self.runtime is None:
                raise AssertionError("catch requires a runtime")
            before = self._before()
            entry = _entity("boundary.run_catch")
            try:
                actual = run(self.runtime, entry)
            except HostFault:
                self.status = "host_failure"
                self.caught = False
                self.state_unchanged = self._before() == before
            else:
                self.caught = actual[0] == "failed"
            return
        if kind == "write":
            name, value = args
            # Report the verdict of the current mutation, not the earlier
            # successful operations used to prepare its live content.
            self.results.clear()
            before = self._before()
            try:
                self.runtime.write(_entity(name), value)
            except (CellContentRejected, RelationConstraintRejected) as exc:
                self._raise_from_runtime(
                    exc, before,
                    report_live=exc.result is ConstraintResult.VIOLATED,
                )
            else:
                self._result("satisfied")
                self._after(before, report_live=True)
            return
        if kind in ("activate_constraint", "trial_constraint"):
            name, expression, transfer = args
            if transfer != "preserve_content":
                raise ValueError("only explicit content continuity supported")
            # Activation/trial supersedes preparatory write verdicts;
            # earlier successful writes remain real committed operations.
            self.results.clear()
            before = self._before()
            source = self.runtime.active.state
            entity = _entity(name)
            result = transform_with_mapping(
                source,
                {entity: CellDeclaration(_constraint(expression),
                                         self.runtime.read(entity))},
                {cell: cell for cell in self.runtime.active.cells},
            )
            try:
                if kind == "activate_constraint":
                    self.runtime.activate(result)
                else:
                    self.last_trial = self.runtime.trial(result)
            except ActivationRejected as exc:
                self._raise_from_runtime(
                    exc, before,
                    report_live=exc.result is ConstraintResult.VIOLATED,
                )
            else:
                self._result("satisfied")
                self._after(before, report_live=True)
                if kind == "trial_constraint":
                    self.trial_cells = _contents(self.last_trial)
                    self.trial_version_matches_staged = (
                        self.last_trial.active.id == result.destination.id
                    )
            return
        if kind == "rename_continuity":
            old, new = args
            source = self.runtime.active.state
            original = self.runtime.active.state.values[_entity(old)]
            result = transform_with_mapping(
                source, {_entity(new): original.content},
                {_entity(old): _entity(new)},
            )
            self.runtime.activate(result)
            return
        if kind == "assert_entity_absent":
            name, = args
            if self.runtime.active.state.contains(_entity(name)):
                raise AssertionError("entity survived declared rename")
            return
        if kind == "assert_relation_role":
            relation, role, target = args
            record = relation_of(self.runtime.active.state.values[_entity(relation)])
            if record is None or record.roles.get(role) != _entity(target):
                raise AssertionError("relation endpoint did not follow continuity")
            return
        if kind == "compare_constraint_identity":
            if args:
                left, right = args
                self.identity_preserved = _candidate().equal_projection(
                    _constraint(left), _constraint(right),
                )
            else:
                if self.original_constraint is None or self.rebuilt_constraint is None:
                    raise AssertionError("identity comparison missing values")
                self.identity_preserved = _candidate().equal_projection(
                    self.original_constraint, self.rebuilt_constraint,
                )
            return
        if kind == "evaluate_in_context":
            expression, registrations = args
            callbacks = {
                name: (lambda _subject, verdict=value: ConstraintResult(verdict))
                for name, value in registrations
            }
            observed = _candidate()._run_external_continuation(
                _constraint(expression), 0, None, callbacks,
            )
            self._result(observed.outcome)
            return
        if kind == "run_recursive_function":
            implementation, limit = args
            if limit != "depth_limit_plus_10":
                raise ValueError("unknown recursion boundary")
            try:
                self._result(_recursive(implementation, CALL_DEPTH_LIMIT + 10))
            except CallDepthExceeded:
                self.status = "limit"
            return
        if kind == "candidate_constraint":
            operation, entity, value = args[0]
            if operation != "attempt_write":
                raise ValueError("unknown candidate effect")
            self._candidate_write = (_entity(entity), value)
            return
        if kind == "evaluate_during_admission":
            before = self._before()
            # RestrictedExecutor performs the real effects preflight. An
            # effectful candidate must be rejected before any VM execution.
            entry = _entity("boundary.effect.entry")
            cell, value = self._candidate_write
            source = load(State.create({
                entry: Value.create(entry, Function((), (
                    "write", "target", ("lit", value),
                ))),
                _entity("boundary.effect.links"): Value.create(
                    _entity("boundary.effect.links"),
                    links(entry, target=cell),
                ),
                # The pure deployment holds a named effect target; its
                # forbidden write must fail preflight before execution.
                cell: Value.create(cell, self.runtime.read(cell)),
            }))
            executor = RestrictedExecutor()
            deployment = executor.deploy(source)
            try:
                executor.run(deployment, entry)
            except AdmissionRejected as exc:
                if "forbidden source write" not in str(exc):
                    raise AssertionError(
                        "effect refusal was not caused by forbidden write"
                    ) from exc
                self.status = "effect_rejected"
            else:
                raise AssertionError("effectful restricted code executed")
            self.effect_count = int(self._before() != before)
            self.state_unchanged = self._before() == before
            return
        if kind == "construct_constraint":
            self.original_constraint = _constraint(args[0])
            return
        if kind == "change_active_version":
            name, = args
            self.identity_source = State.create({
                _entity(name): Value.create(_entity(name), None),
            })
            self.runtime = open_candidate_runtime(self.identity_source)
            next_state = self.identity_source.with_changes({_entity(name): 1})
            self.runtime.activate(next_state)
            return
        if kind == "reconstruct_constraint":
            original, reconstructed = _candidate().reconstruct_constraint(args[0])
            if self.original_constraint is not None and not _candidate().equal_projection(
                self.original_constraint, original,
            ):
                raise AssertionError("reconstruction changed original identity")
            self.rebuilt_constraint = reconstructed
            return
        if kind == "evaluate_in_both_versions":
            subject, = args
            if self.original_constraint is None or self.rebuilt_constraint is None:
                raise AssertionError("missing versioned constraints")
            executor, deployment, entry = _candidate()._generic_ordinary_deployment(
                _candidate()._PRIVATE_COMPILER_GENERATION,
                _candidate()._PRIVATE_SEMANTIC_AUTHORITY,
            )
            for constraint in (self.original_constraint, self.rebuilt_constraint):
                self._result(executor.run(
                    deployment, entry, subject, constraint, None, (),
                ))
            return
        raise NotImplementedError(f"unsupported boundary script operation {kind!r}")

    def observe(self) -> BoundaryObservation:
        for index, step in enumerate(self.script):
            try:
                self.perform(step)
            except HostFault:
                self.status = "host_failure"
                break
            if self.status != "completed":
                break
        if self.runtime is not None and not self.results:
            # For terminal graph loads, the relation outcome is observed
            # through the externally dispatched admitted evaluator.
            if self.script[-1][0] == "load_graph":
                relations = [
                    value for value in self.runtime.active.state.values.values()
                    if relation_of(value) is not None
                    and relation_of(value).kind == "boundary.constraint"
                ]
                if relations and self.external_results:
                    self._result(self.external_results[-1])
        return BoundaryObservation(
            status=self.status,
            results=tuple(self.results),
            state_unchanged=self.state_unchanged,
            caught=self.caught,
            effect_count=self.effect_count,
            observed_subject=self.observed_subject,
            identity_preserved=self.identity_preserved,
            live_cells=self.live_cells,
            trial_cells=self.trial_cells,
            active_version_changed=self.active_version_changed,
            trial_version_matches_staged=self.trial_version_matches_staged,
            route="compiled",
            incumbent_calls=0,
        )


def boundary(case: BoundaryInput) -> BoundaryObservation:
    """Execute a frozen Task 24/123 script without accessing its oracle."""
    if not isinstance(case, BoundaryInput):
        raise TypeError("boundary requires BoundaryInput")
    return _Runner(tuple(case.script)).observe()
