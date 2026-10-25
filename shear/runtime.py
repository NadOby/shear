"""Runtime state: loaded versions, mutable cell content, and holds.

Program states are immutable semantic values. A ``Runtime`` is the mutable
runtime state of one running program: the content of its mutable cells and
the record of what depends on which loaded version.

Ownership follows activation_model.md section 7: the runtime root owns the
loaded versions, and each version owns the content of its cells. Holds record
that running code or runtime-held references depend on a version.

Cell content must satisfy the cell's constraint. A runtime checks the initial
content of every cell when it loads a version, and checks every write, using
its evaluation context. Only ``SATISFIED`` is accepted: ``VIOLATED`` and
``UNKNOWN`` are both rejected.

Constraint relations (relation_model.md section 7) are checked the same way:
when a version loads, when a write changes one of their endpoint cells, and
against the staged content of an activation or trial run.

Activation (activation_model.md) switches the runtime to the destination of a
transformation result. Everything is staged first and the switch is atomic:
a rejected activation leaves the runtime unchanged.

A host can follow versions with a ``VersionListener`` for the length of a
run (``listening``): it is told of a candidate version after the runtime has
staged and accepted it and before anything changes, so it can refuse it by
raising; of a version that retires; and of the end of a trial. The hosted
route (docs/live_evolution.md) uses it to compile and admit a candidate before
the switch or the trial. A runtime with no listener behaves as before.
"""

from __future__ import annotations

import contextlib
from contextvars import ContextVar
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Iterator, Mapping, Protocol

from .canonical import canonicalize
from .cells import CellDeclaration, cells_of
from .constraints import Constraint, ConstraintResult, EvaluationContext
from .identity import EntityID, StateID
from .ownership import owner_of
from .relations import constraint_relations, role_subject
from .references import (
    AmbiguousEntityMapping,
    CrossStateReference,
    MissingEntityMapping,
    Reference,
)
from .state import State
from .transforms import (
    TransformationConflict,
    TransformResult,
    rebase,
    transfer_reference,
)


class VersionListener(Protocol):
    """What a host attaches to follow versions (see ``listening``)."""

    def candidate(
        self,
        runtime: "Runtime",
        version: "Version",
        how: str,
    ) -> None:
        """``version`` is the staged, accepted destination of an
        ``"activate"`` or a ``"trial"`` of ``runtime``. Nothing has changed
        yet: an exception raised here leaves the runtime as it was."""

    def retired(self, runtime: "Runtime", version: "Version") -> None:
        """``version`` was removed from ``runtime``'s loaded versions."""

    def trial_ended(self, runtime: "Runtime", version: "Version") -> None:
        """The run of a trial ``runtime`` ended, whether it returned or
        failed; ``version`` is its version."""


# The listener of the current run, if any. A context variable, so that a run
# nested in another (the hosted route's compiler runs) can leave it.
_LISTENER: ContextVar[VersionListener | None] = ContextVar(
    "shear_version_listener",
    default=None,
)


@contextlib.contextmanager
def listening(listener: VersionListener | None) -> Iterator[None]:
    """Attach ``listener`` to every runtime for the duration of the block, or
    detach the current one with None."""

    token = _LISTENER.set(listener)

    try:
        yield
    finally:
        _LISTENER.reset(token)


def _admission_scope(
    context: EvaluationContext,
    target_state_id: StateID,
    operation: str,
):
    """Use optional host operation metadata without changing plain contexts.

    One admission operation pins evaluator selections through all its cell
    and relation checks. The hook is not canonical content, an additional
    constraint evaluator, or a language-visible effect.
    """

    operation_scope = getattr(context, "operation_scope", None)
    if operation_scope is None:
        return contextlib.nullcontext()
    return operation_scope(target_state_id, operation)


def _evaluate_admission_constraint(
    constraint: Constraint,
    subject: Any,
    context: EvaluationContext,
) -> ConstraintResult:
    """Evaluate through an optional admission authority, without fallback.

    Ordinary EvaluationContext retains existing runtime behavior.
    A custom context may expose an evaluate_constraint hook whose verdict
    must come from its selected authority (e.g. authenticated SHEAR).
    """
    evaluate = getattr(context, "evaluate_constraint", None)
    if evaluate is None:
        return constraint.evaluate(subject, context)

    if not callable(evaluate):
        raise TypeError("admission evaluator must be callable")

    result = evaluate(constraint, canonicalize(subject))
    if type(result) is not ConstraintResult:
        raise TypeError("admission evaluator must return ConstraintResult")
    return result


