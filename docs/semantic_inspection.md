# Semantic Inspection Interface

Status: Proposed interface – independent Review required.
Issue: GH-123.
Decision: D123-7b.
Scope: Generic SHEAR language facilities, not constraint-specific execution.

## 1. Purpose

Ordinary SHEAR functions must inspect canonical semantic
values without exposing their internal serialization format
or forcing proportional-size materialization.

The interface covers all 15 canonical semantic kinds.

This specification proposes the concrete public interface
under the owner-approved D123-7a and D123-7b requirements.

No production implementation is authorized before the
interface has been reviewed and remaining language changes
have received owner approval.

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

This proposal does not overload item(map, key) for
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
Named lookup and positional access return the same value.

Unknown field names and invalid indices are LanguageError.

Field access is shallow. Returning a nested semantic value
does not recursively expand that value.

The fields and their exposure rules are specified below.

## 4. Proposed record schemas

These schemas are proposed for Review. They are not
automatically inferred from Python attributes or from
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

`form` is the semantic constraint form name, such as
"is_kind", "all_of" or "external".

`arguments` is a tuple of its semantic operands.

The operand tuple is shallow. Nested constraints and
collections remain semantically typed.

Creating this field may allocate a bounded tuple of
operand references, but not recursively copy operand
contents or flatten variable-length collections.

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

Closures are opaque in this initial interface.

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

## 7. Implementation boundaries

The interface must be implemented consistently across:

- Input-form operation shapes.
- Text syntax and parsing.
- Source lowering.
- SHEAR compiler generations.
- Bytecode verification.
- VM execution.
- Restricted execution policy.

`inspect` is the one newly approved generic operation.

Generalizing len, item and slice is proposed as the
smallest compatible extension to existing operations.
It must preserve the original tuple contracts.

No additional instruction or public operation follows
implicitly from this proposal.

Compiler preparation and authenticated evaluator
execution must remain distinct.

Restricted inspection provides no graph reflection,
external calls, runtime-state reads or mutation effects.

No Python-side subject-dependent projection or constraint
predicate may substitute for ordinary SHEAR computation.

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
5. Verify shallow preservation of nested semantic types.
6. Verify large strings, bytes, maps and collections
   without eager proportional-size materialization.
7. Verify repeated access does not induce avoidable
   quadratic behavior.
8. Verify closure opacity, cell-state isolation and
   absence of graph or external authority.
9. Verify compiler, verifier, VM and restricted policy
   agree on the operations.
10. Verify existing tuple semantics, canonical identities
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

## 10. Review gates

Independent interface Review must specifically assess:

- Whether generalized len, item and slice suffice for
  the integrated constraint experiment.
- Whether record schemas preserve semantic identity,
  abstraction and authority boundaries.
- Whether relation roles can be exposed without eager
  cloning or unintended type changes.
- Whether closure opacity is compatible with all frozen
  acceptance obligations.
- Whether map ordering and access avoid repeated sorting.
- Whether canonical values can remain physically shared
  across all supported inspection operations.
- Whether the proposed operation extensions require
  additional owner approval.

Unresolved implementation obstacles must be reported
with minimal reproducible counterexamples.

Do not treat this proposed interface or its acceptance
criteria as an executed implementation.

The owner retains authority over normative language
changes, and the independent Review gate remains mandatory.
