"""Authenticated ordinary-SHEAR inspection of generic canonical projections.

No constraint predicate is executed in Python. This module does not add
language operations, VM instructions, semantic identities or host lowering.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .canonical import CanonicalNode, canonical_serialize, canonicalize
from .canonical_projection import ProjectionError, project, unproject
from .identity import EntityID
from .lang import Function, links, load
from .state import State
from .values import Value
from .hosted_bootstrap.restricted import RestrictedExecutor

INSPECT = EntityID("t123.projection.inspect")
EQUAL = EntityID("t123.projection.equal")
SELECT = EntityID("t123.projection.select")
LINKS = EntityID("t123.projection.select.links")
ENTRIES = frozenset({INSPECT, EQUAL, SELECT})
_MARKER = "t123:projected-subtree"
_TAGS = frozenset({"scalar", "sequence", "node", "hex-pairs"})


def _lit(value):
    return ("lit", value)


def _arg(name):
    return ("arg", name)


def _item(value, index):
    return ("item", value, index)


def _eq(left, right):
    return ("eq", left, right)


def _inspection():
    value = _arg("value")
    kind = _item(value, _lit(1))
    payload = _item(value, _lit(2))
    nested_length = ("len", _item(payload, _lit(2)))
    length = _lit(None)
    for name in ("map", "list", "tuple", "bytes"):
        length = ("if", _eq(kind, _lit(name)), nested_length, length)
    length = ("if", _eq(kind, _lit("str")), ("len", payload), length)
    return ("tuple", kind, length, value)


def _selection():
    value = _arg("value")
    path = _arg("path")
    offset = _arg("offset")
    index = _item(path, offset)
    next_offset = ("add", offset, _lit(1))

    def descend(child):
        return ("call", "loop", child, path, next_offset)

    node = (
        "if", _eq(index, _lit(0)), _lit("__type__"),
        ("if", _eq(index, _lit(1)), _item(value, _lit(1)),
         descend(_item(value, _lit(2)))),
    )
    sequence = descend(_item(_item(value, _lit(2)), index))
    invalid = (
        "raise", _lit("invalid_projection_path"),
        _lit("path extends beyond a canonical scalar"),
    )
    return (
        "if", _eq(offset, ("len", path)),
        ("tuple", _lit(_MARKER), value),
        ("if", _eq(_item(value, _lit(0)), _lit("node")), node,
         ("if", _eq(_item(value, _lit(0)), _lit("sequence")),
          sequence, invalid)),
    )


def _source():
    entities = {
        INSPECT: Function(("value",), _inspection()),
        EQUAL: Function(("left", "right"), _eq(
            _arg("left"), _arg("right"),
        )),
        SELECT: Function(("value", "path", "offset"), _selection()),
        LINKS: links(SELECT, loop=SELECT),
    }
    return load(State.create({
        entity: Value.create(entity, content)
        for entity, content in entities.items()
    }))


@lru_cache(maxsize=1)
def projection_bundle():
    """Prepare once, before any admission guard forbids host lowering."""
    executor = RestrictedExecutor()
    deployment = executor.deploy(_source(), compiler_generation=1)
    return executor, deployment


def _run(entry: EntityID, *arguments):
    executor, deployment = projection_bundle()
    return executor.run(deployment, entry, *arguments)


def _is_projection(value: Any) -> bool:
    if isinstance(value, CanonicalNode):
        if value[1] != "tuple":
            return False
        value = value[2]
    return (
        type(value) is tuple
        and len(value) == 3
        and type(value[0]) is str
        and value[0] in _TAGS
    )


def _rejection(operation: str, output: Any, reason: str):
    error = ProjectionError(f"{operation}: {reason}")
    error.projection_operation = operation
    error.rejected_vm_output = output
    return error


def inspect_projection(value: Any) -> tuple:
    original = canonicalize(value)
    output = _run(INSPECT, project(value))
    try:
        if not isinstance(output, tuple) or len(output) != 3:
            raise ProjectionError("expected a three-field VM result")
        kind, length, transported = output
        if type(kind) is not str:
            raise ProjectionError("invalid kind in VM result")
        if length is not None and type(length) is not int:
            raise ProjectionError("invalid length in VM result")
        reconstructed = (
            unproject(transported)
            if _is_projection(transported) else transported
        )
        if canonical_serialize(reconstructed) != canonical_serialize(original):
            raise ProjectionError("VM reconstruction changes canonical content")
    except (ValueError, TypeError) as exc:
        raise _rejection(
            "inspect_projection", output, str(exc),
        ) from exc
    return kind, length, reconstructed


def equal_projection(left: Any, right: Any) -> bool:
    result = _run(EQUAL, project(left), project(right))
    if type(result) is not bool:
        raise _rejection("equal_projection", result, "VM returned non-bool")
    return result


def select_projection(value: Any, path: tuple[int, ...]) -> Any:
    if not isinstance(path, tuple) or any(
        type(index) is not int or index < 0 for index in path
    ):
        raise ValueError("projection path needs nonnegative integer indices")
    output = _run(SELECT, project(value), path, 0)
    try:
        if (
            type(output) is tuple
            and len(output) == 2
            and output[0] == _MARKER
        ):
            return unproject(output[1])
        return canonicalize(output)
    except (ValueError, TypeError) as exc:
        raise _rejection(
            "select_projection", output, str(exc),
        ) from exc
