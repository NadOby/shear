# Reference Model

This document defines the current semantic model of references in SHEAR.

A reference is a state-local, version-pinned handle to one semantic value.

## 1. Reference identity

A reference contains exactly three semantic components:

    StateID
    EntityID
    VersionID

Conceptually:

    Reference(S, E, V)

These components identify:

- the state in which the reference is valid;
- the conceptual entity being referenced;
- the exact semantic value version expected there.

## 2. Reference validity

A reference is valid against a state only when all three conditions hold:

1. the reference's `StateID` equals the state's `StateID`;
2. the referenced `EntityID` exists in the state;
3. the reference's `VersionID` equals the current version of that entity.

Failure of the state condition is a cross-state reference.

Failure of the entity condition means the entity is absent.

Failure of the version condition means the reference is stale. For a
reference made from the state it names, the version condition cannot fail
once the state condition holds (section 14).

## 3. State locality

References do not automatically follow entity identity across states.

Given:

    Reference(S₀, E, V)
    S₁ contains E

the reference remains a reference into `S₀`.

The existence of `E` in `S₁` does not rebind the reference.

Cross-state transfer must be explicit.

## 4. Reference transfer

Reference transfer follows an explicit continuity mapping through one
transformation.

Conceptually:

    Reference(S₀, E, V)
          +
    TransformResult(S₀ -> S₁)
          |
          v
    Reference(S₁, E', V')

Transfer is therefore a one-step operation.

Before following the mapping, the source reference must be valid against the
transformation's source state.

## 5. Transfer preconditions

The transfer operation requires:

    reference.state == transformation.source.id

The referenced entity must exist in the source state.

The reference version must equal the current source value version.

The three cases have distinct meanings:

    wrong StateID
        -> CrossStateReference

    absent EntityID
        -> missing source entity error

    wrong VersionID
        -> StaleReference

The third case arises only for a reference not made from that state
(section 14).

Only after these checks is the transformation mapping consulted.

## 6. Continuity result

The explicit mapping determines the transfer result.

A source entity mapped to no destinations cannot produce a destination
reference.

A source entity mapped to exactly one destination produces a destination
reference.

A source entity mapped to multiple destinations cannot be transferred without
an explicit choice.

The corresponding semantic outcomes are:

    zero destinations
        -> MissingEntityMapping

    one destination
        -> successful transfer

    multiple destinations
        -> AmbiguousEntityMapping

## 7. Destination version

A successful transfer produces a reference to the current value version of the
destination entity.

Therefore the destination reference is not required to preserve the source
`VersionID`.

