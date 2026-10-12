# Relation Model

This document describes relations: the first concrete structure of the
semantic graph.

Two problems motivate it. References to other entities inside values are
plain `EntityID`s that nothing tracks, so a rename or disappearance leaves
them dangling. And constraints can only describe one entity, although many
useful constraints relate several.

Status markers used in this document are:

- **Given**: already stated by other documents;
- **Decided**: agreed direction; later changes should be deliberate;
- **Provisional**: current direction, not fully settled;
- **Open**: options are listed; no direction is chosen.

## 1. Relations are entities

**Given** (semantic_graph.md §2): there is no fundamental semantic
distinction between nodes and edges.

**Decided:**

A relation is an entity whose value is a relation record. It has an
`EntityID`, versions, and continuity like any other entity, and it lives in
program state like any other value.

    entity a : 1
    entity b : 2
    entity r : Relation(kind="depends_on", roles={from: a, to: b})

The semantic graph is therefore the state itself. It has no nodes and edges,
only entities: a relation is an entity whose value relates other entities,
and any entity, including a relation, can be related (semantic_graph.md §2).
No separate store of relations is added.

Consequences:

- a relation can be referenced, versioned, transformed, and mapped like any
  entity;
- a relation can relate other relations, which gives relations about
  relations without extra machinery;
- parallel relations of the same kind between the same entities are
  distinct entities.

## 2. Relation records

**Decided:**

A relation record is a semantic value with:

    kind      a string naming the relation kind
    roles     role name → one EntityID, or an ordered tuple of EntityIDs
    payload   optional semantic value

Named roles make relations readable and order-independent: a relation of
arity three is `{caller: f, callee: g, site: s}`, not a positional triple.
An ordered tuple within one role covers genuinely ordered endpoints such as
arguments.

A relation may have no roles: a nullary relation, whose meaning is its kind
and payload alone. Code in graph form needs it for leaves such as a literal
(graph_form.md). The rule it replaces, at least one role, never ensured
that a relation relates something, since a role may hold an empty tuple.

Relation records are canonical like other records, so equal records have equal
identity. The kind is not interpreted by the core model; meaning comes from
the tools, constraints, and metaprograms that use it.

### Endpoint arity

From the endpoint arity audit (roadmap task 21). Canonical encoding keeps one
endpoint and a one-element tuple apart, so `{r: a}` and `{r: (a,)}` are
different records with different `VersionID`s. Whether the difference matters
depends on the family of relation.

**Provisional:**

Language relations (code nodes, `definition`, `links`): redundant as
information, retained deliberately as representation. Every role's arity
follows from its kind: `operations.py` for code roles, `lang` for link-target
roles (`target` and `cell` one endpoint, `targets` a tuple), one endpoint for
every `definition` and `links` role. An ordered role holds zero or more
endpoints, so it needs the tuple form anyway. One shape per role keeps every
reader free of a normalizing step, and normalizing would change the identity
of every relation that holds a one-element tuple. `tests/test_endpoint_arity.py`
checks the declared arity across both corpora and the states their runs
produce.

**Decided:**

Kinds the core does not interpret (constraint relations, a metaprogram's own
relations): semantically required. Kinds have no meaning in the core (section
9), so no schema says which roles are sequences and the record is the only
carrier. A constraint observes it (section 7): `Role("r", c)` checks `c`
against the endpoint's content for `{r: a}` and against a one-element tuple
for `{r: (a,)}`.

**Open:**

A tuple where the language expects one entity: a link target, or a `links`
relation's `function`. It has no meaning, only the Python API builds it, and
consumers disagree about it (below). Issue #110 chooses one rule.

Evidence: every reader in `shear/` of relation roles or of the link table
derived from them, found by searching for `.roles`, `.endpoints`,
`with_endpoints`, `Endpoint`, `role_subject`, `_decode_endpoint`, a
definition's `.links` and the builder's `scope`.

- Keep the forms apart: `Relation.__post_init__` (`_normalize_endpoint`),
  `Relation.canonical_node` through `canonical.canonicalize`, which encodes an
  `EntityID` and a tuple under different tags, and `relation_of`
  (`_decode_endpoint`).
- Flatten a role, or keep its shape without looking at it:
  - `Relation.endpoints` and `with_endpoints`, `check_relation_endpoints`,
    `relation_index`, the runtime's constraint lookup;
  - transformations (`_follow_relation_endpoints`,
    `_validate_relation_rewrites`, `rebase`);
  - `matching` (`shapes`, `match`), `continuity._operands`, `fold`
    (`children`), `lang._subtree` and `define`;
  - `hosted_bootstrap` (`seed`, `validation._endpoints`).

  `matching.shapes` gives `args: x` and `args: (x,)` the same shape, so
  continuity inference is sound only while arity follows from the kind.
