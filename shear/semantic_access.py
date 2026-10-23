"""Pure semantic-value access and construction for generic SHEAR operations.

These functions do not evaluate constraints or grant access to runtime state.
The VM is responsible for attaching language-error provenance.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .canonical import CanonicalNode, SemanticRecord, _node, canonicalize
from .cells import CellDeclaration
from .constraints import (
    AllOf, AnyOf, Constraint, External, IntRange, IsKind, Length,
    Not, OneOf, Role,
)
from .identity import EntityID, StateID, VersionID
from .relations import Relation


_RECORD_KINDS = frozenset({"cell", "constraint", "relation"})


def semantic_kind(value: Any) -> str:
    """Identify a value without expanding an already available container."""
    if isinstance(value, CanonicalNode):
        return value[1]
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, str):
        return "str"
    if isinstance(value, bytes):
        return "bytes"
    if isinstance(value, EntityID):
        return "entity_id"
    if isinstance(value, VersionID):
        return "version_id"
    if isinstance(value, StateID):
        return "state_id"
    if isinstance(value, tuple):
        return "tuple"
    if isinstance(value, list):
        return "list"
    if isinstance(value, Mapping):
        return "map"
    if isinstance(value, SemanticRecord):
        return value.canonical_node()[1]
    raise TypeError(f"unsupported semantic value: {type(value).__name__}")


def inspect(value: Any) -> tuple[str, Any]:
    """Return the semantic kind and the original, unexpanded value."""
    return semantic_kind(value), value


def _tuple(value: Any) -> tuple[Any, ...]:
    if isinstance(value, CanonicalNode):
        if value[1] == "tuple":
            return value[2]
        raise TypeError("expected a semantic tuple")
    if isinstance(value, tuple):
        return value
    raise TypeError("expected a semantic tuple")


def _constraint(value: Any) -> Constraint:
    if isinstance(value, Constraint):
        return value
    if isinstance(value, CanonicalNode) and value[1] == "constraint":
        return Constraint.from_content(value)
    raise TypeError("expected a typed semantic constraint")


def _entity(value: Any) -> EntityID:
    if isinstance(value, EntityID):
        return value
    if (
        isinstance(value, CanonicalNode)
        and value[1] == "entity_id"
        and isinstance(value[2], str)
    ):
        return EntityID(value[2])
    raise TypeError("relation endpoint must be a typed EntityID")


def _endpoint(value: Any) -> EntityID | tuple[EntityID, ...]:
    if semantic_kind(value) == "entity_id":
        return _entity(value)
    return tuple(_entity(item) for item in _tuple(value))


def _fields(value: Any) -> tuple[tuple[str, Any], ...]:
    if isinstance(value, SemanticRecord):
        value = value.canonical_node()
    kind = semantic_kind(value)
    if kind not in _RECORD_KINDS or not isinstance(value, CanonicalNode):
        raise TypeError("expected an indexable semantic record")
    content = value[2]
    if kind == "cell":
        return (("constraint", content[0]), ("initial", content[1]))
    if kind == "constraint":
        return (("form", content[0]), ("arguments", content[1:]))
    return (
        ("kind", content[0]),
        ("roles", content[1]),
        ("payload", content[2]),
    )


def _indexed(value: Any) -> tuple[str, Any]:
    kind = semantic_kind(value)
    if kind in _RECORD_KINDS:
        return kind, _fields(value)
    if isinstance(value, CanonicalNode):
        if kind in {"tuple", "list", "map", "bytes"}:
            return kind, value[2]
    elif kind in {"str", "bytes", "tuple", "list"}:
        return kind, value
    elif kind == "map":
        # Raw host maps are normalized before admitted execution. The
        # canonical map's stored index is reused on every VM access.
        return kind, canonicalize(value)[2]
    raise TypeError(f"len/item/slice do not support {kind}")


def sequence_length(value: Any) -> int:
    kind, content = _indexed(value)
    if kind == "bytes" and isinstance(content, str):
        return len(content) // 2
    return len(content)


def _index(index: Any, length: int) -> int:
    if isinstance(index, bool) or not isinstance(index, int):
        raise TypeError("index must be an integer")
    if index < 0 or index >= length:
        raise ValueError("index outside semantic sequence")
    return index


def sequence_item(value: Any, index: Any) -> Any:
    kind, content = _indexed(value)
    if isinstance(index, str):
        if kind not in _RECORD_KINDS:
            raise TypeError("named field access requires a semantic record")
        for field_name, field_value in content:
            if field_name == index:
                return field_value
        raise ValueError(f"unknown semantic record field: {index!r}")
    length = sequence_length(value) if kind == "bytes" else len(content)
    index = _index(index, length)
    if kind == "bytes" and isinstance(content, str):
        return int(content[2 * index:2 * index + 2], 16)
    return content[index]


def sequence_slice(value: Any, start: Any, stop: Any) -> Any:
    kind, content = _indexed(value)
    length = sequence_length(value) if kind == "bytes" else len(content)
    if (
        isinstance(start, bool)
        or not isinstance(start, int)
        or isinstance(stop, bool)
        or not isinstance(stop, int)
    ):
        raise TypeError("slice bounds must be integers")
    if not 0 <= start <= stop <= length:
        raise ValueError("slice outside semantic sequence")
    if kind == "bytes" and isinstance(content, str):
        return _node("bytes", content[2 * start:2 * stop])
    if kind == "list" and isinstance(value, CanonicalNode):
        return _node("list", content[start:stop])
    if kind in _RECORD_KINDS or kind == "map":
        return tuple(content[start:stop])
    return content[start:stop]


def _make_constraint(form: Any, args: tuple[Any, ...]) -> Constraint:
    if not isinstance(form, str):
        raise TypeError("constraint form must be a string")
    if form in {"is_kind", "one_of", "all_of", "any_of", "not", "external"}:
        count = 1
    elif form in {"int_range", "length", "role"}:
        count = 2
    else:
        raise ValueError(f"unknown constraint form: {form!r}")
    if len(args) != count:
        raise ValueError("incorrect constraint argument count")
    if form == "is_kind":
        return IsKind(args[0])
    if form == "int_range":
        return IntRange(*args)
    if form == "length":
        return Length(*args)
    if form == "one_of":
        return OneOf(*_tuple(args[0]))
    if form == "all_of":
        return AllOf(*(_constraint(part) for part in _tuple(args[0])))
    if form == "any_of":
        return AnyOf(*(_constraint(part) for part in _tuple(args[0])))
    if form == "not":
        return Not(_constraint(args[0]))
    if form == "role":
        return Role(args[0], _constraint(args[1]))
    return External(args[0])


def record(kind: Any, fields: Any) -> CanonicalNode:
    """Construct a typed semantic record from VM-computed public fields.

    Pure existing model constructors enforce normalization and validation.
    This is a value constructor, never a constraint evaluator.
    """
    if not isinstance(kind, str) or kind not in _RECORD_KINDS:
        raise ValueError(f"unsupported semantic record kind: {kind!r}")
    values = _tuple(fields)
    if kind == "cell":
        if len(values) != 2:
            raise ValueError("cell requires two public fields")
        result = CellDeclaration(_constraint(values[0]), values[1])
    elif kind == "constraint":
        if len(values) != 2:
            raise ValueError("constraint requires two public fields")
        result = _make_constraint(values[0], _tuple(values[1]))
    else:
        if len(values) != 3:
            raise ValueError("relation requires three public fields")
        roles: dict[str, EntityID | tuple[EntityID, ...]] = {}
        for pair in _tuple(values[1]):
            entry = _tuple(pair)
            if len(entry) != 2:
                raise ValueError("relation role must be a pair")
            name, endpoint = entry
            if not isinstance(name, str) or not name:
                raise TypeError("role name must be a non-empty string")
            if name in roles:
                raise ValueError("duplicate relation role")
            roles[name] = _endpoint(endpoint)
        result = Relation(values[0], roles, values[2])
    return result.canonical_node()
