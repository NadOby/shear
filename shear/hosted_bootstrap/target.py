"""One target program on the hosted route (docs/hosted_pipeline.md sections
6 and 7; docs/live_evolution.md sections 3 and 4).

A ``HostedTarget`` binds a target runtime's versions to the artifacts the
SHEAR compiler produced for them. Each artifact is produced by an observed
compiler run, admitted against its pinned state, and only then executable:
``run`` gives the machine a resolver over the admitted sets, so a node without
an admitted artifact fails closed instead of being lowered. Artifacts live
here, outside canonical state.

An artifact set belongs to a version of the target runtime, or to the version
of a running trial, never to a ``StateID``: two owners can have one state. The
target is prepared once, for the runtime's active version. After that, a
candidate built by a running program is compiled when the program runs
``activate`` or ``trial`` (D5.1): the runtime reports the staged candidate to
the target, which admits every code node of it, reusing the active version's
artifacts where it may, before the switch or the trial run. A candidate that
cannot be admitted changes nothing and raises ``AdmissionRejected`` (D5.2). A
set is released when its version retires or its trial ends. A host-API
activation outside a run is not reported: the new version has no set, and the
target must be prepared again.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Mapping

from .. import machine
from ..canonical import canonical_serialize, canonicalize
from ..identity import EntityID, StateID, VersionID
from ..lang import _definition_of
from ..runtime import Runtime, Version, listening
from ..state import State
from .artifacts import TARGET, Artifact, ArtifactSet, artifact_id
from .descriptors import describe
from .errors import AdmissionRejected, UnsupportedOperation
from .generations import CompilerChain
from .trace import (
    ADMIT,
    ADMITTED_HOST,
    EXECUTE,
    HOST_ADMISSION,
    PRODUCE,
    REJECT,
    RELEASE,
    REUSE,
    SHEAR_COMPILER,
    Trace,
)
from .validation import validate_chunk


class _Evidence:
    """An opaque handle for one observed compiler run.

    It carries nothing: what it authorizes is held by the target that issued
    it, so no value built by a caller can stand in for one.
    """

    __slots__ = ()


@dataclass(frozen=True)
class _Production:
    entity: EntityID
    version: VersionID
    owner: EntityID
    chunk: tuple
    artifact_id: str
    state_id: StateID | None = None


def _canonical(chunk: Any) -> bytes | None:
    try:
        return canonical_serialize(canonicalize(chunk))
    except (TypeError, ValueError):
        return None


class _Resolver:
    """The chunk source of a target's runs: the frame's own version decides
    which artifact set answers (two loaded versions can have one state)."""

    def __init__(self, target: "HostedTarget") -> None:
        self._target = target

    def __call__(self, state: Any, entity: EntityID, owner: EntityID) -> tuple:
        raise AdmissionRejected(
            f"{entity.value}: a chunk was requested without its version"
        )

    def for_version(
        self,
        version: Version,
        entity: EntityID,
        owner: EntityID,
    ) -> tuple:
        found = self._target._sets.get(version)

        if found is None:
            raise AdmissionRejected(
                f"no artifacts for the version {entity.value} is run in"
            )

        return found.resolver()(version.state, entity, owner)


class HostedTarget:
    def __init__(
        self,
        runtime: Runtime,
        chain: CompilerChain,
        trace: Trace,
        compiler_generation: int,
    ) -> None:
        self.runtime = runtime
        self.state = runtime.active.state
        self.compiler_generation = compiler_generation
        self._chain = chain
        self._trace = trace
        self._artifacts = ArtifactSet(self.state, self._first_use)
        """The set of the version the target was prepared for."""
        self._sets: dict[Version, ArtifactSet] = {
            runtime.active: self._artifacts,
        }
        self._productions: dict[_Evidence, _Production] = {}
        self._resolver = _Resolver(self)

    # -- preparation ----------------------------------------------------------

    def executable_nodes(self) -> Iterator[tuple[EntityID, EntityID]]:
        """``(owner, node)`` for every code node of every function."""

        return self._nodes_of(self.state)

    @staticmethod
    def _nodes_of(state: State) -> Iterator[tuple[EntityID, EntityID]]:
        for owner in sorted(state.values, key=lambda e: e.value):
            if _definition_of(state.values[owner]) is None:
                continue

            for node in sorted(
                state.owned_subtree(owner) - {owner},
                key=lambda e: e.value,
            ):
                yield owner, node

    def prepare(self) -> None:
        """Produce and admit an artifact for every node the SHEAR compiler
        lowers. A node it does not lower is recorded and left without one."""

        for owner, node in self.executable_nodes():
            try:
                chunk, evidence = self.produce(node)
            except UnsupportedOperation as exc:
                self._trace.emit(
                    REJECT, HOST_ADMISSION,
                    entity=node,
                    version=self.state.values[node].version_id,
                    target_state_id=self.state.id,
                    detail=str(exc),
                )
                continue

            self.admit(
                node, self.state.values[node].version_id, chunk, evidence,
            )

    # -- production and admission ----------------------------------------------

    def _owner_of(self, state: State, node: EntityID) -> EntityID:
        if node not in state.values:
            raise AdmissionRejected(f"{node.value} is not in the pinned state")

        owner = state.owner_of(node)

        if owner is None or _definition_of(state.values[owner]) is None:
            raise AdmissionRejected(f"{node.value} is not owned code")

        return owner

    def produce(self, node: EntityID) -> tuple[tuple, object]:
        """Run the SHEAR compiler on ``node``: its chunk, and the evidence of
        that run, which ``admit`` requires."""

        return self._produce(self.state, node)

    def _produce(self, state: State, node: EntityID) -> tuple[tuple, object]:
        owner = self._owner_of(state, node)
        chunk = self._chain.compile(
            describe(state, node, owner), self.compiler_generation,
        )
        version = state.values[node].version_id
        identity = artifact_id(
            TARGET, None, self.compiler_generation, state.id,
            node, version, owner, chunk,
        )
        evidence = _Evidence()
        self._productions[evidence] = _Production(
            node, version, owner, chunk, identity, state.id,
        )
        self._trace.emit(
            PRODUCE, SHEAR_COMPILER,
            entity=node, version=version, artifact_id=identity,
            compiler_generation=self.compiler_generation,
            target_state_id=state.id,
        )

        return chunk, evidence

    def admit(
        self,
        node: EntityID,
        version: VersionID,
        chunk: tuple,
        evidence: object,
    ) -> Artifact:
        """Admit ``chunk`` for ``node`` at ``version`` if ``evidence`` is the
        handle of the compiler run that returned exactly this chunk for this
        node and version, and the chunk is well formed."""

        return self._admit(
            self.state, self._artifacts, node, version, chunk, evidence,
        )

    def _admit(
        self,
        state: State,
        artifacts: ArtifactSet,
        node: EntityID,
        version: VersionID,
        chunk: tuple,
        evidence: object,
    ) -> Artifact:
        try:
            production = self._productions[evidence]
        except (KeyError, TypeError):
            raise AdmissionRejected("unrecognized producer evidence") from None

        value = state.values.get(node)

        if (
            node != production.entity
            or version != production.version
            or value is None
            or value.version_id != version
            or production.state_id not in (None, state.id)
        ):
            raise AdmissionRejected("wrong node or version for this evidence")

        submitted = _canonical(chunk)

        if submitted is None or submitted != _canonical(production.chunk):
            raise AdmissionRejected(
                "the chunk differs from the compiler's result"
            )

        validate_chunk(state, node, production.owner, production.chunk)
        artifact = Artifact(
            TARGET, state.id, node, version, production.owner,
            production.chunk, None, self.compiler_generation,
            production.artifact_id,
        )
        artifact.verify()
        artifacts.admit(artifact)
        self._trace.emit(
            ADMIT, HOST_ADMISSION,
            entity=node, version=version,
            artifact_id=artifact.artifact_id,
            compiler_generation=self.compiler_generation,
            target_state_id=state.id,
        )

        return artifact

    # -- candidates (live_evolution.md sections 3 and 4) -----------------------

    def candidate(self, runtime: Runtime, version: Version, how: str) -> None:
        """The runtime reports a staged, accepted candidate (a
        ``VersionListener`` callback). Admit every one of its code nodes, or
        raise and leave nothing behind: no artifact set, record or version."""

        if runtime is not self.runtime:
            raise AdmissionRejected(
                f"a {how} of a runtime this target does not hold"
            )

        state = version.state
        artifacts = ArtifactSet(state, self._first_use)
        done = False

        try:
            self._compile_candidate(
                state, artifacts, self._sets.get(runtime.active),
            )
            done = True
        except AdmissionRejected as exc:
            self._trace.emit(
                REJECT, HOST_ADMISSION,
                target_state_id=state.id,
                detail=f"{how}: {exc}",
            )
            raise
        finally:
            if not done:
                artifacts.invalidate()

        self._sets[version] = artifacts

    def _compile_candidate(
        self,
        state: State,
        artifacts: ArtifactSet,
        source: ArtifactSet | None,
    ) -> None:
        """Admit each code node of ``state``: reuse the artifact of the active
        version's set where the rule allows it (section 4.3), compile it
        otherwise."""

        for owner, node in self._nodes_of(state):
            version = state.values[node].version_id
            reused = None if source is None else source.get(node, version)

            if reused is not None and self._reuse(
                state, artifacts, node, version, owner, reused,
            ):
                continue

            chunk, evidence = self._produce(state, node)

            try:
                self._admit(state, artifacts, node, version, chunk, evidence)
            finally:
                del self._productions[evidence]

    def _reuse(
        self,
        state: State,
        artifacts: ArtifactSet,
        node: EntityID,
        version: VersionID,
        owner: EntityID,
        source: Artifact,
    ) -> bool:
        """Admit ``source``'s chunk for ``node`` in ``state`` if the reuse
        rule holds. The node already has the same ``EntityID`` and
        ``VersionID`` in both states (rule 1, by the lookup)."""

        source.verify()

        if (
            source.owner != owner  # rule 2: the same owner
            or source.produced_by != self.compiler_generation  # rule 3
        ):
            return False

        try:
            validate_chunk(state, node, owner, source.chunk)  # rule 4
        except AdmissionRejected:
            return False

        artifact = Artifact(
            TARGET, state.id, node, version, owner, source.chunk,
            None, source.produced_by,
            artifact_id(
                TARGET, None, source.produced_by, state.id,
                node, version, owner, source.chunk, source.artifact_id,
            ),
            source.artifact_id,
        )
        artifact.verify()
        artifacts.admit(artifact)
        self._trace.emit(
            REUSE, HOST_ADMISSION,
            entity=node, version=version,
            artifact_id=artifact.artifact_id,
            source_artifact_id=source.artifact_id,
            compiler_generation=source.produced_by,
            target_state_id=state.id,
        )

        return True

    # -- lifetime ---------------------------------------------------------------

    def retired(self, runtime: Runtime, version: Version) -> None:
        """A version left the runtime's loaded versions (a
        ``VersionListener`` callback): its set is released."""

        self._release(version, "retired")

    def trial_ended(self, runtime: Runtime, version: Version) -> None:
        """A trial's run is over, whether it returned or failed (a
        ``VersionListener`` callback): its set is released."""

        self._release(version, "trial")

    def _release(self, version: Version, why: str) -> None:
        found = self._sets.pop(version, None)

        if found is None:
            return

        state_id = found.state.id
        found.invalidate()
        self._trace.emit(
            RELEASE, HOST_ADMISSION, target_state_id=state_id, detail=why,
        )

    def retained_versions(self) -> frozenset[Version]:
        """The versions that own an artifact set. A version that retired
        outside a run, through a host-API hold, is released first."""

        for version in [v for v in self._sets if v.retired]:
            self._release(version, "retired")

        return frozenset(self._sets)

    def admitted(self, version: Version) -> Mapping[
        tuple[EntityID, VersionID], Artifact
    ]:
        """A read-only view of the artifacts the set that ``version`` owns
        holds, keyed by node and version."""

        found = self._sets.get(version)

        if found is None:
            raise AdmissionRejected("this version owns no artifact set")

        return found.artifacts()

    # -- execution -------------------------------------------------------------

    def run(
        self,
        entry: EntityID,
        *args: Any,
        may_activate: bool = False,
    ) -> Any:
        """Run ``entry`` on the host machine over admitted artifacts only."""

        if self.runtime.active not in self._sets:
            raise AdmissionRejected(
                "the runtime's active state changed; prepare again"
            )

        with listening(self):
            return machine.run(
                self.runtime,
                entry,
                *args,
                may_activate=may_activate,
                resolver=self._resolver,
            )

    def _first_use(self, artifact: Artifact) -> None:
        self._trace.emit(
            EXECUTE, ADMITTED_HOST,
            entity=artifact.entity, version=artifact.version,
            artifact_id=artifact.artifact_id,
            compiler_generation=artifact.produced_by,
            target_state_id=artifact.state_id,
        )