- Assume the declared arity: `bytecode.lower`, `lang._collapse` and
  `_read_definition`, `continuity._node_at`, `fold`'s role reads,
  `hosted_bootstrap.descriptors` and `validation` (the `len` of a counted
  role). The descriptors splice ordered roles, so the self-hosted compiler
  never sees a role.
- Pass link tables through unchanged: `load`, `_edits_of`, `_Definition`,
  `reconcile` (`_graph_links`, `_link_targets`), `examples/vm.py`
  (`_source_links`).
- Branch on the form: `role_subject` (the Decided case above), and, for a
  tuple where one entity is expected:
  - code that names a tuple link becomes an `invalid` node that raises
    `LanguageError` when it runs (`_Builder.resolve`);
  - `linksof` omits the link (the machine's `LINKS` instruction in
    `machine.py`; vm_in_shear.md §1), and `render_program` omits it
    silently, so a text round trip drops it;
  - `load` finds a links relation through the flattened index and accepts
    `function: (f,)`, while `define` and `reconcile` reject it and the
    parser's `_merge` ignores it.

Within one kind and role of a language relation, no reader branches on the
form. Across both corpora (106 distinct states, 3,865 relation versions,
every operation kind except `invalid`), every language relation has its
declared arity. The predictions recorded before the audit held.

## 3. Referential integrity

**Decided:**

Every endpoint of every relation must be present in the same state. A state
with a dangling endpoint cannot be constructed.

This is a structural check, like the check that ownership refers only to
present entities. It evaluates nothing, so program state stays pure data.

Cycles are allowed: relations are ordinary references, and ordinary
references may form arbitrary cycles (ownership_model.md §2).

Recursive destruction follows the same rule. Destroying an owned subtree
fails if a relation outside the subtree points into it: the relation must be
changed or removed first, because relations are never removed implicitly
(section 5).

## 4. References inside ordinary values

**Decided:**

Raw `EntityID`s in ordinary values are data.

An `EntityID` can also appear inside an ordinary value, for example a list of
entity names held by a metaprogram. The options considered were:

    data
        raw EntityIDs in content are data, not references: no integrity
        check and no update across transformations. Relations are the only
        tracked references.

    forbidden
        raw EntityIDs may appear only inside model records such as relation
        records. Every reference to an entity is then tracked.

    implicit relations
        raw EntityIDs are treated as unnamed relations and tracked.

Data was chosen. Metaprograms need entity names as data, and implicit
relations would give every value hidden graph structure. The hazard of stale
names remains, but it becomes a visible choice: a reference that must stay
valid is written as a relation.

## 5. Relations across transformations

**Decided:**

Relations follow declared continuity.

A transformation can remove an entity that relations still point to, or
declare that an entity continues as a different one. A relation that the
transformation explicitly changes or removes is taken as given; its new
endpoints are checked (section 3). The question is what happens to a relation
the transformation does not change.

    explicit
        a transformation must itself change or remove every relation that
        points to an entity it removes; otherwise it is rejected.

    follow continuity
        an endpoint whose entity the transformation maps follows that
        mapping, as reference transfer does. It is rewritten to the single
        destination entity, including when several sources merge into it.
        A mapped endpoint whose entity disappears or splits cannot be
        followed, and the transformation is rejected unless it changes or
        removes that relation explicitly. An endpoint whose entity the
        transformation does not map is unchanged, like any preserved content.

Following continuity was chosen. It infers nothing: it follows declared
continuity, one step, exactly as `transfer_reference` does, and it keeps
renames cheap.

The rewrites are derived, but they are not hidden: the transformation result
lists every relation whose endpoints were rewritten, with the old and new
entity of each rewritten endpoint. The result checks that record against its
source and destination states.

A mapped endpoint follows its mapping even when its entity is still present.
In a swap (`a → b`, `b → a`) or a shift (`a → b`, `b → c`), entity `b` is
present afterwards but continues a different entity. A relation to `a`
therefore points to `b` afterwards, and a relation to `b` points to `a` or
`c`, never silently to whatever now carries the old name. Rewriting endpoints produces a new version of the relation;
like any entity, the relation's own continuity must still be declared by the
transformation (tools generate `r → r`).

Relations are never removed implicitly: a relation is an entity, and
removing it silently would be an undeclared disappearance. Ownership edges
follow declared continuity by the same rule; see transformation_model.md
section 13.

