"""Authenticated restricted invocation of ordinary hosted SHEAR functions.

Deployments are host metadata, separate from canonical External identity. The
SHEAR compiler and existing machine provide every executable instruction;
this module only verifies authority, checks restrictions and connects named
External evaluators to the generic runner.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterator, Mapping
from weakref import WeakKeyDictionary

from .. import machine
from ..canonical import canonicalize
from ..constraints import ConstraintResult, EvaluationContext, Evaluator
from ..identity import EntityID, StateID, VersionID
from ..lang import _definition_of
from ..relations import relation_of
from ..runtime import Runtime
from ..state import State
from .artifacts import Artifact, ArtifactSet, TARGET
from .errors import AdmissionRejected
from .session import HostedSession
from .target import HostedTarget
from .trace import (
    ADMIT, ADMITTED_HOST, EXECUTE, HOST_ADMISSION, PRODUCE,
    SHEAR_COMPILER, Trace, TraceEvent,
)
from .restricted_policy import (
    RestrictionPolicy, _permit_instruction, preflight,
)
from .validation import validate_chunk


@dataclass(frozen=True, eq=False)
class RestrictedDeployment:
    """One separately compiled source with authenticated admitted artifacts.

    Only the creating executor may grant its authority to an invocation. The
    snapshot is detached from the mutable artifact-set mapping: replacement
    at the original lookup key cannot silently replace authenticated code.
    """

    source_state_id: StateID
    compiler_generation: int
    artifacts: Mapping[tuple[EntityID, VersionID], Artifact]
    _session: HostedSession = field(repr=False)
    _target: HostedTarget = field(repr=False)
    _artifact_set: ArtifactSet = field(repr=False)
    _owner: object = field(repr=False)


class _PinnedResolver:
    """Check the same admitted artifact and policy at each machine opening.

    The machine always asks for the frame's version. No invocation can
    silently fall back to lowering, to an unpinned version, or to a chunk
    changed between the preflight and machine execution.
    """

    def __init__(
        self,
        deployment: RestrictedDeployment,
        permitted: frozenset[tuple[EntityID, VersionID]],
        policy: RestrictionPolicy,
    ) -> None:
        self._deployment = deployment
        self._permitted = permitted
        self._policy = policy
        self._resolver = deployment._artifact_set.resolver()

    def __call__(self, state: State, entity: EntityID, owner: EntityID) -> tuple:
        raise AdmissionRejected("restricted execution requires a pinned version")

    def for_version(
        self, version: object, entity: EntityID, owner: EntityID,
    ) -> tuple:
        deployment = self._deployment
        if version is not deployment._target.runtime.active:
            raise AdmissionRejected("restricted invocation changed its version")
        if not deployment._artifact_set.valid:
            raise AdmissionRejected("restricted deployment was invalidated")
        value = version.state.values.get(entity)
        if value is None:
            raise AdmissionRejected("restricted code node is absent")
        key = (entity, value.version_id)
        if key not in self._permitted:
            raise AdmissionRejected("restricted call graph was not preflighted")
        expected = deployment.artifacts.get(key)
        if expected is None or expected.owner != owner:
            raise AdmissionRejected("restricted artifact owner mismatch")
        actual = deployment._artifact_set.get(*key)
        if actual is not expected:
            raise AdmissionRejected("restricted artifact admission was replaced")
        actual.verify()
        validate_chunk(version.state, entity, owner, actual.chunk)
        if any(
            not _permit_instruction(i[0], self._policy)
            for i in actual.chunk
        ):
            raise AdmissionRejected("restricted instruction is not permitted")
        return self._resolver(version.state, entity, owner)


class RestrictedExecutor:
    """Prepare, authenticate, and execute restricted hosted functions.

    Deployments are prepared in an independent runtime, before a constrained
    target runtime is constructed. This avoids circular initial admission.
    """

    def __init__(self) -> None:
        self._identity = object()
        self._trace = Trace()
        # The issuance record, not a field copied out of a descriptor, is
        # the authority to use its admitted artifacts. Weak keys avoid
        # retaining deployments after all legitimate owners release them.
        self._issued: WeakKeyDictionary[
            RestrictedDeployment,
            tuple[
                HostedSession,
                HostedTarget,
                ArtifactSet,
                Mapping[tuple[EntityID, VersionID], Artifact],
            ],
        ] = WeakKeyDictionary()

    @staticmethod
    def _validate_source(state: State) -> None:
        """Do not let graph-form normalization hide malformed link roles."""
        for entity, value in state.values.items():
            relation = relation_of(value)
            if relation is None:
                continue
            if relation.kind == "links":
                if not isinstance(relation.roles.get("function"), EntityID):
                    raise AdmissionRejected("malformed function role in links")
            if relation.kind == "definition":
                try:
                    definition = _definition_of(value)
                except (TypeError, ValueError, KeyError) as exc:
                    raise AdmissionRejected(
                        f"{entity.value}: malformed function definition"
                    ) from exc
                if definition is None or not isinstance(definition.body, EntityID):
                    raise AdmissionRejected("malformed definition body")
                if any(not isinstance(target, EntityID)
                       for target in definition.links.values()):
                    raise AdmissionRejected("malformed definition link role")

    @staticmethod
    def _authenticate(
        session: HostedSession, state: State, target: HostedTarget,
        generation: int,
    ) -> Mapping[tuple[EntityID, VersionID], Artifact]:
        """Require matching production AND admission events at the real key.

        Artifact.verify() is only an integrity check. Even a self-consistent
        rehash does not create the compiler-production or admission events
        which authorize a particular artifact in this target session.
        """
        produced = set()
        admitted = set()
        for event in session.trace():
            if event.target_state_id != state.id:
                continue
            if event.compiler_generation != generation:
                continue
            identity = (event.entity, event.version, event.artifact_id)
            if event.kind == PRODUCE and event.route == SHEAR_COMPILER:
                produced.add(identity)
            if event.kind == ADMIT and event.route == HOST_ADMISSION:
                admitted.add(identity)

        artifacts = dict(target.admitted(target.runtime.active))
        for (node, version), artifact in artifacts.items():
            if (
                artifact.domain != TARGET
                or artifact.state_id != state.id
                or artifact.entity != node
                or artifact.version != version
                or artifact.generation is not None
                or artifact.produced_by != generation
            ):
                raise AdmissionRejected("restricted artifact has wrong provenance")
            if state.values[node].version_id != version:
                raise AdmissionRejected("restricted artifact node version changed")
            identity = (node, version, artifact.artifact_id)
            if identity not in produced or identity not in admitted:
                raise AdmissionRejected("artifact lacks producer/admission evidence")
            artifact.verify()
            validate_chunk(state, node, artifact.owner, artifact.chunk)
            if state.owner_of(node) != artifact.owner:
                raise AdmissionRejected("restricted artifact owner differs")
            if artifact.reused_from is not None:
                raise AdmissionRejected("deployment cannot invent a reuse parent")
        return MappingProxyType(artifacts)

    def deploy(
        self, source: State, *, compiler_generation: int = 1,
    ) -> RestrictedDeployment:
        """Produce admitted evaluator code before constructing target state."""
        if not isinstance(source, State):
            raise TypeError("restricted deployment needs loaded State")
        if type(compiler_generation) is not int or compiler_generation < 1:
            raise ValueError("compiler generation must be positive")
        self._validate_source(source)
        runtime = Runtime(source)
        session = HostedSession(runtime)
        session.rebuild_through(compiler_generation)
        target = HostedTarget(
            runtime, session._chain, session._trace, compiler_generation,
        )
        try:
            target.prepare()
            authenticated = self._authenticate(
                session, source, target, compiler_generation,
            )
            deployment = RestrictedDeployment(
                source.id, compiler_generation, authenticated, session,
                target, target._artifacts, self._identity,
            )
            self._issued[deployment] = (
                session, target, target._artifacts, authenticated,
            )
            for event in session.trace():
                self._trace._events.append(event)
            return deployment
        except BaseException:
            for artifact_set in target._sets.values():
                artifact_set.invalidate()
            raise

    def _check_deployment(self, deployment: RestrictedDeployment) -> None:
        if not isinstance(deployment, RestrictedDeployment):
            raise AdmissionRejected("unknown restricted deployment")
        issued = self._issued.get(deployment)
        if issued is None or deployment._owner is not self._identity:
            raise AdmissionRejected("restricted deployment was not issued here")
        session, target, artifact_set, authenticated = issued
        if (
            deployment._session is not session
            or deployment._target is not target
            or deployment._artifact_set is not artifact_set
            or deployment.artifacts is not authenticated
            or target._artifacts is not artifact_set
            or target._sets.get(target.runtime.active) is not artifact_set
        ):
            raise AdmissionRejected("restricted deployment bindings were altered")
        if deployment.source_state_id != target.state.id:
            raise AdmissionRejected("restricted source identity changed")
        if deployment.compiler_generation != target.compiler_generation:
            raise AdmissionRejected("restricted compiler generation changed")
        if target.runtime.active.state.id != deployment.source_state_id:
            raise AdmissionRejected("restricted runtime changed state")
        if not artifact_set.valid:
            raise AdmissionRejected("restricted deployment was invalidated")
        chain = session._chain
        source_generation = chain._sets.get(deployment.compiler_generation)
        if source_generation is None or not source_generation.valid:
            raise AdmissionRejected("producing compiler generation is invalid")
        current = artifact_set.artifacts()
        if len(current) != len(authenticated):
            raise AdmissionRejected("restricted artifact set changed")
        for key, expected in authenticated.items():
            if current.get(key) is not expected:
                raise AdmissionRejected("restricted admitted artifact was replaced")
            expected.verify()

    def run(
        self, deployment: RestrictedDeployment, entry: EntityID,
        *args: Any, policy: RestrictionPolicy | None = None,
    ) -> Any:
        """Run normal SHEAR bytecode over a proven, pinned admitted view."""
        self._check_deployment(deployment)
        selected = policy if policy is not None else RestrictionPolicy()
        allowed = preflight(
            deployment._target.state, deployment.artifacts, entry, selected,
        )
        resolver = _PinnedResolver(deployment, allowed, selected)
        result = machine.run(
            deployment._target.runtime, entry,
            *(canonicalize(arg) for arg in args),
            resolver=resolver, may_activate=False,
        )
        definition = _definition_of(deployment._target.state.values[entry])
        root = definition.body
        key = (root, deployment._target.state.values[root].version_id)
        artifact = deployment.artifacts[key]
        self._trace.emit(
            EXECUTE, ADMITTED_HOST, entity=entry, version=artifact.version,
            artifact_id=artifact.artifact_id,
            compiler_generation=deployment.compiler_generation,
            target_state_id=deployment.source_state_id,
            detail="restricted invocation",
        )
        return result

    def invalidate(self, deployment: RestrictedDeployment) -> None:
        self._check_deployment(deployment)
        deployment._artifact_set.invalidate()

    def registry(
        self,
        bindings: Mapping[str, tuple[RestrictedDeployment, EntityID]],
        *, budget: int | None = None,
    ) -> RestrictedRegistry:
        return RestrictedRegistry(self, bindings, budget)

    def trace(self) -> tuple[TraceEvent, ...]:
        return self._trace.snapshot()


@dataclass(frozen=True)
class _OperationSelection:
    """Pinned host deployment selections for one target admission operation."""

    target_state_id: StateID
    operation: str
    bindings: Mapping[str, tuple[RestrictedDeployment, EntityID]]


class _RestrictedContext(EvaluationContext):
    """EvaluationContext with an optional generic runtime operation hook.

    The runtime calls operation_scope around each admission boundary. Neither
    its canonical state nor the underlying EvaluationContext contract changes.
    """

    def __init__(
        self, registry: RestrictedRegistry, externals: Mapping[str, Evaluator],
        budget: int | None,
    ) -> None:
        super().__init__(externals, budget=budget)
        object.__setattr__(self, "_registry", registry)

    def operation_scope(self, target_state_id: StateID, operation: str):
        return self._registry.operation_scope(target_state_id, operation)


class RestrictedRegistry:
    """Select named, independently deployed SHEAR evaluators.

    Replacement is atomic between operations. An operation's snapshot keeps
    every name pinned even if one of the machine invocations replaces the
    registry. Explicit invalidation still fails closed, rather than changing
    a pinned selection to the new implementation.
    """

    def __init__(
        self, executor: RestrictedExecutor,
        bindings: Mapping[str, tuple[RestrictedDeployment, EntityID]],
        budget: int | None,
    ) -> None:
        self._executor = executor
        self._bindings: dict[str, tuple[RestrictedDeployment, EntityID]] = {}
        self._operation: ContextVar[_OperationSelection | None] = ContextVar(
            "shear_restricted_evaluator_operation", default=None,
        )
        for name, binding in bindings.items():
            self._set(name, binding)
        evaluators = {
            name: Evaluator(
                lambda subject, name=name: self._evaluate(name, subject)
            )
            for name in self._bindings
        }
        self.context = _RestrictedContext(self, evaluators, budget=budget)

    def _set(
        self, name: str, binding: tuple[RestrictedDeployment, EntityID],
    ) -> None:
        if not isinstance(name, str) or not name:
            raise TypeError("external evaluator name must be non-empty")
        if not isinstance(binding, tuple) or len(binding) != 2:
            raise TypeError("evaluator selection requires deployment and entry")
        deployment, entry = binding
        self._executor._check_deployment(deployment)
        if not isinstance(entry, EntityID):
            raise TypeError("evaluator entry must be an EntityID")
        state = deployment._target.state
        value = state.values.get(entry)
        if value is None or _definition_of(value) is None:
            raise AdmissionRejected("evaluator entry is not a loaded function")
        self._bindings[name] = (deployment, entry)

    def replace(
        self, name: str, binding: tuple[RestrictedDeployment, EntityID],
    ) -> None:
        if name not in self._bindings:
            raise KeyError("cannot replace an unknown named evaluator")
        self._set(name, binding)

    @contextmanager
    def operation_scope(
        self, target_state_id: StateID, operation: str,
    ) -> Iterator[None]:
        """Pin all selected deployments before any constraint is checked."""
        if not isinstance(target_state_id, StateID):
            raise TypeError("operation target must be a StateID")
        if operation not in {"load", "write", "activate", "trial"}:
            raise ValueError("unknown restricted admission operation")
        snapshot = _OperationSelection(
            target_state_id, operation,
            MappingProxyType(dict(self._bindings)),
        )
        token = self._operation.set(snapshot)
        try:
            yield
        finally:
            self._operation.reset(token)

    def _evaluate(self, name: str, subject: Any) -> ConstraintResult:
        operation = self._operation.get()
        selected = self._bindings if operation is None else operation.bindings
        deployment, entry = selected[name]
        result = self._executor.run(
            deployment, entry, canonicalize(subject),
            policy=RestrictionPolicy(),
        )
        if operation is not None:
            source = deployment._target.state
            root = _definition_of(source.values[entry]).body
            artifact = deployment.artifacts[
                (root, source.values[root].version_id)
            ]
            self._executor._trace.emit(
                EXECUTE, ADMITTED_HOST,
                entity=entry,
                version=artifact.version,
                artifact_id=artifact.artifact_id,
                compiler_generation=deployment.compiler_generation,
                target_state_id=operation.target_state_id,
                detail=f"{operation.operation}: External({name})",
            )
        if type(result) is not str or result not in (
            "satisfied", "violated", "unknown",
        ):
            raise TypeError("invalid named constraint result")
        return ConstraintResult(result)
