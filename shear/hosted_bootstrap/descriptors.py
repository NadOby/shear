"""The host side of the compiler boundary: what the SHEAR compiler is given
and how its answer is read back (docs/hosted_pipeline.md section 3).

``describe`` builds, from one node of a pinned state, the descriptor
``compile_node`` takes: the node's operation and operands in input-form order
(children as ``EntityID``, link names replaced by their resolved targets, the
payload decoded where the instruction holds it decoded) and its identity. It
reads operation shapes from ``shear.operations`` and makes no lowering
decision: no instruction, operand order or opcode is chosen here.

``decode_chunk`` reads the answer back. The machine canonicalizes what it is
given, so identities and tuples come back as canonical nodes; they are turned
into the plain values ``bytecode.lower`` holds. The one exception is the
operand of ``LIT``: a literal keeps its canonical form, as the node's payload
does in host lowering. Nothing is synthesized or repaired.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..canonical import CanonicalNode
from ..examples.compiler_source import LOWERED
from ..identity import EntityID, StateID, VersionID
from ..lang import INVALID_KIND, NODE_KINDS, _decode
from ..operations import OPERATIONS, Shape
from ..relations import Relation, relation_of
from ..state import State
from .errors import AdmissionRejected, UnsupportedOperation

# What the SHEAR compiler lowers as node mode: its input-form operations
# (``label`` is input-form only) and the host's ``invalid`` node.
SUPPORTED_KINDS = (LOWERED - {"label"}) | {INVALID_KIND}


@dataclass(frozen=True)
class Descriptor:
    """The argument of ``compile_node`` for one node, and what it names."""

    kind: str
    value: tuple
    """``(operands, (state_id, node, version, owner))``."""


def describe(state: State, entity: EntityID, owner: EntityID) -> Descriptor:
    """The descriptor of ``entity``, a code node of ``owner`` in ``state``."""

    value = state.values.get(entity)
    node = None if value is None else relation_of(value)

    if node is None or node.kind not in NODE_KINDS:
        raise AdmissionRejected(f"{entity.value} is not a code node")

    if node.kind not in SUPPORTED_KINDS:
        raise UnsupportedOperation(
            f"{entity.value}: the SHEAR compiler does not lower "
            f"{node.kind!r}"
        )

    return Descriptor(
        node.kind,
        (
            _operands(node),
            (state.id, entity, value.version_id, owner),
        ),
    )


def _operands(node: Relation) -> tuple:
    kind, roles = node.kind, node.roles
    payload = _decode(node.payload)

    if kind == "lit":
        return (kind, node.payload)

    if kind == "arg":
        return (kind, payload)

    if kind == INVALID_KIND:
        return (kind, payload[0])

    if kind == "call":
        return (kind, roles["target"], *roles["args"])

    if kind == "read":
        return (kind, roles["cell"])

    if kind == "write":
        return (kind, roles["cell"], roles["value"])

    if kind == "let":
        return (kind, payload, roles["value"], roles["body"])

    if kind in ("ref", "code", "linksof"):
        return (kind, roles["target"], payload)

    if kind == "closure":
        return (kind, payload["params"], payload["captures"], roles["body"])

    if kind == "catch":
        body = roles["body"]
        return (kind, body) if payload is None else (kind, body, payload)

    return (kind, *_positional(OPERATIONS[kind], roles))


def _positional(shape: Shape, roles: Any) -> list:
    operands: list = []

    for role in shape.code:
        if role in shape.ordered:
            operands.extend(roles[role])
        else:
            operands.append(roles[role])

    return operands


def _items(value: Any) -> tuple | None:
    if isinstance(value, CanonicalNode):
        return value[2] if value[1] == "tuple" else None

    return value if isinstance(value, tuple) else None


def _plain(value: Any) -> Any:
    """A canonical value as the plain Python value it encodes."""

    if isinstance(value, CanonicalNode):
        tag, payload = value[1], value[2]

        if tag == "entity_id":
            return EntityID(payload)

        if tag == "version_id":
            return VersionID(payload)

        if tag == "state_id":
            return StateID(payload)

        if tag == "tuple":
            return tuple(_plain(item) for item in payload)

        if tag == "list":
            return [_plain(item) for item in payload]

        if tag == "map":
            return {_plain(key): _plain(item) for key, item in payload}

        return value

    if isinstance(value, tuple):
        return tuple(_plain(item) for item in value)

    return value


def decode_chunk(result: Any) -> tuple:
    """The chunk a ``compile_node`` run returned, as plain values."""

    instructions = _items(result)

    if instructions is None:
        raise AdmissionRejected("the compiler did not return a chunk")

    return tuple(_instruction(raw) for raw in instructions)


def _instruction(raw: Any) -> tuple:
    items = _items(raw)

    if not items or not isinstance(items[0], str):
        raise AdmissionRejected("the compiler returned a malformed instruction")

    opcode, operands = items[0], items[1:]

    if opcode == "LIT":
        return (opcode, *operands)

    return (opcode, *(_plain(operand) for operand in operands))
