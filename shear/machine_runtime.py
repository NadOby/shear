"""Activation and program-definition helpers for the SHEAR machine.

These helpers validate requested edits and preserve language-error
provenance. Runtime commit, trial execution, and frame management remain
under the machine's control.
"""

from __future__ import annotations

from typing import Any, Mapping

from .identity import EntityID
from .lang import (
    LanguageError,
    _definition_of,
    _function_value,
    define,
)
from .machine_errors import _attach, _detail
from .runtime import Runtime


def _activation_pairs(
    runtime: Runtime,
    owner: EntityID,
    node: EntityID,
    entries: tuple[Any, ...],
    targets: tuple[EntityID, ...],
    values: list[Any],
    op: str,
) -> tuple[Any, dict]:
    active = runtime.active.state
    resolved = iter(targets)
    seen: set[Any] = set()
    edits: dict[EntityID | tuple[EntityID, str], Any] = {}

    for (name, problem), value in zip(entries, values):
        if problem is not None:
            exc = LanguageError(
                f"{owner.value}: {problem}"
            )
            raise _attach(
                exc,
                "language",
                "malformed",
                _detail(operation=op, problem=problem),
                owner,
                node,
            )

        target = next(resolved)
        label = name[1] if isinstance(name, tuple) else None
        key = (
            (target, label)
            if label is not None
            else target
        )

        if key in seen:
            problem = (
                f"{op} target appears twice: {target.value}"
            )
            exc = LanguageError(
                f"{owner.value}: {problem}"
            )
            raise _attach(
                exc,
                "language",
                "malformed",
                _detail(operation=op, problem=problem),
                owner,
                node,
            )

        seen.add(key)

        if target not in active.values:
            exc = LanguageError(
                f"{owner.value}: {op} target does not exist: "
                f"{target.value}"
            )
            raise _attach(
                exc,
                "language",
                "absent",
                _detail(entity=target, operation=op),
                owner,
                node,
            )

        if _definition_of(active.values[target]) is None:
            exc = LanguageError(
                f"{owner.value}: {op} target is not a function: "
                f"{target.value}"
            )
            raise _attach(
                exc,
                "language",
                "not_a_function",
                _detail(entity=target, operation=op),
                owner,
                node,
            )

        function = _function_value(value)

        if label is not None:
            if function is not None:
                problem = (
                    f"{op} value is not an expression: {target.value}"
                )
                exc = LanguageError(
                    f"{owner.value}: {problem}"
                )
                raise _attach(
                    exc,
                    "language",
                    "malformed",
                    _detail(operation=op, problem=problem),
                    owner,
                    node,
                )

            edits[key] = value
        else:
            if function is None:
                problem = (
                    f"{op} value is not a function: {target.value}"
                )
                exc = LanguageError(
                    f"{owner.value}: {problem}"
                )
                raise _attach(
                    exc,
                    "language",
                    "malformed",
                    _detail(operation=op, problem=problem),
                    owner,
                    node,
                )

            edits[key] = function

    return active, edits


def _define_for_operation(
    active: Any,
    edits: Mapping,
    operation: str,
    function: EntityID,
    node: EntityID,
) -> Any:
    try:
        return define(
            active,
            edits,
        )
    except LanguageError as exc:
        _attach(
            exc,
            "language",
            "malformed",
            _detail(
                operation=operation,
                problem=str(exc),
            ),
            function,
            node,
        )
        raise
