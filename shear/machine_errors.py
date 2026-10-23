"""Error provenance and runtime failure classification for the SHEAR VM.

The run token is shared with the machine so only failures originating
inside the active run may be intercepted by a SHEAR catch handler.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from .constraints import _is_host_failure
from .identity import EntityID
from .lang import LanguageError
from .runtime import (
    ActivationConflict,
    ActivationRejected,
    CellContentRejected,
    RelationConstraintRejected,
)


_RUN: ContextVar[object | None] = ContextVar("shear_run", default=None)


class _Raised(LanguageError):
    """An uncaught program ``raise``."""


_Raised.__name__ = "Raised"
_Raised.__qualname__ = "Raised"


def _detail(**fields: Any) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted(fields.items()))


def _attach(
    exc: BaseException,
    origin: str,
    kind: str,
    detail: Any,
    function: EntityID,
    node: EntityID,
) -> BaseException:
    if not hasattr(exc, "error"):
        exc.error = (origin, kind, detail, (function, node))
        exc._shear_run = _RUN.get()
    return exc


def _attach_runtime(
    exc: BaseException,
    function: EntityID,
    node: EntityID,
    operation: str,
) -> BaseException:
    if _is_host_failure(exc) or hasattr(exc, "error"):
        return exc

    if isinstance(exc, CellContentRejected):
        return _attach(
            exc,
            "runtime",
            "cell_rejected",
            _detail(
                cell=exc.cell,
                constraint=exc.result.value,
                operation=operation,
            ),
            function,
            node,
        )

    if isinstance(exc, RelationConstraintRejected):
        return _attach(
            exc,
            "runtime",
            "relation_rejected",
            _detail(
                constraint=exc.result.value,
                operation=operation,
                relation=exc.relation,
            ),
            function,
            node,
        )

    if isinstance(exc, ActivationConflict):
        return _attach(
            exc,
            "runtime",
            "activation_conflict",
            _detail(reason=exc.reason),
            function,
            node,
        )

    if isinstance(exc, ActivationRejected):
        fields: dict[str, Any] = {"reason": exc.reason}

        if exc.cell is not None:
            fields["cell"] = exc.cell

        if exc.result is not None:
            fields["constraint"] = exc.result.value

        if exc.relation is not None:
            fields["relation"] = exc.relation

        return _attach(
            exc,
            "runtime",
            "activation_rejected",
            _detail(**fields),
            function,
            node,
        )

    return exc
