"""Generic semantic instructions executed by the SHEAR machine.

This module translates public semantic-value validation into structured
language failures. It does not evaluate constraints, open runtime objects,
or grant effects. The machine owns its stack, frames, and error provenance.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from . import semantic_access


ARITY: Mapping[str, int] = MappingProxyType({
    "INSPECT": 1,
    "RECORD": 2,
    "LEN": 1,
    "ITEM": 2,
    "SLICE": 3,
})

_INDEXABLE = frozenset({
    "str", "bytes", "tuple", "list", "map",
    "cell", "constraint", "relation",
})


class SemanticFailure(Exception):
    """A rejected generic value operation, without machine provenance."""

    def __init__(
        self,
        kind: str,
        detail: tuple[tuple[str, Any], ...],
        message: str,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.detail = detail


def _detail(**values: Any) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted(values.items()))


def _failure(
    operation: str,
    args: tuple[Any, ...],
    error: TypeError | ValueError,
) -> SemanticFailure:
    name = operation.lower()
    message = str(error)

    if operation == "RECORD":
        return SemanticFailure(
            "wrong_kind" if isinstance(error, TypeError) else "malformed",
            _detail(operation=name, problem=message),
            message,
        )

    if operation == "INSPECT":
        return SemanticFailure(
            "wrong_kind",
            _detail(operation=name, problem=message),
            message,
        )

    operand = args[0]
    kind = semantic_access.semantic_kind(operand)
    if kind not in _INDEXABLE:
        return SemanticFailure(
            "wrong_kind",
            _detail(expected="indexable", got=kind, operation=name),
            message,
        )

    if isinstance(error, TypeError):
        if operation in ("ITEM", "SLICE"):
            for bound in args[1:]:
                if not isinstance(bound, int) or isinstance(bound, bool):
                    if not (operation == "ITEM" and isinstance(bound, str)
                            and kind in {"cell", "constraint", "relation"}):
                        return SemanticFailure(
                            "wrong_kind",
                            _detail(
                                expected="int",
                                got=semantic_access.semantic_kind(bound),
                                operation=name,
                            ),
                            message,
                        )
        return SemanticFailure(
            "wrong_kind",
            _detail(operation=name, problem=message),
            message,
        )

    if operation == "ITEM":
        if isinstance(args[1], str):
            return SemanticFailure(
                "out_of_range",
                _detail(field=args[1], operation=name),
                message,
            )
        return SemanticFailure(
            "out_of_range",
            _detail(
                index=args[1],
                length=semantic_access.sequence_length(operand),
                operation=name,
            ),
            message,
        )

    if operation == "SLICE":
        return SemanticFailure(
            "out_of_range",
            _detail(
                length=semantic_access.sequence_length(operand),
                operation=name,
                start=args[1],
                stop=args[2],
            ),
            message,
        )

    return SemanticFailure(
        "malformed",
        _detail(operation=name, problem=message),
        message,
    )


def execute(operation: str, *args: Any) -> Any:
    """Execute one approved value instruction on already evaluated operands.

    Validation failures are converted to structured failures for the machine
    to stamp with the active function, node, and run token. Unexpected host
    failures escape rather than becoming catchable language failures.
    """
    if operation not in ARITY:
        raise ValueError(f"unsupported semantic instruction {operation!r}")
    if len(args) != ARITY[operation]:
        raise ValueError("incorrect semantic instruction stack arity")

    try:
        if operation == "INSPECT":
            return semantic_access.inspect(args[0])
        if operation == "RECORD":
            return semantic_access.record(args[0], args[1])
        if operation == "LEN":
            return semantic_access.sequence_length(args[0])
        if operation == "ITEM":
            return semantic_access.sequence_item(args[0], args[1])
        return semantic_access.sequence_slice(args[0], args[1], args[2])
    except (TypeError, ValueError) as error:
        raise _failure(operation, args, error) from error