Conceptually:

    Reference(S₀, E, V₀)
          |
          | continuity
          v
    Reference(S₁, E', V₁)

where `V₁` is the version currently present in `S₁`.

## 8. Transfer versus rebinding

Reference transfer and rebinding are different operations.

Transfer follows an explicitly declared continuity relation.

Rebinding explicitly chooses a destination entity without claiming that it is
the continuation of the source reference.

Conceptually:

    transfer
        = follow declared continuity

    rebind
        = explicitly choose a destination target

Rebinding therefore does not establish continuity.

Because rebinding asserts no relation to the original reference, the original
reference is neither validated nor consulted. A stale, cross-state, or
untransferable reference can be rebound; that is usually why rebinding is
needed.

## 9. One-step composition

Transformations are not implicitly composable for reference transfer.

Given:

    S₀ -> S₁
    S₁ -> S₂

a reference in `S₀` must be transferred first through the `S₀ -> S₁`
transformation and then through the `S₁ -> S₂` transformation.

The second transformation cannot directly consume the original `S₀`
reference.

This prevents ordinary mappings from becoming an implicit global history
graph.

## 10. Creation

A destination entity with no incoming mapping is a newly created destination
entity.

There is no synthetic source entity for creation.

Therefore a source reference cannot be transferred into a purely created
destination entity unless an explicit source-to-destination mapping exists.

## 11. Current implementation model

The Python reference model currently provides:

    Reference
    make_reference()
    project_entity()
    State.reference()
    State.resolve()
    transfer_reference()
    rebind_reference()

The exception types currently distinguish:

    CrossStateReference
    StaleReference
    MissingEntityMapping
    AmbiguousEntityMapping

These distinctions reflect semantic error categories rather than requiring a
particular Python exception hierarchy.

## 12. Unresolved areas

The following remain open:

- borrowing;
- alias analysis;
- lifetime analysis;
- raw pointer semantics;
- capability-backed references;
- references into moved representations;
- reference semantics in the eventual generalized graph model.

## 13. Design principle

A reference is not an ambient name and not merely an `EntityID`.

It is a capability to resolve one exact value in one exact semantic state.

Continuity across states must therefore be explicitly declared and explicitly
followed.

## 14. The version in a reference

From the reference version audit (roadmap task 22).

**Provisional:**

For a state-pinned reference, `VersionID` is redundant: it distinguishes
nothing that `(StateID, EntityID)` does not. It is not removed; the planned
`ref` values decide whether it goes or takes over from `StateID` (below).

Evidence:

- `StateID` hashes every entity's `VersionID` together with ownership
  (state_model.md section 4). A state therefore fixes the version of each
  entity it holds, up to SHA-256 collisions, which state identity already
  assumes away.
- Every producer derives the version from the named state: `State.reference`,
  `transfer_reference` (destination version, section 7) and
  `rebind_reference`. Two references that agree on state and entity agree on
  the version.
- `State.resolve` and `transfer_reference` check `StateID` first. Once it
  matches, the version check cannot fail for a produced reference.
  `StaleReference` needs a `Reference` built directly, or `make_reference`
  given a value the named state does not hold.
- Production code reads `Reference.version` only in those two checks.
  `Runtime.keep`, the transfer of kept references at activation and
  `TransformResult.mapped_entities` use the state and the entity. The
  language never makes or observes a `Reference`, a `VersionID` or a
  `StateID`; its function references are `EntityID`s (language_data.md
  section 3).
- `tests/test_reference_version.py` pins the first three points over
  generated states and transformations and over the continuity corpus. Three
  planted bugs are each caught: transfer keeping the source version, a
  `StateID` that ignores versions, and a reference made with a version its
  state does not hold.

Roles checked and not found:

- Integrity witness: the version catches a triple whose parts disagree, not
  a forged reference, since anyone can compute it from public content.
- Cache key: caches key on a value's own `VersionID` (bytecode chunks,
  native code in activation_model.md section 10, hosted artifacts by entity
  and version), never on a reference.
- Offline validation: checking a value against a reference without its
  state, or comparing versions across states, would resolve across states,
  which section 3 forbids. No caller does either.

**Open:**

For the `ref` values under the roadmap's Later. The owner's direction is a distinct `ref` value that is transferred at
activation along declared continuity and pins the old version when its
target disappears. With a `StateID` in the reference, pinning is a hold on
the runtime version of that state (activation_model.md sections 6 and 7),
which `Runtime.keep` already does for model references, and transfer derives
the new version from the destination. The version stays redundant in that
design.

It carries information only if one of these premises changes, and each is a
decision for the `ref` design:

1. A reference without a `StateID`, `(EntityID, VersionID)`, valid wherever
   the entity still has that version. It would survive activations that
   leave its target unchanged without being transferred; the version then
   does the pinning. It pins only the entity's own content: the `EntityID`s
   inside it (children, link targets) still need a state, which is why the
   hosted pipeline binds an artifact keyed by entity and version to its state
   and never infers compatibility from the version alone
   (hosted_pipeline.md section 7).
2. Resolution against a state other than the named one, relaxing section 3.
   In effect the same as 1.
3. A `StateID` that does not cover every entity's version, for example with
   partial states or structural sharing (state_model.md section 12).

A constraint for `ref` values held in semantic content, such as a code
literal, quoted code or a cell's declared initial content: a value cannot
contain the `StateID` of the state that holds it, because that identity
hashes the value. Likewise a value cannot contain its own entity's
`VersionID`, and such references cannot form a cycle. Only `EntityID`
references can be cyclic, as relation endpoints and today's function
references are. A reference in a cell's current content is outside
`StateID` (state_model.md section 4) and is not affected.
