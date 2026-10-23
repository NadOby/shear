"""The mechanical shape of each graph-form operation (graph_form.md §3).

One table says, per node kind, how many input-form operands it takes, which
roles hold code and in which input order, and which of those roles hold an
ordered tuple of nodes. ``lang`` (building and collapsing graph form),
``continuity`` (operand paths) and ``syntax`` (builtin arity) read it instead
of keeping their own copies. What an operation *means* (how it is parsed,
lowered, run or compiled by the self-hosted compiler) stays explicit in each
of those modules.

A *positional* operation is pure structure: no payload and no link, and its
input operands are its code roles in order, the last one taking every
remaining operand when it is ordered. ``lang`` builds and collapses those
generically; every other operation has its own case there.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Shape:
    kind: str
    arity: int | None = None
    """Fixed number of input-form operands, None when variable."""
    code: tuple[str, ...] = ()
    """Roles that hold code, in input-form order."""
    ordered: frozenset[str] = frozenset()
    """The code roles that hold an ordered tuple of nodes."""
    positional: bool = False
    minimum: int = 0
    """Fewest input operands a positional operation accepts."""
    too_few: str = ""
    """The problem recorded when it gets fewer."""


def _shapes(*shapes: Shape) -> Mapping[str, Shape]:
    return {shape.kind: shape for shape in shapes}


BINARY = ("add", "sub", "mul", "lt", "eq")
INVALID = "invalid"

OPERATIONS: Mapping[str, Shape] = _shapes(
    Shape("lit", 1),
    Shape("arg", 1),
    *(Shape(kind, 2, ("left", "right"), positional=True) for kind in BINARY),
    Shape("if", 3, ("cond", "then", "else"), positional=True),
    Shape(
        "seq", None, ("items",), frozenset({"items"}), True,
        1, "seq needs at least one expression",
    ),
    Shape("call", None, ("args",), frozenset({"args"})),
    Shape("read", 1),
    Shape("write", 2, ("value",)),
    Shape("quote", 1, ("holes",), frozenset({"holes"})),
    Shape("unquote", None, ("expr",)),
    Shape("function", 2, ("params", "body"), positional=True),
    Shape("closure", 3, ("body",)),
    Shape("activate", None, ("values",), frozenset({"values"})),
    Shape("trial", None, ("args", "values"), frozenset({"args", "values"})),
    Shape("tuple", None, ("items",), frozenset({"items"}), True),
    Shape("inspect", 1, ("value",), positional=True),
    Shape("record", 2, ("kind", "fields"), positional=True),
    Shape("len", 1, ("tuple",), positional=True),
    Shape("item", 2, ("tuple", "index"), positional=True),
    Shape("slice", 3, ("tuple", "start", "stop"), positional=True),
    Shape("concat", 2, ("left", "right"), positional=True),
    Shape("let", 3, ("value", "body")),
    Shape("catch", None, ("body",)),
    Shape("raise", 2, ("kind", "detail"), positional=True),
    Shape("ref", 1),
    Shape("code", 1),
    Shape("linksof", 1),
    Shape(
        "apply", None, ("function", "args"), frozenset({"args"}), True,
        1, "apply needs a function",
    ),
    Shape("applyv", 2, ("function", "args"), positional=True),
    Shape(INVALID),
)

ARITY: Mapping[str, int] = {
    kind: shape.arity
    for kind, shape in OPERATIONS.items()
    if shape.arity is not None
}

CODE_ROLES: Mapping[str, tuple[str, ...]] = {
    kind: shape.code
    for kind, shape in OPERATIONS.items()
    if shape.code
}
