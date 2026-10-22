# Semantic Inspection Interface

Status: Independently approved read-only interface; D123-7c owner-authorized.
Issue: GH-123.
Decisions: D123-7a, D123-7b, D123-7c.
Scope: Generic SHEAR language facilities, not constraint-specific execution.
Review baseline: `96c62618cddc04bb3b1074730d6582207a61af37`.

## 1. Purpose

Ordinary SHEAR functions must inspect canonical semantic
values without exposing their internal serialization format
or forcing proportional-size materialization.

The interface covers all 15 canonical semantic kinds.

D123-7a authorizes immutable semantic visibility.
D123-7b authorizes generic `inspect`.
D123-7c authorizes the complete read-only public interface
defined in this document, including the generalized data
operations and semantic-record field schemas.

D123-7c explicitly approves:

- Generalizing `len`, `item` and `slice` to strings, bytes,
  lists, maps and semantic records.
- String-named record-field access through `item`.
- The specified Cell, Constraint and Relation field schemas.
- Closure opacity and all existing authority restrictions.

Existing tuple semantics, canonical identities and security
boundaries remain unchanged.

Semantic-record reconstruction is a separate unresolved
capability. The four operations defined here are sufficient
for inspection, but do not alone establish complete T5
constraint reconstruction.

Owner authorization permits implementation of the approved
interface. It does not establish implementation success or
authorize additional language operations.

## 2. Generic inspection

Input form:

    ("inspect", expression)

Text syntax:

    inspect(expression)

Result:

    (semantic_kind, original_value)

The result is an ordinary two-element tuple.

The first element is one of the 15 canonical kind names.
The second element is the original semantic value, shared
without expanding or reconstructing its contents.

Examples, in semantic notation:

    inspect("abc") = ("str", "abc")
    inspect(42) = ("int", 42)
    inspect(None) = ("none", None)

Inspection of an already inspected value identifies
the semantic kind of the resulting tuple.

The operation is pure and deterministic.

Constructing its result must not require work or new
allocations proportional to the inspected value's size.

The returned value retains its original semantic kind.
No tagged serialization representation is exposed.

## 3. Demand-driven operations

Extend the existing general data operations:

    len(value)
    item(value, index)
    slice(value, start, stop)

Their existing tuple behavior is unchanged.

Generalized operations inspect the semantic kind of their
operand and use its public semantic structure.

They must not interpret a canonical serialization node
as an ordinary tuple containing implementation tags.

Invalid operand kinds, indices and bounds produce
ordinary LanguageError failures.

### 3.1 Sequences

| Kind | len | item | slice |
|---|---|---|---|
| str | Code-point count | Single-code-point string | String |
| bytes | Byte count | Integer 0–255 | Bytes |
| tuple | Element count | Original element | Tuple |
| list | Element count | Original element | List |

Indices are zero-based integers, excluding bool.
Negative indices are invalid.

Slices use half-open bounds:

    0 <= start <= stop <= len(value)

No implicit clamping or negative indexing is introduced.

A slice may allocate storage proportional to the requested
output, not the entire containing value.

For strings, all bounds refer to Unicode code points,
not encoded bytes or grapheme clusters.

Unicode normalization is never implicit.

The choice of runtime string encoding is not part of the
public contract.

Existing canonical string behavior, including unresolved
surrogate-handling questions, is unchanged by this decision.

### 3.2 Maps

A map is an indexed sequence of semantic entries for
generic structural inspection.

    len(map)       number of entries
    item(map, i)   (key, value) at index i
    slice(map,a,b) tuple of selected entry pairs

Map entry ordering follows canonical-key ordering,
independent of insertion order or host dictionary order.

Canonical-key ordering uses the existing canonical
serialization ordering of keys. This does not expose
serialized key bytes to the program.

Map indices are positional integers, even when semantic
map keys are integers.

This interface does not overload item(map, key) for
lookup by semantic key.

Key lookup can be expressed through ordinary SHEAR
iteration over entries. A separate lookup operation
would require explicit authorization.

Accessing one entry must not reconstruct or sort the
entire map.

Any canonical ordering index needed internally must
avoid repeated whole-map sorting during iteration.

### 3.3 Semantic records

Records expose a finite, explicitly defined field schema.

For a record with exposed fields:

    len(record)       number of exposed fields
    item(record, i)   (field_name, field_value)
    item(record, s)   value of named field s
    slice(record,a,b) tuple of selected field pairs

Here s is a field-name string.

