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

The facts about each instruction (operand count, which operands are children,
link targets or names, which give a count, and the stack effect) come from
``shear.instructions.INSTRUCTIONS`` when a chunk is validated; this module
keeps none of its own, so an instruction the table lacks is refused.
"""

from __future__ import annotations

from typing import Any

from ..identity import EntityID
from ..instructions import INSTRUCTIONS, Instruction, stack_effect
from ..lang import NODE_KINDS, _definition_of
from ..operations import OPERATIONS
from ..relations import relation_of
from ..state import State
from .errors import AdmissionRejected


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
        entry = _check(node, entity, instruction, children, targets & permitted)
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

        taken, left = stack_effect(entry, operands)

        if depth < taken:
            raise AdmissionRejected(
                f"{entity.value}: {opcode} takes {taken} values from a "
                f"stack of {depth}"
            )

        depth += left - taken

        if entry.handover:
            if depth != 0:
                raise AdmissionRejected(
                    f"{entity.value}: {opcode} leaves {depth} values"
                )

            open_ = False
        elif entry.raises:
            open_ = False


def _check(
    node: Any,
    entity: EntityID,
    instruction: Any,
    children: set[EntityID],
    targets: set[EntityID],
) -> Instruction:
    """Check one instruction against the table and the node; its entry."""

    def reject(why: str) -> AdmissionRejected:
        return AdmissionRejected(f"{entity.value}: {why}")

    if (
        not isinstance(instruction, tuple)
        or not instruction
        or not isinstance(instruction[0], str)
    ):
        raise reject("malformed instruction")

    opcode, operands = instruction[0], instruction[1:]
    entry = INSTRUCTIONS.get(opcode)

    if entry is None:
        raise reject(f"unsupported instruction {opcode}")

    if len(operands) != entry.operands:
        raise reject(f"wrong operand count for {opcode}")

    for index in entry.children:
        if operands[index] not in children:
            raise reject(f"{opcode} names a node that is not a child")

    for index in entry.linked:
        _check_linked(opcode, entry, index, operands[index], targets, reject)

    for index in entry.names:
        if not isinstance(operands[index], str):
            raise reject(f"{opcode} needs a name")

    if entry.counted is not None:
        index, role = entry.counted

        if (
            type(operands[index]) is not int
            or operands[index] != len(node.roles.get(role, ()))
        ):
            raise reject(f"{opcode} count disagrees with the node")

    for index, role in entry.sized:
        if (
            not isinstance(operands[index], tuple)
            or len(operands[index]) != len(node.roles.get(role, ()))
        ):
            raise reject(f"{opcode} disagrees with the node's {role}")

    _check_shapes(opcode, operands, reject)

    return entry


def _check_linked(
    opcode: str,
    entry: Instruction,
    index: int,
    operand: Any,
    targets: set[EntityID],
    reject: Any,
) -> None:
    """A link operand is one entity, a tuple of entities, or (where the table
    allows it) none, and every entity is a link target."""

    if operand is None and index in entry.optional:
        return

    if index in entry.grouped:
        found = (
            isinstance(operand, tuple)
            and all(isinstance(item, EntityID) for item in operand)
        )
        group = operand if found else ()
    else:
        found = isinstance(operand, EntityID)
        group = (operand,) if found else ()

    if not found:
        raise reject(f"{opcode} needs link targets")

    if any(target not in targets for target in group):
        raise reject(f"{opcode} names a target that is not linked")


def _check_shapes(opcode: str, operands: tuple, reject: Any) -> None:
    """The types of operands the table does not describe."""

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

    if opcode in ("ACTIVATE", "TRIAL") and not _entries(operands[0]):
        raise reject(f"{opcode} needs (link, problem) entries")

    if opcode == "TRIAL" and not (
        operands[2] is None or isinstance(operands[2], str)
    ):
        raise reject("TRIAL needs None or a problem string")


def _entries(value: Any) -> bool:
    """A tuple of ``(name, problem)`` pairs: a name is a link name or a
    ``(link, label)`` pair, and a problem is none or a string."""

    def name(item: Any) -> bool:
        return isinstance(item, str) or (
            isinstance(item, tuple)
            and len(item) == 2
            and all(isinstance(part, str) for part in item)
        )

    return isinstance(value, tuple) and all(
        isinstance(pair, tuple)
        and len(pair) == 2
        and name(pair[0])
        and (pair[1] is None or isinstance(pair[1], str))
        for pair in value
    )
