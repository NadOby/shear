"""Provenance events of the hosted pipeline.

The trace is the pipeline's account of what it did: every host lowering of a
declared seed node, every artifact a SHEAR compiler produced, every admission,
and the first execution of every admitted artifact. Events are recorded at the
boundary that acts, never reconstructed afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..identity import EntityID, StateID, VersionID

# Event kinds.
HOST_LOWER = "host-lower"  # a declared seed node lowered by the host
PRODUCE = "produce"  # a chunk returned by an observed SHEAR compiler run
ADMIT = "admit"  # a produced chunk admitted
REJECT = "reject"  # a node the pipeline does not compile
EXECUTE = "execute"  # first run of an admitted program-code artifact
COMPILER_EXECUTE = "compiler-execute"  # first run of an admitted compiler one

# Routes: which boundary acted.
DECLARED_SEED = "declared-seed"
SHEAR_COMPILER = "shear-compiler"
HOST_ADMISSION = "host-admission"
ADMITTED_HOST = "admitted-host"
ADMITTED_COMPILER = "admitted-compiler"


@dataclass(frozen=True)
class TraceEvent:
    kind: str
    route: str
    entity: EntityID | None = None
    version: VersionID | None = None
    artifact_id: str | None = None
    generation: int | None = None
    """For a compiler artifact: its own generation (0 is the seed)."""
    compiler_generation: int | None = None
    """The generation of the SHEAR compiler that produced the artifact."""
    target_state_id: StateID | None = None
    detail: str = ""

    def as_json(self) -> dict[str, Any]:
        def text(value: Any) -> Any:
            return None if value is None else value.value

        return {
            "kind": self.kind,
            "route": self.route,
            "entity": text(self.entity),
            "version": text(self.version),
            "artifact_id": self.artifact_id,
            "generation": self.generation,
            "compiler_generation": self.compiler_generation,
            "target_state_id": text(self.target_state_id),
            "detail": self.detail,
        }


class Trace:
    """An append-only record shared by one session's components."""

    def __init__(self) -> None:
        self._events: list[TraceEvent] = []

    def emit(self, kind: str, route: str, **fields: Any) -> None:
        self._events.append(TraceEvent(kind, route, **fields))

    def snapshot(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events)