Field enumeration follows the schema's declared order.

The named and positional forms agree on the field value,
not on their complete return shapes:

    item(record, i)[1] == item(record, field_name)

where field_name is the name at position i.

Unknown field names and invalid indices are LanguageError.

Field access is shallow. Returning a nested semantic value
does not recursively expand that value.

The fields and their exposure rules are specified below.

## 4. Approved record schemas

These are the owner-approved public record schemas.
They are not inferred from Python attributes or from
the CanonicalNode serialization layout.

### Cell

Fields, in order:

    constraint
    initial

Only immutable declaration content is exposed.

The current runtime contents of the cell, its storage,
runtime references and mutation history are inaccessible.

### Constraint

Fields, in order:

    form
    arguments

`form` is one of the nine semantic constraint form names.

`arguments` is a tuple with the exact following schema:

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

The table describes public semantic values, not Python
implementation objects or private CanonicalNode structures.

For `is_kind`, kind is the semantic kind name.

For `int_range` and `length`, minimum and maximum retain
their existing optional-bound semantics and validation rules.

For `one_of`, values is a single existing immutable
collection of canonical semantic values.

For `all_of` and `any_of`, parts is a single existing
immutable collection of semantic constraints. Canonical
deduplication and ordering remain unchanged.

For `not`, part is the nested semantic constraint.

For `role`, role_name is the declared role-name string
and part is the nested semantic constraint.

For `external`, name is the external evaluator name.
No evaluator object or dispatch authority is exposed.

Empty `one_of`, `all_of` and `any_of` collections retain
their existing semantic identities and evaluation behavior.

In particular:

    OneOf.arguments = (values,)
    AllOf.arguments = (parts,)
    AnyOf.arguments = (parts,)

The nested collections are not flattened into the outer
argument tuple.

The operand tuple is shallow. Nested constraints and
collections remain semantically typed.

Creating this field may allocate a bounded tuple of
operand references, but not recursively copy operand
contents or flatten variable-length collections.

The outer tuple length is determined by the form's
declared schema, not by the size of any nested collection.

This schema provides generic dispatch without exposing
the Python Constraint class hierarchy.

### Relation

Fields, in order:

    kind
    roles
    payload

`kind` is the relation's semantic kind string.

`roles` is an immutable ordered sequence of
(role_name, endpoint) pairs.

This sequence is ordered by role name and refers to
the relation's existing semantic endpoints.

It is distinct from an ordinary map. Its order does not
change the canonical identity of the relation.

`payload` is the original semantic payload.

Reading an endpoint identifier does not grant authority
to traverse or modify the referenced graph entity.

Role enumeration must not eagerly clone the complete
role collection.

### Closure

Closures are opaque in this interface.

    inspect(closure) = ("closure", closure)

No public fields are exposed.

In particular, inspection cannot extract executable
code, runtime frames, owner authority or lexical
captures through implementation reflection.

Direct len, item and slice operations on closures are
unsupported.

Any future exposure of captured values or structural
metadata requires a separate authority and opacity
review.

## 5. Atomic and opaque values

The following kinds expose their semantic kind but no
indexable structure through this interface:

    none
    bool
    int
    entity_id
    version_id
    state_id
    closure

Inspection returns the original value unchanged.

Their internal representation is not part of the
public interface.

The generalized len, item and slice operations reject
unsupported atomic or opaque operands.

Large integers must not be converted to digit sequences
merely to determine their kind.

## 6. Identity, ownership and lifetime

Inspection creates no new public view type.

The original canonical value is retained by reference
in the inspection result.

Its identity and immutable semantic content are unchanged.

No lifetime is tied to an active execution frame,
restricted deployment, artifact set or graph traversal.

Values remain governed by ordinary SHEAR value ownership
and lifetime semantics.

Requested slices create ordinary semantic values and
do not mutate the source.

No runtime alias permits mutation of canonical contents.

## 7. Implementation boundaries and missing construction

The approved inspection interface must be implemented
consistently across:

- Input-form operation shapes.
- Text syntax and parsing.
- Source lowering.
- SHEAR compiler generations.
- Bytecode verification.
- VM execution.
- Restricted execution policy.

`inspect` is the approved new generic operation.

D123-7c authorizes generalizing the existing `len`,
`item` and `slice` operations to the semantic kinds
specified in sections 3 and 4.

It also authorizes string-named record lookup through
`item` and the exact public record-field schemas.

Existing tuple behavior must remain unchanged.

No additional instruction or public operation follows
implicitly from D123-7c.

