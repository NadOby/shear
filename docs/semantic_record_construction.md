# Generic Semantic-Record Construction – C10 Proposal

Status: Proposed D123-8 – independent Review and owner approval required.
Issue: GH-123.
Branch: `task/123-complete-constraints`.
Inspection baseline: `8cedf3eb21ef797fa9ea3e02aff9130162c3881a`.

## 1. Problem

The approved D123-7c interface can inspect existing
semantic values but cannot construct new typed semantic
records from values computed at runtime.

Existing tuple construction produces a semantic tuple,
not a Cell, Constraint or Relation record.

Host-side `Constraint.from_content()` is not an admitted
SHEAR operation. Adapter-side reconstruction would not
satisfy the approved T5 contract.

The required distinction is between computing a semantic
value in SHEAR and converting a host-produced answer into
a semantic value after execution.

C10 remains unresolved until genuine admitted construction
and the frozen T5 reconstruction evidence are demonstrated.

## 2. Proposed decision D123-8

Introduce one generic, pure semantic-record constructor.

Input form:

    ("record", kind_expression, fields_expression)

Proposed text syntax:

    record(kind_expression, fields_expression)

The two arguments are ordinary evaluated SHEAR expressions.

`kind_expression` must evaluate to a supported semantic-record
kind string.

`fields_expression` must evaluate to an ordinary tuple
containing the fields defined by that kind's public schema.

The result is an immutable semantic value of the specified
record kind, with its existing canonical identity.

Initially supported kinds:

- cell
- constraint
- relation

Closure reconstruction is not authorized.

The operation does not evaluate constraints, traverse graph
entities, read live runtime state or install records in
program state.

It introduces one generic public operation, not a family
of constraint-specific operations.

This operation requires explicit owner authorization.
It is not implied by D123-7c.

## 3. Construction schemas

Construction uses the public field schemas approved by
`docs/semantic_inspection.md`.

### Cell

    record("cell", (constraint, initial))

`constraint` must be an existing semantic constraint value.

`initial` is canonical immutable semantic content.

Construction creates a cell declaration value. It does
not create live cell storage, read existing runtime cells
or mutate program state.

Existing Cell declaration normalization and identity
rules remain unchanged.

### Constraint

    record("constraint", (form, arguments))

`form` must be one of the nine existing constraint forms.

`arguments` follows the exact approved schema:

| Form | arguments |
|---|---|
| is_kind | `(kind,)` |
| int_range | `(minimum, maximum)` |
| length | `(minimum, maximum)` |
| one_of | `(values,)` |
| all_of | `(parts,)` |
| any_of | `(parts,)` |
| not | `(part,)` |
| role | `(role_name, part)` |
| external | `(name,)` |

The outer arguments tuple must not flatten nested values
or composite constraint collections.

Nested constraints must retain their semantic constraint
kind. Ordinary tuples imitating canonical record tags
must not be accepted as typed constraint values.

Use the existing normative constructor validation:

- Exact kind and bound validation.
- Bool/int distinctions.
- Canonical deduplication and ordering for OneOf.
- Canonical deduplication and ordering for AllOf/AnyOf.
- Correct empty-composition identities.
- Typed nested operands for Not and Role.
- Existing role-name and external-name validation.

Construction must not call `Constraint.evaluate`,
`Constraint._evaluate` or any constraint predicate.

No new constraint evaluation semantics are introduced.

### Relation

    record("relation", (kind, roles, payload))

`kind` is the existing nonempty relation-kind string.

`roles` is an ordered tuple of `(role_name, endpoint)`
pairs, as exposed by the approved inspection interface.

Construction validates role names and endpoint types,
rejects duplicate names and applies existing canonical
role ordering and endpoint normalization.

`payload` retains its canonical semantic value.

The result is a relation value, not a graph insertion.

Constructing an endpoint reference does not grant
authority to traverse or modify the referenced entity.

## 4. Genericity and opacity

The constructor is defined by semantic kind and public
record-field schemas.

It does not expose Python classes, arbitrary attributes,
CanonicalNode tags or serialized identity bytes.

It must not accept arbitrary implementation-defined
record kinds or import host classes dynamically.

Opaque EntityID, VersionID and StateID values can be
passed through as typed values. Their internal identifiers
cannot be recovered or forged using this operation.

Closures remain opaque. No construction or inspection of
captures, executable code or runtime frames is authorized.

Future record kinds require separate schema and authority
review.

This proposal does not claim that all 15 semantic kinds
can be independently manufactured from public components.
C10's complete scope remains subject to the frozen
acceptance evidence.

## 5. Admitted execution boundary

The proposed operation is an ordinary SHEAR expression,
compiled and executed through the existing authenticated
language pipeline.

Implementation must cover:

- Operation-shape registration.
- Text syntax and parsing.
- Source and graph-form lowering.
- Bytecode generation.
- Structural bytecode verification.
- Machine execution.
- Task 32 restricted-policy authorization.
- Hosted compiler and artifact generations.

