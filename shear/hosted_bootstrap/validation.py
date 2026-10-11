"""Structural admission checks for a produced chunk (docs/hosted_pipeline.md
section 6).

Admission authenticates a chunk's origin and structure. It does not decide
whether the compiler was right: it never lowers the node again, so host
lowering stays a test oracle and never becomes part of admission.

A chunk of node N is well formed when its instructions are known and have
their operands, every child operand is one of N's own code children, every
entity operand is both one of N's own link targets and a link of N's owner,
and its operand stack is sound: no instruction takes more values than the
stack holds, a handover (``GOTO``, ``BRANCH``, ``LETBIND``) leaves it empty,
only the final ``END`` follows a handover or a raise, and the chunk ends
with exactly one value, its result. A chunk has no jumps inside it, so one
pass settles this.
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


# Values an instruction takes from the stack and leaves on it. ``MKTUPLE``,
# ``CALL`` and ``APPLY`` also take their counted arguments (see _taken).
_STACK = {
    "LIT": (0, 1), "ARG": (0, 1), "EVAL": (0, 1), "REF": (0, 1),
    "CODE": (0, 1), "LINKS": (0, 1), "READ": (0, 1), "CLOSURE": (0, 1),
    "CATCH": (0, 1), "LETCHECK": (0, 0), "POP": (1, 0), "INT": (1, 1),
    "TUPLE": (1, 1), "REFCHECK": (1, 1), "WRITE": (1, 1), "LEN": (1, 1),
    "ADD": (2, 1), "SUB": (2, 1), "MUL": (2, 1), "LT": (2, 1),
    "EQ": (2, 1), "ITEM": (2, 1), "CONCAT": (2, 1), "APPLYV": (2, 1),
    "SLICE": (3, 1), "MKTUPLE": (0, 1), "CALL": (0, 1), "APPLY": (1, 1),
}

# Handovers: the instruction takes this many values and nothing may stay.
_HANDOVER = {"GOTO": 0, "BRANCH": 1, "LETBIND": 1}

# Instructions that raise: nothing is checked after them.
_RAISING = {"FAIL": 2, "RAISE": 0}

# Operands that name something and so must be strings.
_NAMES = {
    "ARG": (0,), "INT": (0,), "TUPLE": (0,), "LETCHECK": (0,),
    "LETBIND": (0,), "RAISE": (0,), "REF": (1,), "CODE": (1,),
    "LINKS": (1,),
}


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

    depth = 0
    open_ = True

    for position, instruction in enumerate(chunk):
        _check(node, entity, instruction, children, targets & permitted)
        opcode, operands = instruction[0], instruction[1:]

        if opcode == "END":
            if position != len(chunk) - 1:
                raise AdmissionRejected(
                    f"{entity.value}: END before the end of the chunk"
                )

            if open_ and depth != 1:
                raise AdmissionRejected(
                    f"{entity.value}: a chunk must end with one value, "
                    f"not {depth}"
                )

            continue

        if not open_:
            raise AdmissionRejected(
                f"{entity.value}: {opcode} is unreachable"
            )

        taken, left = _stack_effect(opcode, operands)

        if depth < taken:
            raise AdmissionRejected(
                f"{entity.value}: {opcode} takes {taken} values from a "
                f"stack of {depth}"
            )

        depth += left - taken

        if opcode in _HANDOVER:
            if depth != 0:
                raise AdmissionRejected(
                    f"{entity.value}: {opcode} leaves {depth} values"
                )

            open_ = False
        elif opcode in _RAISING:
            open_ = False


def _stack_effect(opcode: str, operands: tuple) -> tuple[int, int]:
    """``(taken, left)`` of one instruction."""

    if opcode in _HANDOVER:
        return _HANDOVER[opcode], 0

    if opcode in _RAISING:
        return _RAISING[opcode], 0

    taken, left = _STACK[opcode]

    if opcode in _COUNTED:
        taken += operands[-1]

    return taken, left


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

    for index in _NAMES.get(opcode, ()):
        if not isinstance(operands[index], str):
            raise reject(f"{opcode} needs a name")

    if opcode == "CLOSURE" and not all(
        isinstance(names, tuple) and all(isinstance(n, str) for n in names)
        for names in operands[1:]
    ):
        raise reject("CLOSURE needs tuples of names")

    if opcode == "CATCH" and operands[1] is not None and not (
        isinstance(operands[1], tuple)
        and all(isinstance(kind, str) for kind in operands[1])
    ):
        raise reject("CATCH needs None or a tuple of kinds")

    role = _COUNTED.get(opcode)

    if role is not None:
        if (
            type(operands[-1]) is not int
            or operands[-1] != len(node.roles.get(role, ()))
        ):
            raise reject(f"{opcode} count disagrees with the node")