Compiler preparation and authenticated evaluator
execution must remain distinct.

Restricted inspection provides no graph reflection,
external calls, runtime-state reads or mutation effects.

No Python-side subject-dependent projection or constraint
predicate may substitute for ordinary SHEAR computation.

### 7.1 Unresolved semantic-record reconstruction

The four inspection and access operations read existing
semantic values. They do not construct a new semantic
constraint value from runtime-computed fields.

In particular:

- Tuple construction creates an ordinary semantic tuple,
  not a semantic constraint record.
- An inspection result is not a record constructor.
- Constraint.from_content() is host-side machinery,
  not an admitted ordinary SHEAR operation.
- Returning the supplied original constraint does not
  establish independent semantic reconstruction.

The full T5 contract requires reconstruction performed
through admitted ordinary SHEAR computation while
preserving canonical constraint identity.

This is the missing capability identified as C10 in
`docs/constraint_functions_capability_matrix.md`.

A separate owner-approved solution is required before
complete T5 feasibility can be established.

Any proposal must specify:

- Whether construction is generic across semantic records.
- How forms and operand schemas are validated.
- How existing canonical identities are preserved.
- How construction is compiled and executed in SHEAR.
- Which effects, authorities and runtime policies apply.
- How malformed inputs fail without host semantic fallback.
- How genuine SHEAR reconstruction is independently tested.

D123-7c does not authorize a constructor, a new
opcode, a constraint-specific VM operation, privileged
host reconstruction or additional language syntax.

The missing capability must remain explicit until its
design is approved or the experiment demonstrates a
different sufficient existing mechanism.

Approval of the inspection interface does not constitute
approval of complete T5 reconstruction.

## 8. Resource requirements

The cost of shallow inspection must not scale with the
number of elements inside its input merely because
the input is inspected.

A single element access must not construct the entire
collection.

Repeated indexed access must not repeatedly re-sort
or re-serialize the complete input.

Explicitly requested slices may allocate in proportion
to their output.

Canonicalization performed before inspection is a
separate cost and must be measured separately.

Unicode code-point access may depend on the physical
string representation. This contract does not require
a specific encoding or unconditional constant-time
random access.

Inspection work and allocation remain distinct from
the existing semantic constraint-node budget.

An independent generic execution-resource limit may
be investigated without altering semantic budgets.

## 9. Required interface evidence

Before accepting implementation:

1. Cover all 15 canonical kinds.
2. Verify Unicode code-point indexing and slicing.
3. Verify maps with differing insertion orders.
4. Verify record field ordering and missing fields.
5. Verify all nine constraint argument schemas.
6. Verify shallow preservation of nested semantic types.
7. Verify large strings, bytes, maps and collections
   without eager proportional-size materialization.
8. Verify repeated access does not induce avoidable
   quadratic behavior.
9. Verify closure opacity, cell-state isolation and
   absence of graph or external authority.
10. Verify compiler, verifier, VM and restricted policy
    agree on the operations.
11. Verify existing tuple semantics, canonical identities
    and golden records remain unchanged.

The integrated GH-123 witness remains mandatory:

Raw canonical subject
→ authenticated ordinary SHEAR execution
→ generic semantic inspection
→ composite constraint evaluation
→ exact semantic budget
→ three-valued outcome.

An isolated inspection demonstration does not establish
complete constraint equivalence.

Constraint reconstruction is separately required by T5,
and remains blocked on the capability in section 7.1.

## 10. Review and authorization

Independent Review approved the read-only semantic
inspection interface at
`96c62618cddc04bb3b1074730d6582207a61af37`.

The owner subsequently approved D123-7c, authorizing
the normative extensions and record-field exposure rules
specified in this document.

This authorization closes the public inspection-interface
design gate only.

Implementation must still establish:

- Correct operation of generalized len, item and slice.
- Exact public semantic-record field behavior.
- Map ordering without repeated sorting.
- Shallow access without eager copying.
- Canonical identity and lifetime preservation.
- Closure opacity and cell-state isolation.
- Restricted execution and authority enforcement.
- Compiler, verifier and VM consistency.
- Preservation of existing tuple behavior and golden records.

C10 semantic-record reconstruction remains unresolved
and requires its own architectural decision or a
demonstration of sufficient existing generic facilities.

The independently approved 18-module, 78-test T5
acceptance contract remains unchanged.

No candidate-dependent test success is implied by
interface approval.

The owner retains authority over any subsequent
normative language or construction changes.
