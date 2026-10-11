"""Structural admission checks for a produced chunk (docs/hosted_pipeline.md
section 6).

Admission authenticates a chunk's origin and structure. It does not decide
whether the compiler was right: it never lowers the node again, so host
lowering stays a test oracle and never becomes part of admission.

A chunk of node N is well formed when its instructions are known and have
their operands, it ends with ``END``, every child operand is one of N's own
code children, and every entity operand is both one of N's own link targets
and a link of N's owner.
"""

from __future__ import annotations

from typing import Any

from ..identity import EntityID
from ..lang import NODE_KINDS, _definition_of
from ..operations import OPERATIONS
from ..relations import relation_of
from ..state import State
from .errors import AdmissionRejected

# Operand counts of the instructions the SHEAR compiler can produce.
_OPERANDS = {
    "END": 0, "POP": 0, "ADD": 0, "SUB": 0, "MUL": 0, "LT": 0, "EQ": 0,
    "LEN": 0, "ITEM": 0, "SLICE": 0, "CONCAT": 0, "REFCHECK": 0,
    "APPLYV": 0, "FAIL": 0,
    "LIT": 1, "ARG": 1, "EVAL": 1, "GOTO": 1, "INT": 1, "TUPLE": 1,
    "MKTUPLE": 1, "APPLY": 1, "LETCHECK": 1, "RAISE": 1, "READ": 1,
    "WRITE": 1,
    "BRANCH": 2, "CALL": 2, "LETBIND": 2, "CATCH": 2,
    "REF": 2, "CODE": 2, "LINKS": 2,
    "CLOSURE": 3,
}

# Positions of operands that name a child node of the chunk's node.
_CHILDREN = {
    "EVAL": (0,), "GOTO": (0,), "BRANCH": (0, 1), "LETBIND": (1,),
    "CATCH": (0,), "CLOSURE": (0,),
}

# Instructions whose first operand names a link target of the node.
_LINKED = frozenset({"CALL", "REF", "CODE", "LINKS", "READ", "WRITE"})

# Instructions whose count operand is the number of items in a role.
_COUNTED = {"CALL": "args", "APPLY": "args", "MKTUPLE": "items"}


def _endpoints(value: Any) -> tuple[EntityID, ...]:
    if isinstance(value, EntityID):
        return (value,)

    if isinstance(value, tuple):
        return tuple(item for item in value if isinstance(item, EntityID))

    return ()


def validate_chunk(
    state: State,
    entity: EntityID,
    owner: EntityID,
    chunk: Any,
) -> None:
    """Raise ``AdmissionRejected`` unless ``chunk`` is well formed for the
    code node ``entity`` of ``owner`` in ``state``."""

    value = state.values.get(entity)
    node = None if value is None else relation_of(value)
    owner_value = state.values.get(owner)
    definition = None if owner_value is None else _definition_of(owner_value)

    if (
        node is None
        or node.kind not in NODE_KINDS
        or definition is None
        or entity == owner
        or state.owner_of(entity) != owner
    ):
        raise AdmissionRejected(
            f"{entity.value} is not an executable node of {owner.value}"
        )

    code_roles = OPERATIONS[node.kind].code
    children = {
        child
        for role in code_roles
        for child in _endpoints(node.roles.get(role))
    }
    targets = {
        target
        for role, endpoint in node.roles.items()
        if role not in code_roles
        for target in _endpoints(endpoint)
    }
    permitted = {
        target
        for endpoint in definition.links.values()
        for target in _endpoints(endpoint)
    }

    if (
        not isinstance(chunk, tuple)
        or not chunk
        or chunk[-1] != ("END",)
    ):
        raise AdmissionRejected(f"{entity.value}: a chunk must end with END")

    for instruction in chunk:
        _check(node, entity, instruction, children, targets & permitted)


def _check(
    node: Any,
    entity: EntityID,
    instruction: Any,
    children: set[EntityID],
    targets: set[EntityID],
) -> None:
    def reject(why: str) -> AdmissionRejected:
        return AdmissionRejected(f"{entity.value}: {why}")

    if (
        not isinstance(instruction, tuple)
        or not instruction
        or not isinstance(instruction[0], str)
    ):
        raise reject("malformed instruction")

    opcode, operands = instruction[0], instruction[1:]

    if opcode not in _OPERANDS:
        raise reject(f"unsupported instruction {opcode}")

    if len(operands) != _OPERANDS[opcode]:
        raise reject(f"wrong operand count for {opcode}")

    for index in _CHILDREN.get(opcode, ()):
        if operands[index] not in children:
            raise reject(f"{opcode} names a node that is not a child")

    if opcode in _LINKED and operands[0] not in targets:
        raise reject(f"{opcode} names a target that is not linked")

    role = _COUNTED.get(opcode)

    if role is not None:
        if operands[-1] != len(node.roles.get(role, ())):
            raise reject(f"{opcode} count disagrees with the node")
