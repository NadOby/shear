"""Callable construction and target resolution for the SHEAR machine.

Pure callable operations and active-state target checks live here.
The machine remains responsible for frame management and execution.
"""

from __future__ import annotations

from typing import Any, Mapping

from .canonical import CanonicalNode
from .closures import Closure, closure_value
from .identity import EntityID
from .lang import Function, LanguageError, _decode
from .machine_errors import _attach, _detail
from .runtime import Runtime


def _reference(value: Any) -> EntityID | None:
    if isinstance(value, EntityID):
        return value

    if isinstance(value, CanonicalNode) and value[1] == "entity_id":
        return EntityID(value[2])

    return None


def _callable(value: Any) -> EntityID | Closure | None:
    reference = _reference(value)
    return reference if reference is not None else closure_value(value)


def _function(owner: EntityID, params: Any, body: Any) -> Function:
    params, body = _decode(params), _decode(body)

    if not isinstance(params, tuple):
        raise LanguageError(
            f"{owner.value}: function parameters must be a tuple"
        )

    if not isinstance(body, tuple):
        raise LanguageError(
            f"{owner.value}: function body must be a tuple"
        )

    try:
        return Function(params, body)
    except (TypeError, ValueError) as exc:
        raise LanguageError(str(exc)) from exc


def _closure(
    owner: EntityID,
    body: EntityID,
    params: Any,
    capture_names: Any,
    env: Mapping[str, Any],
) -> Closure:
    params, capture_names = _decode(params), _decode(capture_names)

    if not isinstance(params, tuple):
        raise LanguageError(
            f"{owner.value}: closure parameters must be a tuple"
        )

    if not isinstance(capture_names, tuple):
        raise LanguageError(
            f"{owner.value}: closure captures must be a tuple"
        )

    if not all(
        isinstance(name, str) and name
        for name in capture_names
    ):
        raise LanguageError(
            f"{owner.value}: closure captures need non-empty string names"
        )

    captures = []

    for name in capture_names:
        if name not in env:
            raise LanguageError(
                f"{owner.value}: missing closure capture {name!r}"
            )

        captures.append((name, env[name]))

    try:
        return Closure(
            owner,
            body,
            params,
            tuple(captures),
        )
    except (TypeError, ValueError) as exc:
        raise LanguageError(
            f"{owner.value}: {exc}"
        ) from exc


def _resolved_call(
    runtime: Runtime,
    owner: EntityID,
    node: EntityID,
    target: EntityID | Closure,
    operation: str,
) -> tuple[EntityID, Closure | None]:
    active = runtime.active.state

    if isinstance(target, Closure):
        if not active.contains(target.owner):
            exc = LanguageError(
                f"{owner.value}: apply of closure whose owner "
                f"{target.owner.value} is not in the active state"
            )
            raise _attach(
                exc,
                "language",
                "absent",
                _detail(
                    entity=target.owner,
                    operation=operation,
                ),
                owner,
                node,
            )

        if not active.contains(target.body):
            exc = LanguageError(
                f"{owner.value}: apply of closure whose body "
                f"{target.body.value} is not in the active state"
            )
            raise _attach(
                exc,
                "language",
                "absent",
                _detail(
                    entity=target.body,
                    operation=operation,
                ),
                owner,
                node,
            )

        return target.owner, target

    if not active.contains(target):
        exc = LanguageError(
            f"{owner.value}: apply of {target.value}, "
            f"which is not in the active state"
        )
        raise _attach(
            exc,
            "language",
            "absent",
            _detail(
                entity=target,
                operation=operation,
            ),
            owner,
            node,
        )

    return target, None
