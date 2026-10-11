"""One target program on the hosted route (docs/hosted_pipeline.md sections
6 and 7).

A ``HostedTarget`` binds a target runtime's active state to the artifacts the
SHEAR compiler produced for it. Each artifact is produced by an observed
compiler run, admitted against the pinned state, and only then executable:
``run`` gives the machine a resolver over the admitted set, so a node without
an admitted artifact fails closed instead of being lowered. Artifacts live
here, outside canonical state, and are bound to one state: when the runtime's
active state changes they are stale and the target must be prepared again
(conservative invalidation; nothing is inferred from a ``VersionID`` alone).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from .. import machine
from ..canonical import canonical_serialize, canonicalize
from ..identity import EntityID, VersionID
from ..lang import _definition_of
from ..runtime import Runtime
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


def _canonical(chunk: Any) -> bytes | None:
    try:
        return canonical_serialize(canonicalize(chunk))
    except (TypeError, ValueError):
        return None


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
        self._productions: dict[_Evidence, _Production] = {}

    # -- preparation ----------------------------------------------------------

    def executable_nodes(self) -> Iterator[tuple[EntityID, EntityID]]:
        """``(owner, node)`` for every code node of every function."""

        for owner in sorted(self.state.values, key=lambda e: e.value):
            if _definition_of(self.state.values[owner]) is None:
                continue

            for node in sorted(
                self.state.owned_subtree(owner) - {owner},
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

    def _owner_of(self, node: EntityID) -> EntityID:
        if node not in self.state.values:
            raise AdmissionRejected(f"{node.value} is not in the pinned state")

        owner = self.state.owner_of(node)

        if (
            owner is None
            or owner == node
            or _definition_of(self.state.values[owner]) is None
        ):
            raise AdmissionRejected(f"{node.value} is not owned code")

        return owner

    def produce(self, node: EntityID) -> tuple[tuple, object]:
        """Run the SHEAR compiler on ``node``: its chunk, and the evidence of
        that run, which ``admit`` requires."""

        owner = self._owner_of(node)
        chunk = self._chain.compile(
            describe(self.state, node, owner), self.compiler_generation,
        )
        version = self.state.values[node].version_id
        identity = artifact_id(
            TARGET, None, self.compiler_generation, self.state.id,
            node, version, owner, chunk,
        )
        evidence = _Evidence()
        self._productions[evidence] = _Production(
            node, version, owner, chunk, identity,
        )
        self._trace.emit(
            PRODUCE, SHEAR_COMPILER,
            entity=node, version=version, artifact_id=identity,
            compiler_generation=self.compiler_generation,
            target_state_id=self.state.id,
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

        try:
            production = self._productions[evidence]
        except (KeyError, TypeError):
            raise AdmissionRejected("unrecognized producer evidence") from None

        value = self.state.values.get(node)

        if (
            node != production.entity
            or version != production.version
            or value is None
            or value.version_id != version
        ):
            raise AdmissionRejected("wrong node or version for this evidence")

        submitted = _canonical(chunk)

        if submitted is None or submitted != _canonical(production.chunk):
            raise AdmissionRejected(
                "the chunk differs from the compiler's result"
            )

        validate_chunk(self.state, node, production.owner, production.chunk)
        artifact = Artifact(
            TARGET, self.state.id, node, version, production.owner,
            production.chunk, None, self.compiler_generation,
            production.artifact_id,
        )
        artifact.verify()
        self._artifacts.admit(artifact)
        self._trace.emit(
            ADMIT, HOST_ADMISSION,
            entity=node, version=version,
            artifact_id=artifact.artifact_id,
            compiler_generation=self.compiler_generation,
            target_state_id=self.state.id,
        )

        return artifact

    # -- execution -------------------------------------------------------------

    def run(
        self,
        entry: EntityID,
        *args: Any,
        may_activate: bool = False,
    ) -> Any:
        """Run ``entry`` on the host machine over admitted artifacts only."""

        active = self.runtime.active.state

        if active is not self.state and active.id != self.state.id:
            raise AdmissionRejected(
                "the runtime's active state changed; prepare again"
            )

        return machine.run(
            self.runtime,
            entry,
            *args,
            may_activate=may_activate,
            resolver=self._artifacts.resolver(),
        )

    def _first_use(self, artifact: Artifact) -> None:
        self._trace.emit(
            EXECUTE, ADMITTED_HOST,
            entity=artifact.entity, version=artifact.version,
            artifact_id=artifact.artifact_id,
            compiler_generation=artifact.produced_by,
            target_state_id=self.state.id,
        )