## 6. Ownership

**Decided:**

Ownership stays a separate relation in state for now.

Ownership has lifetime semantics and structural invariants (one owner,
acyclic, recursive destruction) that general relations do not. It already
follows declared continuity by the same rule as relations. How it becomes
part of the graph is deferred until the first program implementations need
it; see ownership_model.md section 13.

## 7. Constraints over several entities

**Decided:**

Direction.

**Open:**

The full set of constraint primitives.

A constraint relation carries a constraint as its payload. The payload, not
the kind, makes a relation a constraint relation, because the core gives
kinds no meaning (section 9). The subject of that constraint is the map from
role name to the current content of each endpoint: the value of an ordinary
entity, or the runtime content of a cell. A role holding a tuple of
endpoints maps to the tuple of their contents.

    Relation(kind="bound",
             roles={low: min_cell, high: max_cell},
             payload=<constraint over {low: ..., high: ...}>)

**Decided:**

An endpoint that owns entities contributes its owned
subtree with it, as the map `{"value": <its own content>, "owned": {child:
<the child's contribution>, ...}}`, recursively; an endpoint that owns
nothing contributes its content as before. Ownership bounds a composite,
so a constraint over the owner sees all of it. Code in graph form needs
this: a function's value holds only its definition, and its code lives in
the nodes it owns (graph_form.md), so a constraint over a function's code
is a constraint over the function, and it keeps holding when nodes are
edited, added or swapped.

The shape of an endpoint's contribution therefore depends on whether it owns
anything: plain content for an entity that owns nothing, the composite map
for one that does. A constraint written for a plain value stops matching
when its endpoint gains an owned child. Only owners of structure (functions,
whose nodes they own) have the composite shape today; cells own nothing. A
constraint over a kind of entity that may own or not must accept both
shapes, or name the shape it means. An opt-in for the subtree was considered
and not taken, since no program needs the plain shape of an owner.

Evaluation follows the existing rules for cells: it happens in a runtime,
with the runtime's evaluation context, and anything but `Satisfied` rejects.

- loading a version evaluates every constraint relation;
- a cell write re-evaluates every constraint relation that has that cell,
  or one of its owners, as an endpoint, and a rejected write leaves the
  cell unchanged;
- activation and trial runs evaluate every constraint relation of the
  destination state against the staged content.

The first primitives over a role map are a projection, `Role(name,
constraint)`, which is violated when the subject is not a map or lacks the
role, and `External` evaluators, which receive the whole canonical map.
Comparisons between roles are not yet a primitive; they are written as
evaluators.

## 8. Queries and indexes

**Decided:**

Finding the relations that touch an entity needs an index. An
index is derived implementation data: it is rebuilt from state content and
never contributes to `StateID` (README §29).

The decoded relation record of a value is derived data of the same kind: it
is decoded once and kept with the value, like its `VersionID`
(state_model.md §4), so a relation a transformation carries unchanged is
not decoded again.

## 9. What this does not add

Relations add structure, not a computational model. In line with the design
pressures in `priors.md`:

- transformations remain ordinary functions over immutable states; there is
  no graph rewriting and no pattern matching;
- there is no traversal language;
- the kind of a relation has no built-in meaning in the core.

## 10. Current implementation status

The Python reference model currently provides:

    Relation
        the relation record (kind, named roles, payload) as a semantic
        value; relation_of and relations_of read relations from values
        and states

    endpoint integrity
        state construction rejects a relation with an absent endpoint
        (DanglingRelation), which also makes destroy fail when a relation
        outside the destroyed subtree points into it

    relations across transformations
        applying a definition rewrites mapped endpoints of every relation
        the definition does not change, records each rewrite in the result
        (RelationRewrite), and rejects a mapped endpoint that disappears or
        splits (section 5)

    relation_index
        the derived index from entity to (relation, role) pairs

    constraint relations
        constraint_relations and Role; a runtime evaluates constraint
        relations when a version loads, when a write changes an endpoint
        cell or a cell an endpoint owns, and against the staged content of
        activation and trial runs, rejecting anything but Satisfied; an
        owner endpoint contributes its owned subtree (section 7)

## 11. Unresolved areas

- constraint primitives over role maps beyond `Role` and `External`
  (section 7);
- whether ownership becomes a relation kind (section 6);
- relation kinds with semantics the core must enforce;
- persistence and indexing strategy for large graphs.

## 12. Design principle

A reference that must stay valid is a relation. Relations are entities: they
have identity, versions, and declared continuity, they are checked
structurally in every state, and they follow continuity only where the
transformation declares it.