class CellError(ValueError):
    """A cell operation named an entity that is not a mutable cell."""


class CellContentRejected(ValueError):
    """Cell content was not established to satisfy the cell's constraint."""

    def __init__(
        self,
        cell: EntityID,
        result: ConstraintResult,
        operation: str,
    ) -> None:
        super().__init__(
            f"{operation} of cell {cell.value} rejected: constraint is "
            f"{result.value}"
        )
        self.cell = cell
        self.result = result


class RelationConstraintRejected(ValueError):
    """A constraint relation was not established to be satisfied."""

    def __init__(
        self,
        relation: EntityID,
        result: ConstraintResult,
        operation: str,
    ) -> None:
        super().__init__(
            f"{operation} rejected: constraint relation {relation.value} is "
            f"{result.value}"
        )
        self.relation = relation
        self.result = result


class ActivationRejected(ValueError):
    """An activation was rejected; the runtime is unchanged."""

    def __init__(
        self,
        reason: str,
        cell: EntityID | None = None,
        result: ConstraintResult | None = None,
        relation: EntityID | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.cell = cell
        self.result = result
        self.relation = relation


class ActivationConflict(ActivationRejected, TransformationConflict):
    """A result built from a state this runtime had active earlier does not
    combine with a result activated since (continuity_inference.md section
    5); the runtime is unchanged.
    """


def _failed_constraint_relation(
    state: State,
    cells: Mapping[EntityID, Any],
    context: EvaluationContext,
    touching: EntityID | None = None,
) -> tuple[EntityID, ConstraintResult] | None:
    """Return the first constraint relation not established as satisfied.

    Endpoint content is the runtime content of a cell, or the value content
    of any other entity. An endpoint that owns entities contributes that
    content together with its owned subtree, as ``{"value": ...,
    "owned": {child: ...}}`` (relation_model.md section 7). With
    ``touching``, only relations that have that entity, or one of its
    owners, as an endpoint are checked.
    """

    def content_of(entity: EntityID) -> Any:
        if entity in cells:
            own = cells[entity]
        else:
            own = state.values[entity].content

        children = state.ownership.get(entity, ())

        if not children:
            return own

        return {
            "value": own,
            "owned": {child: content_of(child) for child in children},
        }

    affected: set[EntityID] | None = None

    for entity, (relation, constraint) in constraint_relations(state).items():
        if touching is not None:
            if affected is None:
                affected = set()
                current: EntityID | None = touching

                while current is not None:
                    affected.add(current)
                    current = owner_of(state.ownership, current)

            if affected.isdisjoint(relation.endpoints):
                continue

        outcome = _evaluate_admission_constraint(
            constraint,
            role_subject(relation, content_of),
            context,
        )

        if outcome is not ConstraintResult.SATISFIED:
            return entity, outcome

    return None


@dataclass(frozen=True)
class Converter:
    """Executable conversion of cell content at activation.

    A converter receives the canonical content of every source cell mapped
    into one destination cell, keyed by source entity, and returns that
    cell's new content. Like an ``Evaluator``, it is not a semantic value:
    transformation definitions refer to converters by name.
    """

    function: Callable[[Mapping[EntityID, Any]], Any]
    description: str = ""

    def __post_init__(self) -> None:
        if not callable(self.function):
            raise TypeError("converter function must be callable")

        if not isinstance(self.description, str):
            raise TypeError("converter description must be a string")

    def convert(self, sources: Mapping[EntityID, Any]) -> Any:
        return canonicalize(
            self.function(MappingProxyType(dict(sources)))
        )


def _check_content(
    cell: EntityID,
    declaration: CellDeclaration,
    content: object,
    context: EvaluationContext,
    operation: str,
) -> None:
    result = _evaluate_admission_constraint(
        declaration.constraint, content, context,
    )

    if result is not ConstraintResult.SATISFIED:
        raise CellContentRejected(cell, result, operation)


class Version:
    """A program state loaded into a runtime.

    A version is owned by the runtime root and owns the content of its
    mutable cells. Cell content is runtime state: writing it never changes the
    version's program state or ``StateID``. A retired version has been
    destroyed together with the cell content it owned.
    """

    def __init__(
        self,
        state: State,
        contents: Mapping[EntityID, Any],
    ) -> None:
        self._state = state
        self._declarations = cells_of(state)
        self._cells: dict[EntityID, Any] = dict(contents)
        self._holds: set[Hold] = set()
        self._runtime: Runtime | None = None
        self._retired = False

    @staticmethod
    def _load(state: State, context: EvaluationContext) -> "Version":
        declarations = cells_of(state)

        for entity, declaration in declarations.items():
            _check_content(
                entity,
                declaration,
                declaration.initial,
                context,
                "initial content",
            )

        contents = {
            entity: declaration.initial
            for entity, declaration in declarations.items()
        }
        failure = _failed_constraint_relation(state, contents, context)

        if failure is not None:
            raise RelationConstraintRejected(*failure, "load")

        return Version(state, contents)

    @property
    def state(self) -> State:
        return self._state

    @property
    def id(self) -> StateID:
        return self._state.id

    @property
    def cells(self) -> Mapping[EntityID, Any]:
        """Read-only view of current cell content."""

        return MappingProxyType(self._cells)

    @property
    def holds(self) -> frozenset[Hold]:
        """Holds currently recorded on this version."""

        return frozenset(self._holds)

    @property
    def retired(self) -> bool:
        return self._retired

    def __repr__(self) -> str:
        return f"Version({self.id.value[:12]}, holds={len(self._holds)})"


class Hold:
    """Runtime-internal record that something depends on a version.

    A hold is deliberately narrower than a borrow: it covers a whole version,
    it is tracked dynamically by the runtime, and it has no lifetimes,
    aliasing rules, or presence in types.
    """

    def __init__(self, version: Version) -> None:
        self._version = version
        self._released = False
        version._holds.add(self)

    @property
    def version(self) -> Version:
        return self._version

    @property
    def released(self) -> bool:
        return self._released

    def release(self) -> None:
        if self._released:
            raise ValueError("hold is already released")

        self._version._holds.discard(self)
        self._released = True

        runtime = self._version._runtime

        if runtime is not None:
            runtime._retire_if_unused(self._version)

    def _move(self, version: Version) -> None:
        self._version._holds.discard(self)
        version._holds.add(self)
        self._version = version


class Frame(Hold):
    """Simulated frame executing the code of an entity in a version."""

    def __init__(self, version: Version, entity: EntityID) -> None:
        super().__init__(version)
        self._entity = entity

    @property
    def entity(self) -> EntityID:
        return self._entity


class KeptReference(Hold):
    """A reference held by runtime state, holding the version it points into."""

    def __init__(self, version: Version, reference: Reference) -> None:
        super().__init__(version)
        self._reference = reference

    @property
    def reference(self) -> Reference:
        return self._reference


class Runtime:
    """Mutable runtime state of one running program.

    The runtime root owns the loaded versions: the active version and, after
    an activation, the previous version for as long as something holds it.
    The initial version is loaded from a program state with every cell set to
    its declared initial content.
    """

    def __init__(
        self,
        state: State,
        context: EvaluationContext | None = None,
    ) -> None:
        self._context = context or EvaluationContext()
        with _admission_scope(self._context, state.id, "load"):
            self._active = Version._load(state, self._context)
        self._active._runtime = self
        self._versions: list[Version] = [self._active]
        # Every result activated, in order, so that a result built from an
        # earlier active state can be rebased over those that followed it.
        self._history: list[TransformResult] = []

    @property
    def context(self) -> EvaluationContext:
        """Evaluation context used to check cell content."""

        return self._context

    @property
    def active(self) -> Version:
        return self._active

    @property
    def versions(self) -> tuple[Version, ...]:
        """Loaded versions owned by the runtime root, active first."""

        return tuple(self._versions)

    @property
    def previous(self) -> Version | None:
        """The superseded version still held, if any."""

        for version in self._versions:
            if version is not self._active:
                return version

        return None

    def _retire_if_unused(self, version: Version) -> None:
        # Retirement destroys the version's owned subtree: its cell content.
        if (
            version is self._active
            or version._holds
            or version not in self._versions
        ):
            return

        self._versions.remove(version)
        version._cells.clear()
        version._retired = True
        listener = _LISTENER.get()

        if listener is not None:
            listener.retired(self, version)

    def _active_cell(self, cell: EntityID) -> None:
        if not self._active.state.contains(cell):
            raise KeyError(
                f"{cell.value} is absent from {self._active.id.value}"
            )

        if cell not in self._active._cells:
            raise CellError(f"{cell.value} is not a mutable cell")

    def read(self, cell: EntityID) -> Any:
        """Return the current content of a cell in the active version."""

        self._active_cell(cell)

        return self._active._cells[cell]

    def write(self, cell: EntityID, content: Any) -> None:
        """Replace the content of a cell in the active version in place.

        The content is canonicalized, so later changes to the supplied object
        do not affect the cell. It must satisfy the cell's constraint; a
        rejected write leaves the cell unchanged. Program state and
        ``StateID`` are unchanged either way.
        """

        with _admission_scope(self._context, self._active.id, "write"):
            self._active_cell(cell)
            canonical = canonicalize(content)
            _check_content(
                cell,
                self._active._declarations[cell],
                canonical,
                self._context,
                "write",
            )

            staged = dict(self._active._cells)
            staged[cell] = canonical
            failure = _failed_constraint_relation(
                self._active.state,
                staged,
                self._context,
                touching=cell,
            )

            if failure is not None:
                raise RelationConstraintRejected(
                    *failure, f"write of {cell.value}"
                )

            self._active._cells[cell] = canonical

    def enter(self, entity: EntityID) -> Frame:
        """Start a simulated frame executing code of an entity."""

        if not self._active.state.contains(entity):
            raise KeyError(
                f"{entity.value} is absent from {self._active.id.value}"
            )

        return Frame(self._active, entity)

    def keep(self, reference: Reference) -> KeptReference:
        """Hold a reference in runtime state.

        The reference must resolve against a loaded version, which it then
        holds.
        """

        for version in self._versions:
            if version.id == reference.state:
                version.state.resolve(reference)
                return KeptReference(version, reference)

        raise CrossStateReference(
            f"reference belongs to {reference.state.value}, "
            f"which is not loaded in this runtime"
        )

    def activate(
        self,
        target: TransformResult | State,
        converters: Mapping[str, Converter] | None = None,
        *,
        reject_untransferable_references: bool = False,
    ) -> Version:
        """Activate the destination of a transformation result.

        A bare ``State`` has no transformation record, so every live entity
        has unknown continuity. Everything is staged before the switch; any
        rejection or failure leaves the runtime unchanged.
        """

        active = self._active
        result, available = self._prepare(target, converters)

        with _admission_scope(
            self._context, result.destination.id, "activate",
        ):
            if self.previous is not None:
                raise ActivationRejected(
                    "the previous version is still held"
                )

            contents = self._stage_cells(result, available, self._context)
            self._check_staged_relations(result, contents, self._context)
            references = self._stage_references(
                result,
                reject_untransferable_references,
            )

            new = Version(result.destination, contents)
            new._runtime = self
            listener = _LISTENER.get()

            if listener is not None:
                # Everything is staged and accepted; nothing has changed yet.
                listener.candidate(self, new, "activate")

            for kept, reference in references:
                kept._reference = reference
                kept._move(new)

            self._versions = [new, active]
            self._active = new
            self._history.append(result)
            self._retire_if_unused(active)

            return new

    def trial(
        self,
        target: TransformResult | State,
        converters: Mapping[str, Converter] | None = None,
        *,
        context: EvaluationContext | None = None,
    ) -> "Runtime":
        """Run a candidate in an isolated runtime (activation_model.md §8).

        Cell content is staged exactly as activation would stage it, with the
        same converters and checks, into a new runtime with its own root. A
        trial is rejected whenever the activation would be, for the same
        reason. This runtime is unchanged, and its two-version bound does
        not apply: the isolated runtime's version does not count against it.
        Runtime-held references and frames are not copied.

        The isolated runtime evaluates constraints in ``context``, which
        defaults to this runtime's context. Capabilities are not modelled
        yet; the context and the converters are what a trial grants.
        """

        result, available = self._prepare(target, converters)
        trial_context = context or self._context

        with _admission_scope(
            trial_context, result.destination.id, "trial",
        ):
            contents = self._stage_cells(result, available, trial_context)
            self._check_staged_relations(result, contents, trial_context)

            isolated = Runtime._isolated(
                result.destination,
                contents,
                trial_context,
            )
            listener = _LISTENER.get()

            if listener is not None:
                listener.candidate(self, isolated.active, "trial")

            return isolated

    def end_trial(self) -> None:
        """Tell the listener that the run of this trial, a runtime that
        ``trial`` returned, is over. Nothing else changes."""

        listener = _LISTENER.get()

        if listener is not None:
            listener.trial_ended(self, self._active)

    @classmethod
    def _isolated(
        cls,
        state: State,
        contents: Mapping[EntityID, Any],
        context: EvaluationContext,
    ) -> "Runtime":
        runtime = cls.__new__(cls)
        runtime._context = context
        runtime._active = Version(state, contents)
        runtime._active._runtime = runtime
        runtime._versions = [runtime._active]
        runtime._history = []

        return runtime

    def _prepare(
        self,
        target: TransformResult | State,
        converters: Mapping[str, Converter] | None,
    ) -> tuple[TransformResult, dict[str, Converter]]:
        if isinstance(target, State):
            result = TransformResult(
                source=self._active.state,
                destination=target,
                mappings=(),
            )
        elif isinstance(target, TransformResult):
            result = target
        else:
            raise TypeError(
                "expected a TransformResult or a State"
            )

        if result.source.id != self._active.id:
            result = self._rebased(result)

        available = dict(converters or {})

        for name, converter in available.items():
            if not isinstance(name, str) or not isinstance(
                converter,
                Converter,
            ):
                raise TypeError(
                    "converters must map names to Converter instances"
                )

        return result, available

    def _rebased(self, result: TransformResult) -> TransformResult:
        """``result``, built from a state this runtime had active earlier,
        rebased over every result activated since, in order.
        """

        starts = [past.source.id for past in self._history]

        if result.source.id not in starts:
            raise ActivationRejected(
                "transformation does not start from the active state"
            )

        index = len(starts) - 1 - starts[::-1].index(result.source.id)

        try:
            for past in self._history[index:]:
                result = rebase(result, past)
        except TransformationConflict as exc:
            raise ActivationConflict(str(exc)) from exc

        return result

    def _stage_cells(
        self,
        result: TransformResult,
        converters: Mapping[str, Converter],
        context: EvaluationContext,
    ) -> dict[EntityID, Any]:
        old = self._active
        declarations = cells_of(result.destination)
        incoming: dict[EntityID, list[EntityID]] = {
            cell: []
            for cell in declarations
        }

        for cell in old._declarations:
            mapping = result.mapping_for(cell)

            if mapping is None:
                raise ActivationRejected(
                    f"cell {cell.value} holds live content but has no "
                    f"declared continuity",
                    cell=cell,
                )

            for destination in mapping.destination_entities:
                if destination not in declarations:
                    raise ActivationRejected(
                        f"cell {cell.value} continues as "
                        f"{destination.value}, which is not a cell",
                        cell=cell,
                    )

                incoming[destination].append(cell)

        staged: dict[EntityID, Any] = {}

        for cell, declaration in declarations.items():
            sources = incoming[cell]
            name = result.conversion_for(cell)

            if name is not None:
                if not sources:
                    raise ActivationRejected(
                        f"conversion {name!r} for cell {cell.value} has "
                        f"no source cells",
                        cell=cell,
                    )

                converter = converters.get(name)

                if converter is None:
                    raise ActivationRejected(
                        f"no converter named {name!r} is available",
                        cell=cell,
                    )

                content = converter.convert({
                    source: old._cells[source]
                    for source in sources
                })
                origin = f"output of conversion {name!r}"
                hint = ""
            elif not sources:
                content = declaration.initial
                origin = "initial content"
                hint = ""
            elif (
                len(sources) == 1
                and result.mapping_for(sources[0]).destination_entities
                == (cell,)
            ):
                content = old._cells[sources[0]]
                origin = f"content transferred from {sources[0].value}"
                hint = "; a conversion is required"
            else:
                raise ActivationRejected(
                    f"cell {cell.value} receives a split or merge and "
                    f"needs a conversion",
                    cell=cell,
                )

            outcome = _evaluate_admission_constraint(
                declaration.constraint, content, context,
            )

            if outcome is not ConstraintResult.SATISFIED:
                raise ActivationRejected(
                    f"{origin} is {outcome.value} under the constraint of "
                    f"cell {cell.value}{hint}",
                    cell=cell,
                    result=outcome,
                )

            staged[cell] = content

        return staged

    def _check_staged_relations(
        self,
        result: TransformResult,
        contents: Mapping[EntityID, Any],
        context: EvaluationContext,
    ) -> None:
        failure = _failed_constraint_relation(
            result.destination,
            contents,
            context,
        )

        if failure is not None:
            relation, outcome = failure
            raise ActivationRejected(
                f"constraint relation {relation.value} is {outcome.value} "
                f"against the staged content",
                result=outcome,
                relation=relation,
            )

    def _stage_references(
        self,
        result: TransformResult,
        reject_untransferable: bool,
    ) -> list[tuple[KeptReference, Reference]]:
        staged = []

        for hold in self._active._holds:
            if not isinstance(hold, KeptReference):
                continue

            try:
                reference = transfer_reference(hold.reference, result)
            except (MissingEntityMapping, AmbiguousEntityMapping) as exc:
                if reject_untransferable:
                    raise ActivationRejected(
                        f"reference to {hold.reference.entity.value} "
                        f"cannot be transferred: {exc}"
                    ) from exc

                continue

            staged.append((hold, reference))

        return staged
