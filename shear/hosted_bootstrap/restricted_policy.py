"""Generic source/bytecode effect preflight for admitted SHEAR execution.

This is host-side restriction metadata, not a language-visible effect system.
It does not authenticate artifacts: the caller must first establish their
compiler-production and admission authority, and must pin the same admitted
artifact view for the subsequent machine invocation.

Conservative by design: only statically resolved calls are supported. All
code nodes of each reachable function are checked, including dead branches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ..identity import EntityID, VersionID
from ..lang import NODE_KINDS, _definition_of
from ..relations import relation_of
from ..state import State
from .artifacts import Artifact, TARGET
from .errors import AdmissionRejected
from .validation import validate_chunk


# The exact, bounded Task 32 policy (docs/restricted_execution.md section 5.1).
# These sets are independent of the instruction structural validator: a
# structurally valid instruction can still be forbidden by this policy.
_PURE_SOURCE = frozenset({
    "lit", "arg", "add", "sub", "mul", "lt", "eq", "tuple", "seq",
    "if", "let", "unquote", "len", "item", "slice", "concat",
    "catch", "raise", "invalid", "call",
})
_PURE_INSTRUCTIONS = frozenset({
    "LIT", "ARG", "ADD", "SUB", "MUL", "LT", "EQ", "INT",
    "TUPLE", "MKTUPLE", "LEN", "ITEM", "SLICE", "CONCAT", "POP",
    "EVAL", "BRANCH", "GOTO", "LETCHECK", "LETBIND", "END",
    "CALL", "CATCH", "FAIL", "RAISE",
})
_KNOWN_EFFECTS = frozenset({"read", "write", "activate", "trial"})


@dataclass(frozen=True)
class RestrictionPolicy:
    """Allowed host-managed effects. Empty means pure execution.

    Only ``read`` has an implementation in the Task 32 restricted runner.
    Listing an effect does not authorize an unsupported execution category.
    """

    allowed_effects: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.allowed_effects, frozenset)
            or any(not isinstance(e, str) for e in self.allowed_effects)
            or not self.allowed_effects <= _KNOWN_EFFECTS
        ):
            raise ValueError("unknown restricted-execution effect")


def _permit_source(kind: str, policy: RestrictionPolicy) -> bool:
    return kind in _PURE_SOURCE or (
        kind == "read" and "read" in policy.allowed_effects
    )


def _permit_instruction(opcode: str, policy: RestrictionPolicy) -> bool:
    return opcode in _PURE_INSTRUCTIONS or (
        opcode == "READ" and "read" in policy.allowed_effects
    )


def _function(state: State, entity: EntityID):
    value = state.values.get(entity)
    if value is None:
        raise AdmissionRejected(f"{entity.value}: function is absent")
    try:
        definition = _definition_of(value)
    except (TypeError, ValueError, KeyError) as exc:
        raise AdmissionRejected(
            f"{entity.value}: malformed function definition"
        ) from exc
    if definition is None or not isinstance(definition.body, EntityID):
        raise AdmissionRejected(f"{entity.value}: not a loaded function")
    return definition


def _check_links(state: State) -> None:
    """Reject malformed link function roles before trusting call resolution.

    A tuple-valued ``function`` role is not a function, even if it contains
    exactly one valid entity. Do not normalize it away (#110).
    """

    for value in state.values.values():
        relation = relation_of(value)
        if relation is not None and relation.kind == "links":
            if not isinstance(relation.roles.get("function"), EntityID):
                raise AdmissionRejected("malformed links function role")


def preflight(
    state: State,
    artifacts: Mapping[tuple[EntityID, VersionID], Artifact],
    entry: EntityID,
    policy: RestrictionPolicy,
) -> frozenset[tuple[EntityID, VersionID]]:
    """Prove that the entire statically reachable admitted program is safe.

    Checks *both* graph nodes and the actual admitted chunks. Transitive
    calls, including those in unreachable branches, must be proven before
    any machine instruction executes. Unknown operations, indirect calls,
    unresolved targets and unsupported effects reject closed.

    Returns the node/version keys whose artifacts the invocation may use.
    Artifact integrity and structural validity are checked here, but the
    caller must separately authenticate their production and admission.
    """

    if not isinstance(policy, RestrictionPolicy):
        raise TypeError("expected RestrictionPolicy")
    if not isinstance(entry, EntityID):
        raise AdmissionRejected("restricted entry must be an EntityID")

    _check_links(state)
    visited: set[EntityID] = set()
    allowed: set[tuple[EntityID, VersionID]] = set()
    pending = [entry]

    while pending:
        owner = pending.pop()
        if owner in visited:
            continue
        visited.add(owner)
        definition = _function(state, owner)

        # Prevent malformed or ambiguous function-local link references from
        # being mistaken for a statically proven callee.
        for name, target in definition.links.items():
            if not isinstance(name, str) or not isinstance(target, EntityID):
                raise AdmissionRejected(
                    f"{owner.value}: unresolved or grouped link {name!r}"
                )

        nodes = state.owned_subtree(owner) - {owner}
        if definition.body not in nodes:
            raise AdmissionRejected(f"{owner.value}: body has no code owner")

        for node_id in nodes:
            value = state.values.get(node_id)
            relation = None if value is None else relation_of(value)
            if relation is None or relation.kind not in NODE_KINDS:
                raise AdmissionRejected(
                    f"{node_id.value}: unclassified executable node"
                )
            if not _permit_source(relation.kind, policy):
                raise AdmissionRejected(
                    f"{node_id.value}: forbidden source {relation.kind}"
                )

            key = (node_id, value.version_id)
            artifact = artifacts.get(key)
            if artifact is None:
                raise AdmissionRejected(
                    f"{node_id.value}: no admitted executable artifact"
                )
            if (
                artifact.domain != TARGET
                or artifact.state_id != state.id
                or artifact.entity != node_id
                or artifact.version != value.version_id
                or artifact.owner != owner
                or artifact.generation is not None
                or artifact.produced_by is None
            ):
                raise AdmissionRejected(
                    f"{node_id.value}: artifact binding mismatch"
                )
            artifact.verify()
            validate_chunk(state, node_id, owner, artifact.chunk)
            allowed.add(key)

            if relation.kind == "call":
                target = relation.roles.get("target")
                if not isinstance(target, EntityID):
                    raise AdmissionRejected(
                        f"{node_id.value}: unresolved static call"
                    )
                if target not in definition.links.values():
                    raise AdmissionRejected(
                        f"{node_id.value}: static call lacks a link"
                    )
                _function(state, target)
                pending.append(target)

            for instruction in artifact.chunk:
                opcode = instruction[0]
                if not _permit_instruction(opcode, policy):
                    raise AdmissionRejected(
                        f"{node_id.value}: forbidden instruction {opcode}"
                    )
                if opcode == "CALL":
                    target = instruction[1]
                    if not isinstance(target, EntityID):
                        raise AdmissionRejected(
                            f"{node_id.value}: unresolved emitted call"
                        )
                    _function(state, target)
                    pending.append(target)

    return frozenset(allowed)
