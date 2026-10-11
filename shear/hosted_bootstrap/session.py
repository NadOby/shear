"""The hosted pipeline's public boundary (docs/hosted_pipeline.md).

A ``HostedSession`` joins one target runtime to the pinned SHEAR compiler:

* ``compiler_source_state`` and ``seed_manifest`` name the compiler and its
  generation-0 seed; neither depends on the target.
* ``rebuild_through`` builds compiler generations; ``compiler_artifacts``
  exposes the admitted chunks the machine consumes.
* ``prepare`` has the SHEAR compiler produce and admit an artifact for every
  node of the target's active state; ``run`` executes only those.
* ``stage_edit`` prepares an edited candidate beside the original without
  activating it.

Nothing here defines or activates a state, and host lowering is reachable
only through the declared seed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..identity import EntityID, StateID, VersionID
from ..lang import _definition_of
from ..reconcile import reconcile
from ..runtime import Runtime
from ..state import State
from .artifacts import Artifact
from .errors import AdmissionRejected
from .generations import CompilerChain, GenerationReport
from .seed import SeedManifest, compiler_source_state, verified_manifest
from .target import HostedTarget
from .trace import Trace, TraceEvent


@dataclass(frozen=True)
class StagedEdit:
    """The result of running an edited program beside its original."""

    result: Any
    candidate_result: Any
    base_state_id: StateID
    candidate_state_id: StateID
    active_state_id: StateID
    continuity: Mapping[str, Mapping[str, str]]


def continuity_of(base: State, candidate: State) -> dict[str, dict[str, str]]:
    """For every function in both states: the body node and version it had
    and the ones it has."""

    found: dict[str, dict[str, str]] = {}

    for entity, value in base.values.items():
        old = _definition_of(value)
        new_value = candidate.values.get(entity)
        new = None if new_value is None else _definition_of(new_value)

        if old is None or new is None:
            continue

        found[entity.value] = {
            "entity": entity.value,
            "original_body": old.body.value,
            "candidate_body": new.body.value,
            "original_version": base.values[old.body].version_id.value,
            "candidate_version": candidate.values[new.body].version_id.value,
        }

    return found


class HostedSession:
    def __init__(self, target_runtime: Runtime) -> None:
        self.target_runtime = target_runtime
        self.compiler_source_state = compiler_source_state()
        self.seed_manifest: SeedManifest = verified_manifest()
        self._trace = Trace()
        self._chain = CompilerChain(
            self.compiler_source_state, self.seed_manifest, self._trace,
        )
        self._target: HostedTarget | None = None

    # -- the compiler ---------------------------------------------------------

    def rebuild_through(self, generation: int) -> tuple[GenerationReport, ...]:
        return self._chain.rebuild_through(generation)

    def compiler_artifacts(
        self,
        generation: int,
    ) -> Mapping[tuple[EntityID, VersionID], tuple]:
        return self._chain.artifacts(generation)

    def invalidate_compiler_generation(self, generation: int) -> None:
        self._chain.invalidate(generation)

    def attempt_seed_lower(self, node: EntityID) -> tuple:
        """Diagnostic: host lowering of ``node``, which only a declared seed
        node of the compiler source survives."""

        return self._chain.seed_lower(node)

    # -- the target -----------------------------------------------------------

    def prepare(self, compiler_generation: int = 1) -> None:
        """Compile and admit the target's active state with the SHEAR
        compiler of ``compiler_generation``, replacing earlier artifacts."""

        if compiler_generation < 1:
            raise ValueError("a target is compiled by generation 1 or later")

        self._chain.rebuild_through(compiler_generation)
        target = self._prepared(self.target_runtime, compiler_generation)
        self._target = target

    def _prepared(self, runtime: Runtime, generation: int) -> HostedTarget:
        target = HostedTarget(runtime, self._chain, self._trace, generation)
        target.prepare()
        return target

    def _bound(self) -> HostedTarget:
        if self._target is None:
            raise AdmissionRejected("no target is prepared")

        return self._target

    def produce(self, node: EntityID) -> tuple[tuple, object]:
        return self._bound().produce(node)

    def admit(
        self,
        node: EntityID,
        version: VersionID,
        chunk: tuple,
        evidence: object,
    ) -> Artifact:
        return self._bound().admit(node, version, chunk, evidence)

    def run(
        self,
        entry: EntityID,
        *args: Any,
        may_activate: bool = False,
    ) -> Any:
        return self._bound().run(entry, *args, may_activate=may_activate)

    def trace(self) -> tuple[TraceEvent, ...]:
        return self._trace.snapshot()

    # -- staging an edit ------------------------------------------------------

    def stage_edit(
        self,
        edited_source: str,
        entry: EntityID,
        args: tuple,
        compiler_generation: int = 1,
    ) -> StagedEdit:
        """Run ``entry`` on the original, reconcile ``edited_source`` against
        it, and run ``entry`` on the candidate: a host-orchestrated diagnostic
        run on a separate runtime. The original runtime keeps its active state
        and nothing is activated."""

        if self._target is None:
            self.prepare(compiler_generation)

        original = self._bound()
        base = original.state
        result = original.run(entry, *args)

        candidate_state = reconcile(base, edited_source).destination
        candidate = self._prepared(
            Runtime(candidate_state, self.target_runtime.context),
            compiler_generation,
        )
        candidate_result = candidate.run(entry, *args)

        return StagedEdit(
            result,
            candidate_result,
            base.id,
            candidate_state.id,
            self.target_runtime.active.state.id,
            continuity_of(base, candidate_state),
        )