A single generic record-construction VM instruction may
be introduced after owner approval.

The VM implementation may reuse the canonical semantic
model's pure validation and normalization rules.

This is a value-construction primitive, analogous to
existing tuple construction.

The distinction is essential:

Allowed:
- SHEAR computes the kind and fields.
- An admitted VM instruction consumes those values.
- The generic constructor validates and normalizes them.
- The VM returns the resulting typed semantic value.

Forbidden:
- The adapter computes the requested fields in Python.
- The adapter calls `Constraint.from_content()` after VM
  execution to manufacture the expected reconstruction.
- The VM executes unrelated code merely to fabricate an
  authenticated execution trace.
- Host-side constraint evaluation supplies the result.
- A privileged callback performs arbitrary record creation.

The canonical model may implement the primitive, but
construction must occur as a consequence of executing
the authorized instruction in the admitted machine.

## 6. Identity and validation

For every accepted construction:

    kind_of(result) == requested_kind

For a record whose public fields are reconstructed
without semantic modification:

    canonical_serialize(result)
      == canonical_serialize(original)

Equivalent normalized forms must retain their existing
canonical identities.

Bool and int, bytes and text, and distinct sequence
kinds must remain distinguishable.

Invalid field counts, field kinds, constraint forms,
bounds, nested constraints, roles and endpoints produce
ordinary language-level construction errors with
machine-operation provenance.

Validation errors must not be translated into Unknown,
Satisfied or Violated.

Host failures outside the documented input-validation
contract must preserve their existing failure boundary.

No effects are committed by failed construction.

Construction does not consume the constraint evaluation's
semantic node budget.

Generic execution-resource accounting remains separate.

## 7. Independent acceptance evidence

D123-8 does not modify the independently approved T5
acceptance contract.

Execution must establish all of the following:

1. The new operation can construct Cell, Constraint and
   Relation semantic records from runtime-computed fields.

2. All nine constraint forms reconstruct with their
   original canonical identities.

3. Reconstruction handles nested and empty compositions,
   deduplication, reordered operands, and type-sensitive
   distinctions.

4. Mutating independently selected SHEAR-computed input
   fields changes the reconstructed semantic result.

5. Authenticated execution evidence identifies the actual
   constructor instruction and its admitted artifact.

6. A controlled VM-return fault propagates without adapter
   fallback.

7. Independent source-path review confirms that the
   reconstructed record is produced by admitted SHEAR
   computation, not host-side postprocessing.

8. Malformed forms and typed impostors are rejected.

9. The operation remains pure under Task 32 restricted
   execution, with no new graph, runtime, closure or
   external authority.

10. All 18 candidate-dependent acceptance modules and 78
    tests remain mandatory, alongside the frozen Task 24
    semantics and Task 32 security requirements.

Evidence of construction alone does not prove complete
constraint evaluation or close GH-123.

## 8. Decisive experiment

Build one ordinary SHEAR function that:

1. Receives a semantic constraint through a raw argument.
2. Reads its public `form` and `arguments` fields.
3. Recursively reconstructs nested constraint values.
4. Calls `record("constraint", computed_fields)`.
5. Returns both the original and reconstructed values.

The implementation must work for all nine forms using
one generic construction facility.

The independent oracle verifies semantic identity.

Subsequently prove that constructed constraints can
participate in the complete integrated evaluation,
semantic-budget and restricted-execution experiment.

Failure must produce a minimal reproducible blocker,
not a weakened acceptance test.

## 9. Alternatives and stop conditions

A. Existing tuple and quote operations.

Insufficient unless an existing executable mechanism is
demonstrated to produce genuine typed semantic records.

B. One generic record-construction operation.

Preferred experiment. Reuses existing record schemas and
canonical validation without a new constraint interpreter.

C. Python-side reconstruction after admitted execution.

Rejected. It cannot establish that SHEAR produced the
semantic reconstruction.

Stop or return to Plan if:

- A special constraint evaluator is required to construct
  the record.
- Identity preservation requires exposing private tags.
- Construction grants forbidden runtime authority.
- The VM cannot distinguish typed semantic operands from
  ordinary tuple impostors.
- Source-path auditing cannot demonstrate that admitted
  computation determines the constructed result.
- Existing Task 24 or Task 32 requirements would change.

## 10. Approval boundary

Independent Review must determine whether this single
generic operation is sufficient, coherent and consistent
with the existing semantic and authority model.

The owner must separately approve D123-8 before production
implementation.

Approval would authorize only the described immutable
record-construction operation and its necessary language,
compiler, verifier, VM and restricted-policy support.

It would not authorize:

- Constraint-specific interpreter operations.
- Arbitrary host callbacks.
- Dynamic Python class construction.
- Forging opaque identities.
- Closure reconstruction or reflection.
- New graph or runtime mutation authority.
- Changes to frozen semantic or security acceptance.

Until then, C10 remains unresolved and full GH-123
feasibility is not demonstrated.
