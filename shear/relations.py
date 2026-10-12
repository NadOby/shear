"""Relations: entities whose values are relation records (relation_model.md)."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Callable, Mapping

from .canonical import (
    CanonicalNode,
    SemanticRecord,
    _node,
    canonical_serialize,
    canonicalize,
)
from .constraints import Constraint
from .identity import EntityID
from .values import Value

if TYPE_CHECKING:
    from .state import State

Endpoint = EntityID | tuple[EntityID, ...]


class DanglingRelation(ValueError):
    """A relation endpoint is absent, or could not follow continuity."""


def _normalize_endpoint(role: str, endpoint: Any) -> Endpoint:
    if isinstance(endpoint, EntityID):
        return endpoint

    if isinstance(endpoint, (tuple, list)):
        endpoints = tuple(endpoint)

        if all(isinstance(item, EntityID) for item in endpoints):
            return endpoints

    raise TypeError(
        f"role {role!r} must hold an EntityID or a sequence of EntityIDs"
    )


@dataclass(frozen=True, eq=False)
class Relation(SemanticRecord):
    """A relation record: the value of a relation entity.

    ``roles`` maps role names to one endpoint entity, or to an ordered tuple
    of endpoint entities. Role order does not matter; order within a tuple
    does. A relation may have no roles at all (a nullary relation, such as
    a leaf of code in graph form). The kind has no built-in meaning in the
    core model.
    """

    kind: str
    roles: Mapping[str, Endpoint]
    payload: Any = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind:
            raise TypeError("relation kind must be a non-empty string")

        if not isinstance(self.roles, Mapping):
            raise TypeError("relation roles must be a mapping")

        roles = {}

        for role, endpoint in self.roles.items():
            if not isinstance(role, str) or not role:
                raise TypeError("role names must be non-empty strings")

            roles[role] = _normalize_endpoint(role, endpoint)

        object.__setattr__(
            self,
            "roles",
            MappingProxyType(dict(sorted(roles.items()))),
        )
        object.__setattr__(
            self,
            "payload",
            canonicalize(self.payload),
        )

    @property
    def endpoints(self) -> frozenset[EntityID]:
        """Every entity this relation points to."""

        found: set[EntityID] = set()

        for endpoint in self.roles.values():
            if isinstance(endpoint, EntityID):
                found.add(endpoint)
            else:
                found.update(endpoint)

        return frozenset(found)

    def with_endpoints(
        self,
        replacement: Mapping[EntityID, EntityID],
    ) -> "Relation":
        """Return this relation with endpoints replaced where given."""

        def replace(endpoint: Endpoint) -> Endpoint:
            if isinstance(endpoint, EntityID):
                return replacement.get(endpoint, endpoint)

            return tuple(replacement.get(item, item) for item in endpoint)

        return Relation(
            self.kind,
            {role: replace(endpoint) for role, endpoint in self.roles.items()},
            self.payload,
        )

    def canonical_node(self) -> CanonicalNode:
        return _node(
            "relation",
            (
                self.kind,
                tuple(
                    (role, canonicalize(endpoint))
                    for role, endpoint in self.roles.items()
                ),
                self.payload,
            ),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Relation):
            return NotImplemented

        return canonical_serialize(self) == canonical_serialize(other)

    def __hash__(self) -> int:
        return hash(canonical_serialize(self))


def _decode_endpoint(node: CanonicalNode) -> Endpoint:
    if node[1] == "entity_id":
        return EntityID(node[2])

    return tuple(EntityID(item[2]) for item in node[2])


_UNDECODED = object()


def relation_of(value: Value) -> Relation | None:
    """Return the relation record held by a value, if it is a relation.

    The record is decoded once and kept with the value, like its
    ``VersionID`` (state_model.md section 4): a value carried unchanged
    into a new state is not decoded again by the integrity check, endpoint
    following, or constraint lookup of that state. Values and relation
    records are immutable, so the kept record can never disagree with the
    value's content.
    """

    cached = value.__dict__.get("_relation", _UNDECODED)

    if cached is not _UNDECODED:
        return cached

    content = value.content
    record = None

    if isinstance(content, CanonicalNode) and content[1] == "relation":
        kind, roles, payload = content[2]

        record = Relation(
            kind,
            {role: _decode_endpoint(endpoint) for role, endpoint in roles},
            payload,
        )

    object.__setattr__(value, "_relation", record)

    return record


def relations_of(state: State) -> Mapping[EntityID, Relation]:
    """Return the relation entities of a state, in canonical order."""

    relations = {}

    for entity in sorted(state.values):
        relation = relation_of(state.values[entity])

        if relation is not None:
            relations[entity] = relation

    return MappingProxyType(relations)


def check_relation_endpoints(
    values: Mapping[EntityID, Value],
) -> None:
    """Reject any relation whose endpoints are not all present."""

    for entity, value in values.items():
        relation = relation_of(value)

        if relation is None:
            continue

        # Look each endpoint up in ``values``: subtracting ``values.keys()``
        # from the endpoints would hash every entity of the state once per
        # relation.
        missing = sorted(
            endpoint
            for endpoint in relation.endpoints
            if endpoint not in values
        )

        if missing:
            raise DanglingRelation(
                f"relation {entity.value} points to absent "
                f"{', '.join(item.value for item in missing)}"
            )


def relation_index(
    state: State,
) -> Mapping[EntityID, tuple[tuple[EntityID, str], ...]]:
    """Derived index: for each entity, the (relation, role) pairs touching it.

    The index is implementation data rebuilt from state content; it never
    contributes to ``StateID``.
    """

    index: dict[EntityID, list[tuple[EntityID, str]]] = {}

    for relation_entity, relation in relations_of(state).items():
        for role, endpoint in relation.roles.items():
            targets = (
                (endpoint,)
                if isinstance(endpoint, EntityID)
                else endpoint
            )

            for target in targets:
                pairs = index.setdefault(target, [])

                if (relation_entity, role) not in pairs:
                    pairs.append((relation_entity, role))

    return MappingProxyType({
        entity: tuple(sorted(pairs))
        for entity, pairs in sorted(index.items())
    })


def constraint_relations(
    state: State,
) -> Mapping[EntityID, tuple[Relation, Constraint]]:
    """Relations with an endpoint whose payload is a constraint
    (relation_model.md §7).

    The payload, not the kind, makes a relation a constraint relation: the
    kind has no built-in meaning in the core. A relation without endpoints
    constrains nothing, so its payload stays data; code in graph form keeps
    literals there.
    """

    found = {}

    for entity, relation in relations_of(state).items():
        payload = relation.payload

        if (
            isinstance(payload, CanonicalNode)
            and payload[1] == "constraint"
            and relation.endpoints
        ):
            found[entity] = (relation, Constraint.from_content(payload))

    return MappingProxyType(found)


def role_subject(
    relation: Relation,
    content_of: Callable[[EntityID], Any],
) -> dict[str, Any]:
    """The subject of a constraint relation: role name to endpoint content."""

    return {
        role: (
            content_of(endpoint)
            if isinstance(endpoint, EntityID)
            else tuple(content_of(item) for item in endpoint)
        )
        for role, endpoint in relation.roles.items()
    }
