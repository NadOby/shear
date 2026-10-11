"""The generation-0 seed: the finite set of compiler nodes the host lowers
(docs/hosted_pipeline.md section 4).

The seed is derived from the pinned compiler source alone: the code owned by
the root compiler functions and by every compiler function their links
transitively name. ``manifest.json`` records that set, node by node, and is
checked in so that reviewing a change to the compiler source includes
reviewing a change to the seed. A session verifies the manifest against the
source before any lowering and refuses to run on a mismatch; the manifest
never grows during a run. ``SeedGate`` is the only door to host lowering.

Regenerate after an intended compiler change, then review the diff:

    python3 -m shear.hosted_bootstrap.seed_cli --write
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
import json
from pathlib import Path

from .. import bytecode
from ..examples._support import program
from ..examples.compiler_source import (
    COMPILE_NODE,
    EVALS,
    LOWER,
    SEQ_CODE,
    UPPER,
    compiler_entities,
)
from ..identity import EntityID, StateID, VersionID
from ..lang import _definition_of, load
from ..relations import relation_of
from ..state import State
from .descriptors import SUPPORTED_KINDS
from .errors import AdmissionRejected
from .trace import DECLARED_SEED, HOST_LOWER, Trace

MANIFEST_PATH = Path(__file__).with_name("manifest.json")
SCHEMA_VERSION = 1

ROOTS = tuple(sorted(
    (LOWER, UPPER, EVALS, SEQ_CODE, COMPILE_NODE),
    key=lambda entity: entity.value,
))

# Host machinery the pipeline may use besides the seed, listed apart from it
# (D4: explicitly contracted, replaceable Python host services).
FIXED_SERVICES = (
    "shear.machine: executes admitted chunks, explicit stacks",
    "shear.bytecode.lower: lowers only the declared seed nodes",
    "shear.canonical: canonical values and serialization",
    "shear.state, shear.runtime: semantic state, holds and cells",
    "shear.hosted_bootstrap.descriptors: node descriptors and generic "
    "decoding of compiler results",
    "shear.hosted_bootstrap.validation: structural admission checks",
)


@dataclass(frozen=True)
class SeedNode:
    entity: EntityID
    version: VersionID
    owner: EntityID


@dataclass(frozen=True)
class SeedManifest:
    compiler_source_state_id: StateID
    roots: tuple[EntityID, ...]
    functions: tuple[EntityID, ...]
    """Every compiler function in the dependency closure of the roots."""
    code_nodes: tuple[SeedNode, ...]
    fixed_services: tuple[str, ...]


@cache
def compiler_source_state() -> State:
    """The canonical SHEAR compiler source, loaded; never modified."""

    return load(program(compiler_entities()))


def derive(state: State) -> SeedManifest:
    """The seed of ``state``, from its canonical definitions and links alone."""

    pending = list(ROOTS)
    functions: set[EntityID] = set()
    nodes: list[SeedNode] = []

    while pending:
        function = pending.pop()

        if function in functions:
            continue

        value = state.values.get(function)
        definition = None if value is None else _definition_of(value)

        if definition is None:
            raise AdmissionRejected(
                f"{function.value} is not a compiler function"
            )

        functions.add(function)

        for entity in sorted(
            state.owned_subtree(function) - {function},
            key=lambda e: e.value,
        ):
            node = relation_of(state.values[entity])

            if node is None or node.kind not in SUPPORTED_KINDS:
                raise AdmissionRejected(
                    f"{entity.value}: the compiler source uses an operation "
                    "the SHEAR compiler cannot lower"
                )

            nodes.append(
                SeedNode(entity, state.values[entity].version_id, function)
            )

        for endpoint in definition.links.values():
            targets = (
                (endpoint,) if isinstance(endpoint, EntityID) else endpoint
            )

            for target in targets:
                linked = state.values[target]

                if _definition_of(linked) is not None:
                    pending.append(target)

    return SeedManifest(
        state.id,
        ROOTS,
        tuple(sorted(functions, key=lambda e: e.value)),
        tuple(sorted(nodes, key=lambda n: n.entity.value)),
        FIXED_SERVICES,
    )


def to_json(manifest: SeedManifest) -> str:
    return json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "compiler_source_state_id": manifest.compiler_source_state_id.value,
            "roots": [e.value for e in manifest.roots],
            "functions": [e.value for e in manifest.functions],
            "fixed_services": list(manifest.fixed_services),
            "code_nodes": [
                {
                    "entity": n.entity.value,
                    "version": n.version.value,
                    "owner": n.owner.value,
                }
                for n in manifest.code_nodes
            ],
        },
        indent=1,
    ) + "\n"


def load_manifest(path: Path = MANIFEST_PATH) -> SeedManifest:
    """The checked-in manifest, read fail-closed."""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        if data["schema_version"] != SCHEMA_VERSION:
            raise ValueError("unsupported schema version")

        return SeedManifest(
            StateID(data["compiler_source_state_id"]),
            tuple(EntityID(e) for e in data["roots"]),
            tuple(EntityID(e) for e in data["functions"]),
            tuple(
                SeedNode(
                    EntityID(n["entity"]),
                    VersionID(n["version"]),
                    EntityID(n["owner"]),
                )
                for n in data["code_nodes"]
            ),
            tuple(data["fixed_services"]),
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AdmissionRejected(
            f"the seed manifest {path.name} cannot be read: {exc}"
        ) from exc


@cache
def verified_manifest() -> SeedManifest:
    """The checked-in manifest, proved equal to the seed of the source."""

    declared = load_manifest()

    if declared != derive(compiler_source_state()):
        raise AdmissionRejected(
            "the seed manifest does not match the compiler source; "
            "regenerate it with `python3 -m shear.hosted_bootstrap.seed_cli "
            "--write` and review the difference"
        )

    return declared


class SeedGate:
    """The only door to host lowering: a declared seed node of the pinned
    compiler source, or nothing."""

    def __init__(
        self,
        state: State,
        manifest: SeedManifest,
        trace: Trace,
    ) -> None:
        self._state = state
        self._manifest = manifest
        self._trace = trace
        self._declared = {node.entity: node for node in manifest.code_nodes}

    def lower(self, entity: EntityID) -> tuple[SeedNode, tuple]:
        """Host-lower one declared seed node, or fail before lowering."""

        declared = self._declared.get(entity)
        value = self._state.values.get(entity)

        if (
            declared is None
            or value is None
            or value.version_id != declared.version
            or self._state.id != self._manifest.compiler_source_state_id
        ):
            raise AdmissionRejected(
                f"{entity.value} is not a declared seed node"
            )

        chunk = bytecode.lower(relation_of(value))
        self._trace.emit(
            HOST_LOWER,
            DECLARED_SEED,
            entity=entity,
            version=declared.version,
            generation=0,
        )

        return declared, chunk


def main(argv: list[str]) -> int:
    derived = derive(compiler_source_state())

    if argv == ["--write"]:
        MANIFEST_PATH.write_text(to_json(derived), encoding="utf-8")
        print(f"wrote {MANIFEST_PATH} ({len(derived.code_nodes)} nodes)")
        return 0

    if argv:
        print(__doc__)
        return 2

    if load_manifest() != derived:
        print("the seed manifest is stale")
        return 1

    print(f"the seed manifest is current ({len(derived.code_nodes)} nodes)")
    return 0

