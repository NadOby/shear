"""Lossless, immutable canonical-content transport for ordinary SHEAR code.

Projection is structural, not constraint evaluation. Every projected value
is made entirely of ordinary tuples and scalar literals, so the existing
SHEAR ``item``, ``len`` and ``eq`` operations can inspect it after normal
argument canonicalization. Projected contents never replace stored content
or participate in semantic identity.

The outer tuple is always (representation, semantic_kind, payload).
A canonical tagged node has representation ``node``; a raw tuple embedded
inside a record has representation ``sequence``. This distinction prevents
an ordinary user tuple from masquerading as a CanonicalNode.
"""

from __future__ import annotations

from string import hexdigits
from typing import Any

from .canonical import CanonicalNode, _node, canonicalize


class ProjectionError(ValueError):
    """A VM-produced projection is structurally invalid."""


def project(value: Any) -> tuple:
    """Project supported canonical content without changing its identity."""
    return _encode(canonicalize(value))


def _encode(value: Any) -> tuple:
    if isinstance(value, CanonicalNode):
        kind, payload = value[1], value[2]
        if kind == "bytes":
            if not isinstance(payload, str) or len(payload) % 2:
                raise ProjectionError("invalid canonical byte payload")
            if any(char not in hexdigits for char in payload):
                raise ProjectionError("invalid canonical hex digit")
            return (
                "node", kind,
                ("hex-pairs", "bytes", tuple(
                    payload[index:index + 2]
                    for index in range(0, len(payload), 2)
                )),
            )
        return ("node", kind, _encode(payload))

    if type(value) is tuple:
        return ("sequence", "tuple", tuple(_encode(item) for item in value))

    if value is None:
        return ("scalar", "none", None)
    if type(value) is bool:
        return ("scalar", "bool", value)
    if type(value) is int:
        return ("scalar", "int", value)
    if type(value) is str:
        return ("scalar", "str", tuple(value))

    raise TypeError(f"unsupported canonical component: {type(value).__name__}")


def _tuple(value: Any) -> tuple:
    """Unwrap an ordinary tuple, including one canonicalized by the VM."""
    if isinstance(value, CanonicalNode):
        if value[1] != "tuple":
            raise ProjectionError("expected an inspectable tuple")
        return value[2]
    if type(value) is tuple:
        return value
    raise ProjectionError("expected an inspectable tuple")


def unproject(value: Any) -> Any:
    """Rebuild canonical content from a projected VM result, fail-closed."""
    fields = _tuple(value)
    if len(fields) != 3:
        raise ProjectionError("projection must have three fields")

    representation, kind, payload = fields
    if type(representation) is not str or type(kind) is not str:
        raise ProjectionError("invalid projection tags")

    if representation == "node":
        if not kind:
            raise ProjectionError("empty canonical kind")
        if kind == "bytes":
            if _tuple(payload)[:2] != ("hex-pairs", "bytes"):
                raise ProjectionError("invalid byte projection")
        return _node(kind, unproject(payload))

    if representation == "sequence":
        if kind != "tuple":
            raise ProjectionError("invalid sequence kind")
        return tuple(unproject(item) for item in _tuple(payload))

    if representation == "hex-pairs":
        if kind != "bytes":
            raise ProjectionError("invalid byte-pair kind")
        pairs = _tuple(payload)
        if any(
            type(pair) is not str
            or len(pair) != 2
            or any(char not in hexdigits for char in pair)
            for pair in pairs
        ):
            raise ProjectionError("invalid byte pair")
        return "".join(pairs)

    if representation == "scalar":
        if kind == "none" and payload is None:
            return None
        if kind == "bool" and type(payload) is bool:
            return payload
        if kind == "int" and type(payload) is int:
            return payload
        if kind == "str":
            chars = _tuple(payload)
            if all(type(char) is str and len(char) == 1 for char in chars):
                return "".join(chars)
        raise ProjectionError("invalid scalar payload")

    raise ProjectionError("unknown projection representation")
