"""Bytecode lowering for graph-form code (docs/bytecode.md).

Every expression node of a loaded program lowers to a **chunk**: a tuple of
instructions such as ``("ARG", "x")``, ``("MUL",)`` or ``("CALL", f, 2)``.

A chunk holds the instructions of one node only and names child nodes by
``EntityID``. It therefore depends only on the node's semantic value and can
be cached on that value across program versions.

Execution lives in :mod:`shear.machine`.
"""

from __future__ import annotations

from typing import Any

from .identity import EntityID
from .lang import (
    INVALID_KIND,
    NODE_KINDS,
    LanguageError,
    _decode,
)
from .relations import Relation, relation_of
from .values import Value

Instruction = tuple
Chunk = tuple

# Provisional (bytecode.md section 4): the most calls that may wait on each
# other in one run. Tail calls replace their caller and do not count.
CALL_DEPTH_LIMIT = 100_000

_END: Instruction = ("END",)

# Number of nodes lowered since process start. Tests use this to verify that
# unchanged nodes retain their cached chunks across edits.
_lowered = 0


def lowered_count() -> int:
    """Return the number of nodes lowered since process start."""

    return _lowered


def _eval_all(
    entities: tuple[EntityID, ...],
) -> list[Instruction]:
    return [
        ("EVAL", entity)
        for entity in entities
    ]


def lower(node: Relation) -> Chunk:
    """Lower one graph-form node to bytecode.

    Lowering depends only on ``node``. Invalid code lowers to ``RAISE`` so
    failure remains an execution-time property.
    """

    kind = node.kind
    roles = node.roles
    code: list[Instruction]

    if kind == INVALID_KIND:
        code = [
            (
                "RAISE",
                _decode(node.payload)[0],
            )
        ]

    elif kind == "lit":
        code = [
            ("LIT", node.payload)
        ]

    elif kind == "arg":
        code = [
            (
                "ARG",
                _decode(node.payload),
            )
        ]

    elif kind in (
        "add",
        "sub",
        "mul",
        "lt",
    ):
        code = [
            ("EVAL", roles["left"]),
            ("INT", kind),
            ("EVAL", roles["right"]),
            ("INT", kind),
            (kind.upper(),),
        ]

    elif kind == "eq":
        code = [
            ("EVAL", roles["left"]),
            ("EVAL", roles["right"]),
            ("EQ",),
        ]

    elif kind == "if":
        code = [
            ("EVAL", roles["cond"]),
            (
                "BRANCH",
                roles["then"],
                roles["else"],
            ),
        ]

    elif kind == "seq":
        items = roles["items"]
        code = []

        for item in items[:-1]:
            code += [
                ("EVAL", item),
                ("POP",),
            ]

        code.append(
            ("GOTO", items[-1])
            if items
            else ("LIT", None)
        )

    elif kind == "call":
        args = roles["args"]
        code = [
            *_eval_all(args),
            (
                "CALL",
                roles["target"],
                len(args),
            ),
        ]

    elif kind == "tuple":
        items = roles["items"]
        code = [
            *_eval_all(items),
            ("MKTUPLE", len(items)),
        ]

    elif kind == "inspect":
        code = [
            ("EVAL", roles["value"]),
            ("INSPECT",),
        ]

    elif kind == "record":
        code = [
            ("EVAL", roles["kind"]),
            ("EVAL", roles["fields"]),
            ("RECORD",),
        ]

    elif kind == "len":
        code = [
            ("EVAL", roles["tuple"]),
            ("TUPLE", kind),
            ("LEN",),
        ]

    elif kind == "item":
        code = [
            ("EVAL", roles["tuple"]),
            ("TUPLE", kind),
            ("EVAL", roles["index"]),
            ("INT", kind),
            ("ITEM",),
        ]

    elif kind == "slice":
        code = [
            ("EVAL", roles["tuple"]),
            ("TUPLE", kind),
            ("EVAL", roles["start"]),
            ("INT", kind),
            ("EVAL", roles["stop"]),
            ("INT", kind),
            ("SLICE",),
        ]

    elif kind == "concat":
        code = [
            ("EVAL", roles["left"]),
            ("TUPLE", kind),
            ("EVAL", roles["right"]),
            ("TUPLE", kind),
            ("CONCAT",),
        ]

    elif kind == "let":
        name = _decode(node.payload)
        code = [
            ("LETCHECK", name),
            ("EVAL", roles["value"]),
            (
                "LETBIND",
                name,
                roles["body"],
            ),
        ]

    elif kind == "catch":
        code = [
            (
                "CATCH",
                roles["body"],
                _decode(node.payload),
            )
        ]

    elif kind == "raise":
        code = [
            ("EVAL", roles["kind"]),
            ("EVAL", roles["detail"]),
            ("FAIL",),
        ]

    elif kind == "ref":
        code = [
            (
                "REF",
                roles["target"],
                _decode(node.payload),
            )
        ]

    elif kind == "code":
        code = [
            (
                "CODE",
                roles["target"],
                _decode(node.payload),
            )
        ]

    elif kind == "linksof":
        code = [
            (
                "LINKS",
                roles["target"],
                _decode(node.payload),
            )
        ]

    elif kind == "applyv":
        code = [
            ("EVAL", roles["function"]),
            ("REFCHECK",),
            ("EVAL", roles["args"]),
            ("TUPLE", kind),
            ("APPLYV",),
        ]

    elif kind == "apply":
        args = roles["args"]
        code = [
            ("EVAL", roles["function"]),
            ("REFCHECK",),
            *_eval_all(args),
            ("APPLY", len(args)),
        ]

    elif kind == "read":
        code = [
            ("READ", roles["cell"])
        ]

    elif kind == "write":
        code = [
            ("EVAL", roles["value"]),
            ("WRITE", roles["cell"]),
        ]

    elif kind == "quote":
        holes = roles["holes"]
        code = [
            *_eval_all(holes),
            (
                "QUOTE",
                node.payload,
                len(holes),
            ),
        ]

    elif kind == "unquote":
        code = [
            ("GOTO", roles["expr"])
        ]

    elif kind == "function":
        code = [
            ("EVAL", roles["params"]),
            ("EVAL", roles["body"]),
            ("FUNCTION",),
        ]

    elif kind == "closure":
        payload = _decode(node.payload)
        code = [
            (
                "CLOSURE",
                roles["body"],
                payload["params"],
                payload["captures"],
            )
        ]

    elif kind in (
        "activate",
        "trial",
    ):
        code = _lower_activation(node)

    else:
        code = [
            (
                "RAISE",
                f"unknown operation {kind!r}",
            )
        ]

    return (
        *code,
        _END,
    )


