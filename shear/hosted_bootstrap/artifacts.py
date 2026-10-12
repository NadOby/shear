"""Admitted executable artifacts, kept outside canonical state
(docs/hosted_pipeline.md sections 6 and 7).

An ``Artifact`` is a chunk bound to the node and version it executes, the
pinned state and owner it belongs to, and the compiler generation that
produced it. An ``ArtifactSet`` holds the admitted artifacts of one pinned
state and is the only source of chunks for a run that uses it: ``resolver``
gives the machine a function that returns an admitted chunk or fails closed.

A set is owned by a version (or by a running trial), not by its state: see
``HostedTarget`` and docs/live_evolution.md section 4.1.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import Any, Callable, Mapping

from ..canonical import canonical_serialize, canonicalize
from ..identity import EntityID, StateID, VersionID
from ..machine import ChunkResolver
from ..state import State
from .errors import AdmissionRejected

COMPILER = "compiler"
TARGET = "target"


def artifact_id(
    domain: str,
    generation: int | None,
    produced_by: int | None,
    state_id: StateID,
    entity: EntityID,
    version: VersionID,
    owner: EntityID,
    chunk: tuple,
    reused_from: str | None = None,
) -> str:
    """Content-derived identity; it binds every field that authorizes use,
    and, for an artifact admitted by reuse, the artifact it reuses."""

    content = (
        "artifact", domain, generation, produced_by,
        state_id, entity, version, owner, chunk,
    )

    if reused_from is not None:
        content += (reused_from,)

    return sha256(
        canonical_serialize(canonicalize(content))
    ).hexdigest()


@dataclass(frozen=True)
class Artifact:
    domain: str
    """``COMPILER`` (a node of the pinned compiler source) or ``TARGET``."""
    state_id: StateID
    entity: EntityID
    version: VersionID
    owner: EntityID
    chunk: tuple
    generation: int | None
    """A compiler artifact's own generation; 0 is the declared seed."""
    produced_by: int | None
    """The generation of the SHEAR compiler that produced it; None for the
    seed, which the host lowered."""
    artifact_id: str
    reused_from: str | None = None
    """For an artifact admitted by reuse (live_evolution.md section 4.3): the
    id of the artifact of the active version whose chunk it shares. Two
    admissions for one state then differ, so a reuse is never its own
    source."""

    def verify(self) -> None:
        recomputed = artifact_id(
            self.domain, self.generation, self.produced_by, self.state_id,
            self.entity, self.version, self.owner, self.chunk,
            self.reused_from,
        )

        if recomputed != self.artifact_id:
            raise AdmissionRejected(
                f"{self.entity.value}: artifact integrity check failed"
            )


class ArtifactSet:
    """The admitted artifacts of one pinned state."""

    def __init__(
        self,
        state: State,
        first_use: Callable[[Artifact], None],
    ) -> None:
        """``first_use`` is called once for each artifact, after its
        integrity check, when a run first asks for it."""

        self.state = state
        self._first_use = first_use
        self._verified: set[str] = set()
        self._resolve = self._make_resolver()
        self._artifacts: dict[tuple[EntityID, VersionID], Artifact] = {}
        self._chunks: dict[tuple[EntityID, VersionID], tuple] = {}
        self._valid = True

    @property
    def valid(self) -> bool:
        return self._valid

    def admit(self, artifact: Artifact) -> None:
        if not self._valid:
            raise AdmissionRejected("this artifact set was invalidated")

        key = (artifact.entity, artifact.version)
        self._artifacts[key] = artifact
        self._chunks[key] = artifact.chunk

    def invalidate(self) -> None:
        """Drop every artifact; none can be used or re-admitted."""

        self._valid = False
        self._artifacts.clear()
        self._chunks.clear()

    def get(self, entity: EntityID, version: VersionID) -> Artifact | None:
        """The artifact admitted for this node at this version, if any."""

        return self._artifacts.get((entity, version))

    def artifacts(self) -> Mapping[tuple[EntityID, VersionID], Artifact]:
        """A read-only view of the admitted artifacts."""

        return MappingProxyType(self._artifacts)

    def chunks(self) -> Mapping[tuple[EntityID, VersionID], tuple]:
        """Read-only bindings to the exact admitted chunk objects."""

        return MappingProxyType(self._chunks)

    def artifact_ids(self) -> tuple[str, ...]:
        return tuple(a.artifact_id for a in self._artifacts.values())

    def resolver(self) -> ChunkResolver:
        """A chunk source for ``machine.run``: admitted chunks only."""

        return self._resolve

    def _make_resolver(self) -> ChunkResolver:
        def resolve(state: Any, entity: EntityID, owner: EntityID) -> tuple:
            if not self._valid:
                raise AdmissionRejected("the artifact set was invalidated")

            if state is not self.state and state.id != self.state.id:
                raise AdmissionRejected(
                    f"stale artifacts: {entity.value} is requested from a "
                    "state they were not admitted for"
                )

            value = state.values.get(entity)
            artifact = (
                None
                if value is None
                else self._artifacts.get((entity, value.version_id))
            )

            if artifact is None or artifact.owner != owner:
                raise AdmissionRejected(
                    f"no admitted artifact for {entity.value} of "
                    f"{owner.value}"
                )

            if artifact.artifact_id not in self._verified:
                artifact.verify()
                self._verified.add(artifact.artifact_id)
                self._first_use(artifact)

            return artifact.chunk

        return resolve
