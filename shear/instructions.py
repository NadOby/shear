"""The instructions lowering emits, as one table of metadata
(docs/live_evolution.md section 5.2).

``INSTRUCTIONS`` has one entry per instruction ``bytecode.lower`` can emit:
the host machine's dispatch less its internal ``CATCH_OK`` and ``RETURN``.
Admission (``hosted_bootstrap.validation``) reads it when it validates a
chunk, and the SHEAR-written VM (``examples/vm.py``) reads operand positions
from it where its generator encodes them. The tests check it against the
machine's dispatch, against the operands of every chunk host lowering
produces for the corpus, and against the VM's instruction set.

It is metadata only. What an instruction *does* stays explicit in each
route: the host machine and the VM execute independently, which is what
lets the VM stay an oracle. Nothing here lowers or runs anything.

**Provisional:** the field names beyond ``operands``, ``children`` and
``linked`` (live_evolution.md section 5.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

# How an operand gives a number of stack values: its value, or the length of
# the tuple it holds.
COUNT = "count"
LENGTH = "length"


@dataclass(frozen=True)
class Instruction:
    operands: int
    """How many operands the instruction has."""
    children: tuple[int, ...] = ()
    """Positions of operands that name a code child of the node."""
    linked: tuple[int, ...] = ()
    """Positions of operands that are link targets of the node and of its
    owner: an entity, a tuple of entities, or none where ``optional``."""
    grouped: tuple[int, ...] = ()
    """The ``linked`` positions that hold a tuple of entities rather than
    one."""
    optional: tuple[int, ...] = ()
    """The ``linked`` positions that are none when the link did not resolve."""
    names: tuple[int, ...] = ()
    """Positions of operands that must be strings."""
    counted: tuple[int, str] | None = None
    """``(position, role)``: the operand at ``position`` is the number of items
    in the node's ``role``."""
    sized: tuple[tuple[int, str], ...] = ()
    """``(position, role)``: the tuple at ``position`` has as many items as
    the node's ``role``."""
    taken: int = 0
    """Stack values taken whatever the operands."""
    taken_by: tuple[tuple[str, int], ...] = ()
    """More values taken, each given by an operand: ``(COUNT, position)`` or
    ``(LENGTH, position)``."""
    left: int = 0
    """Stack values left, unless the instruction hands over or raises."""
    handover: bool = False
    """It hands over control (``GOTO``, ``BRANCH``, ``LETBIND``): it takes its
    values, leaves none, and nothing may follow it."""
    raises: bool = False
    """It raises (``FAIL``, ``RAISE``): nothing is checked after it."""


def _plain(operands: int, taken: int, left: int, **fields) -> Instruction:
    return Instruction(operands, taken=taken, left=left, **fields)


INSTRUCTIONS: Mapping[str, Instruction] = {
    "END": Instruction(0),
    "POP": _plain(0, 1, 0),
    "ADD": _plain(0, 2, 1),
    "SUB": _plain(0, 2, 1),
    "MUL": _plain(0, 2, 1),
    "LT": _plain(0, 2, 1),
    "EQ": _plain(0, 2, 1),
    "LEN": _plain(0, 1, 1),
    "ITEM": _plain(0, 2, 1),
    "SLICE": _plain(0, 3, 1),
    "CONCAT": _plain(0, 2, 1),
    "REFCHECK": _plain(0, 1, 1),
    "APPLYV": _plain(0, 2, 1),
    "FAIL": Instruction(0, taken=2, raises=True),
    "FUNCTION": _plain(0, 2, 1),
    "LIT": _plain(1, 0, 1),
    "ARG": _plain(1, 0, 1, names=(0,)),
    "EVAL": _plain(1, 0, 1, children=(0,)),
    "GOTO": Instruction(1, children=(0,), handover=True),
    "INT": _plain(1, 1, 1, names=(0,)),
    "TUPLE": _plain(1, 1, 1, names=(0,)),
    "MKTUPLE": Instruction(
        1, counted=(0, "items"), taken_by=((COUNT, 0),), left=1,
    ),
    "APPLY": Instruction(
        1, counted=(0, "args"), taken=1, taken_by=((COUNT, 0),), left=1,
    ),
    "LETCHECK": _plain(1, 0, 0, names=(0,)),
    "RAISE": Instruction(1, names=(0,), raises=True),
    "READ": _plain(1, 0, 1, linked=(0,)),
    "WRITE": _plain(1, 1, 1, linked=(0,)),
    "BRANCH": Instruction(2, children=(0, 1), taken=1, handover=True),
    "CALL": Instruction(
        2, linked=(0,), counted=(1, "args"), taken_by=((COUNT, 1),), left=1,
    ),
    "LETBIND": Instruction(
        2, children=(1,), names=(0,), taken=1, handover=True,
    ),
    "CATCH": _plain(2, 0, 1, children=(0,)),
    "REF": _plain(2, 0, 1, linked=(0,), names=(1,)),
    "CODE": _plain(2, 0, 1, linked=(0,), names=(1,)),
    "LINKS": _plain(2, 0, 1, linked=(0,), names=(1,)),
    "QUOTE": Instruction(
        2, counted=(1, "holes"), taken_by=((COUNT, 1),), left=1,
    ),
    "CLOSURE": _plain(3, 0, 1, children=(0,)),
    "ACTIVATE": Instruction(
        2,
        linked=(1,),
        grouped=(1,),
        sized=((0, "values"),),
        taken_by=((LENGTH, 0),),
        left=1,
    ),
    "TRIAL": Instruction(
        5,
        linked=(1, 3),
        grouped=(1,),
        optional=(3,),
        counted=(4, "args"),
        sized=((0, "values"),),
        taken_by=((LENGTH, 0), (COUNT, 4)),
        left=1,
    ),
}


def stack_effect(entry: Instruction, operands: tuple) -> tuple[int, int]:
    """``(taken, left)`` of one instruction with these operands.

    A handover or a raise leaves nothing: control leaves the chunk. The
    operands must already have the right count and types; a count that is not
    a plain int, or a tuple operand that is not a tuple, is the caller's to
    reject first.
    """

    taken = entry.taken

    for how, position in entry.taken_by:
        taken += operands[position] if how == COUNT else len(operands[position])

    return taken, 0 if entry.handover or entry.raises else entry.left