def _lower_activation(
    node: Relation,
) -> list[Instruction]:
    """Lower ``activate`` or ``trial``."""

    roles = node.roles
    payload = _decode(node.payload)
    entries = tuple(payload["links"])
    values = roles["values"]
    code: list[Instruction] = []

    if node.kind == "trial":
        code += _eval_all(
            roles["args"]
        )

    if len(entries) != len(values):
        code.append(
            (
                "RAISE",
                f"{node.kind} needs link/value pairs",
            )
        )
        return code

    code += _eval_all(values)

    if node.kind == "activate":
        code.append(
            (
                "ACTIVATE",
                entries,
                roles["targets"],
            )
        )
    else:
        problem = payload["call"][1]
        code.append(
            (
                "TRIAL",
                entries,
                roles["targets"],
                problem,
                roles.get("target"),
                len(roles["args"]),
            )
        )

    return code


def chunk_of(
    state: Any,
    entity: EntityID,
    owner: EntityID | None = None,
) -> Chunk:
    """Return a node's cached chunk, lowering it if necessary."""

    value = state.values.get(entity)

    if value is not None:
        chunk = value.__dict__.get(
            "_chunk"
        )

        if chunk is not None:
            return chunk

    return lower_value(
        value,
        entity,
        owner,
    )


def lower_value(
    value: Value | None,
    entity: EntityID,
    owner: EntityID | None,
) -> Chunk:
    global _lowered

    node = (
        None
        if value is None
        else relation_of(value)
    )

    if (
        node is None
        or node.kind not in NODE_KINDS
    ):
        where = (
            owner.value
            if owner is not None
            else entity.value
        )
        raise LanguageError(
            f"{where}: {entity.value} "
            f"is not a code node"
        )

    chunk = lower(node)
    object.__setattr__(
        value,
        "_chunk",
        chunk,
    )
    _lowered += 1

    return chunk


def disassemble(
    chunk: Chunk,
) -> str:
    """Return one human-readable instruction per line."""

    def show(
        operand: Any,
    ) -> str:
        if isinstance(
            operand,
            EntityID,
        ):
            return operand.value

        if isinstance(
            operand,
            tuple,
        ):
            return (
                "("
                + ", ".join(
                    show(item)
                    for item in operand
                )
                + ")"
            )

        return repr(operand)

    return "\n".join(
        " ".join(
            [
                instruction[0],
                *(
                    show(operand)
                    for operand
                    in instruction[1:]
                ),
            ]
        )
        for instruction in chunk
    )
