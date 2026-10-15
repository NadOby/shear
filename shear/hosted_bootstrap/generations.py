"""The compiler generations G0 to Gn (docs/hosted_pipeline.md section 5).

All generations compile the same pinned compiler source. G0 is the declared
seed, lowered by the host. Generation n >= 1 is produced by running
``compile_node`` on the host machine over the admitted artifacts of generation
n-1 only: the machine is given generation n-1's chunks and nothing else, so a
missing, invalidated or substituted predecessor fails closed instead of being
rescued by lowering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .. import machine
from ..examples.compiler_source import COMPILE_NODE
from ..identity import EntityID, StateID, VersionID
from ..lang import LanguageError
from ..runtime import Runtime, listening
from ..state import State
from .artifacts import COMPILER, Artifact, ArtifactSet, artifact_id
from .descriptors import Descriptor, decode_chunk, describe
from .errors import AdmissionRejected
from .seed import SeedGate, SeedManifest
from .trace import (
    ADMIT,
    ADMITTED_COMPILER,
    COMPILER_EXECUTE,
    HOST_ADMISSION,
    PRODUCE,
    SHEAR_COMPILER,
    Trace,
)
from .validation import validate_chunk


@dataclass(frozen=True)
class GenerationReport:
    generation: int
    producer_generation: int
    compiler_source_state_id: StateID
    artifact_ids: tuple[str, ...]


class CompilerChain:
    """The pinned compiler source, its runtime and its generations."""

    def __init__(
        self,
        state: State,
        manifest: SeedManifest,
        trace: Trace,
    ) -> None:
        self.state = state
        self.manifest = manifest
        self._trace = trace
        self._runtime = Runtime(state)
        self._gate = SeedGate(state, manifest, trace)
        self._sets: dict[int, ArtifactSet] = {}
        self._reports: list[GenerationReport] = []

    # -- seed ---------------------------------------------------------------

    def seed_lower(self, entity: EntityID) -> tuple:
        """Host-lower ``entity`` if, and only if, it is a declared seed node."""

        return self._gate.lower(entity)[1]

    def _ensure_seed(self) -> None:
        if 0 in self._sets:
            return

        artifacts = ArtifactSet(self.state, self._first_use)

        for node in self.manifest.code_nodes:
            _, chunk = self._gate.lower(node.entity)
            artifacts.admit(self._artifact(
                node.entity, node.version, node.owner, chunk, 0, None,
            ))

        self._sets[0] = artifacts

    # -- generations --------------------------------------------------------

    def rebuild_through(self, generation: int) -> tuple[GenerationReport, ...]:
        """Build the missing generations up to ``generation``; report 1..n."""

        self._ensure_seed()

        for number in range(1, generation + 1):
            existing = self._sets.get(number)

            if existing is None:
                self._build(number)
            elif not existing.valid:
                raise AdmissionRejected(
                    f"generation {number} was invalidated"
                )

        return tuple(self._reports[:generation])

    def artifacts(
        self,
        generation: int,
    ) -> Mapping[tuple[EntityID, VersionID], tuple]:
        """Read-only bindings to generation's actual admitted chunks."""

        found = self._sets.get(generation)

        if found is None:
            raise AdmissionRejected(f"generation {generation} is not built")

        return found.chunks()

    def invalidate(self, generation: int) -> None:
        found = self._sets.get(generation)

        if found is not None:
            found.invalidate()

    def _artifact(
        self,
        entity: EntityID,
        version: VersionID,
        owner: EntityID,
        chunk: tuple,
        generation: int,
        produced_by: int | None,
    ) -> Artifact:
        validate_chunk(self.state, entity, owner, chunk)

        return Artifact(
            COMPILER, self.state.id, entity, version, owner, chunk,
            generation, produced_by,
            artifact_id(
                COMPILER, generation, produced_by, self.state.id,
                entity, version, owner, chunk,
            ),
        )

    def _build(self, generation: int) -> None:
        producer = generation - 1
        artifacts = ArtifactSet(self.state, self._first_use)

        for node in self.manifest.code_nodes:
            chunk = self.compile(
                describe(self.state, node.entity, node.owner), producer,
            )
            artifact = self._artifact(
                node.entity, node.version, node.owner, chunk,
                generation, producer,
            )
            self._trace.emit(
                PRODUCE, SHEAR_COMPILER,
                entity=node.entity, version=node.version,
                artifact_id=artifact.artifact_id,
                generation=generation, compiler_generation=producer,
            )
            artifacts.admit(artifact)
            self._trace.emit(
                ADMIT, HOST_ADMISSION,
                entity=node.entity, version=node.version,
                artifact_id=artifact.artifact_id,
                generation=generation, compiler_generation=producer,
            )

        self._sets[generation] = artifacts
        self._reports.append(GenerationReport(
            generation, producer, self.state.id, artifacts.artifact_ids(),
        ))

    # -- running the compiler -----------------------------------------------

    def compile(self, descriptor: Descriptor, generation: int) -> tuple:
        """One observed run of ``compile_node`` under ``generation``'s
        admitted artifacts; the chunk it returned, decoded."""

        self._ensure_seed()
        artifacts = self._sets.get(generation)

        if artifacts is None or not artifacts.valid:
            raise AdmissionRejected(
                f"compiler generation {generation} is not available"
            )

        before = self._runtime.active.state

        try:
            # The compiler's runtime is its own: a run that happens inside a
            # target's activation does not report to the target's listener.
            with listening(None):
                returned = machine.run(
                    self._runtime,
                    COMPILE_NODE,
                    descriptor.value,
                    resolver=artifacts.resolver(),
                )
        except LanguageError as exc:
            raise AdmissionRejected(
                f"the SHEAR compiler failed: {exc}"
            ) from exc

        if self._runtime.active.state is not before:
            raise AdmissionRejected("the compiler run changed its source")

        return decode_chunk(returned)

    def _first_use(self, artifact: Artifact) -> None:
        self._trace.emit(
            COMPILER_EXECUTE, ADMITTED_COMPILER,
            entity=artifact.entity, version=artifact.version,
            artifact_id=artifact.artifact_id,
            generation=artifact.generation,
        )
