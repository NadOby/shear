# GH-123 – T5 Semantic Inspection Acceptance Mapping

Status: Owner-approved contract correction – acceptance Review pending.
Issue: GH-123.
Branch: `task/123-complete-constraints`.
Decision baseline: `23bdaeb5f58ce2890c03b9ebf33ff677c0bbc885`.

## 1. Scope

Replace only T5 expectations that require ordinary SHEAR
functions to expose private CanonicalNode structure.

The old path contract treats canonical content as:

    ("__type__", semantic_kind, payload)

D123-7a and D123-7b instead establish immutable semantic
inspection through:

    inspect(value)
    len(value)
    item(value, index)
    slice(value, start, stop)

The latter three operations are proposed compatible
extensions of existing tuple operations. Their precise
public changes remain subject to interface approval.

Do not introduce private serialization inspection,
identity-payload extraction, closure reflection, graph
authority or additional normative language operations.

Host-side canonical serialization remains permitted as
an independent acceptance oracle, never as a substitute
for admitted SHEAR computation.

## 2. Semantic path contract

The candidate adapter retains:

    select_projection(value, path)

Its path now addresses public semantic structure.

Path components are:

- Integer indices for sequences and canonical-order maps.
- Integer indices or declared field names for records.
- Tuple indices for map entry pairs and similar tuples.

Indices are nonnegative and exclude bool.

The empty path selects the complete original value.

A map index selects a semantic (key, value) pair.
Subsequent indices 0 and 1 select its key and value.

Record fields follow the approved inspection schemas.

Strings use Unicode code-point indexing.
Bytes use integer byte values, never hex characters.

Opaque values are terminal leaves. Selecting a component
inside an opaque value must fail as a language error.

A path must not inspect CanonicalNode implementation
tags, payload tuples or serialized identity components.

Path traversal is implemented by admitted ordinary SHEAR
code, not by Python-side projection.

## 3. Old-to-new witness mapping

| Old structural witness | Replacement semantic witness |
|---|---|
| `(1,)` reads a private kind tag | `inspect(value)` returns the semantic kind |
| `(2,)` reads private payload | Access only approved elements or record fields |
| `(2,)` on EntityID extracts a string | Empty path preserves EntityID; nonempty paths fail |
| `(2,)` on VersionID or StateID extracts a string | Preserve typed identity as an opaque leaf |
| `(2,)` on bytes exposes hexadecimal data | Index bytes directly, yielding integers 0–255 |
| Internal string traversal | Index Unicode code points directly |
| Canonical tuple/list payload traversal | Index semantic sequence members directly |
| Canonical map payload traversal | Select canonical-order semantic (key, value) pairs |
| Cell payload tuple traversal | Select immutable `constraint` and `initial` fields |
| Constraint canonical payload traversal | Select `form` and `arguments` fields |
| Relation canonical payload traversal | Select `kind`, `roles` and `payload` fields |
| Closure canonical payload traversal | Preserve the closure as an opaque leaf |
| Private tag inspection of an ordinary tuple | Distinguish semantic tuple from semantic record using inspect |

Representative paths:

    value: EntityID("sample")
    old:   (2,) -> "sample"
    new:   ()   -> EntityID("sample")

    value: b"\x00\xff"
    new:   (1,) -> 255

    value: {"a": [1, 2], "b": {"c": True}}
    new:   (1, 0) -> "b"
    new:   (1, 1, 0, 1) -> True

Map entry ordering is established by the existing
canonical-key ordering, not Python insertion order.

Closure and identity internals are never traversed.

## 4. Existing test mapping

### constraint_functions_complete_projection.py

Retain:
- All 15 canonical kinds.
- Kind and length observations.
- Type-sensitive equality.
- Nested data and semantic identity roundtrips.
- Map order independence.
- Machine-execution fault propagation.

`inspect_projection` must use admitted SHEAR computation.
Its reconstructed result must retain canonical identity
without exposing private representation to SHEAR code.

### constraint_functions_projection_adversarial.py

Retain all existing tests and their adversarial scope.

Replace canonical structural-path generation with semantic
path generation from the approved public field schemas.

Update:
- `structural_paths` and `sampled_paths` to use semantic paths.
- `test_structural_path_access` to test public traversal.
- Deep and wide path witnesses to use semantic structure.
- `test_selection_depends_on_valid_machine_output` to use
  a public semantic path and two distinct valid outputs.

Preserve unchanged in strength:
- All 15 kinds and cross-kind equality matrix.
- Deterministic generated nested-value coverage.
- Deep structures at depths 8, 64 and 128.
- Wide maps at widths 8, 64 and 256.
- Map insertion-order and canonical-identity invariance.
- Near-equal values, type collisions and impostor tuples.
- Authenticated machine entry for every candidate call.
- Controlled valid machine-output perturbation.
- Explicit fail-closed validation with operation and
  rejected-VM-output provenance.
- Independent source-path and fallback auditing.

Add or explicitly retain:
- Opaque-leaf non-traversal and invalid-path rejection.
- Unicode code-point and raw-byte access witnesses.
- Cell, constraint and relation field-selection paths.
- Closure identity preservation without field access.
- Repeated access and large-value resource witnesses.
- Independent verification that no subject-specific
  host projection computes the selected subtree.

Generated semantic paths must not be derived from a
candidate result or expose private canonical tags.

### constraint_functions_identity_acceptance.py

Retain every existing expression witness, canonical
equivalence pair and distinction pair.

Reconstruction outputs must preserve canonical semantic
identity and reflect actual admitted SHEAR computation.

Replace assertions requiring tagged CanonicalNode tuples
with semantic-kind and canonical-identity checks.

Constraint reconstruction remains mandatory where the
approved language interface can express it. Any genuine
missing construction capability must be reported as an
interface gap, not hidden with Python reconstruction.

Do not treat a pass-through input, host-generated expected
value or forged execution trace as valid reconstruction.

### constraint_functions_complete_coverage.md

Update T5 to require public semantic inspection rather
than private canonical-structure traversal.

Retain canonical identity, semantic reconstruction,
type-sensitive equality, independent result provenance,
fail-closed validation and deployment independence.

Do not modify T1–T4 or T6–T9 obligations.

## 5. Resource and authenticity obligations

Shallow inspect must not expand large values.

Single-element and field access must not clone the whole
container or require repeated full serialization or sort.

Repeated map iteration must not induce avoidable
quadratic work.

Measure work and allocation attributable to inspection
separately from initial canonicalization.

Constraint-node budgets remain distinct from inspection
resource costs.

Every candidate-dependent T5 operation must enter
authenticated ordinary SHEAR execution.

Controlled VM outputs must either affect the public result
or produce the existing explicit fail-closed validation
evidence.

Independent review must rule out Python truth evaluation,
host-side subtree selection, forged machine entry and
fallback to the incumbent.

## 6. Preserved frozen requirements

Unchanged:
- Task 24 semantic oracles and T1–T9 semantics.
- All 17 Task 24 boundary cases.
- Task 32 security and authentication requirements.
- Existing canonical identities and golden records.
- The original 15-kind and equality coverage.
- Large, deep, nested and adversarial test strength.
- Independent execution-authenticity and fallback audit.
- Existing 1000x performance assessment ceilings.

The T5 change corrects an obsolete representation-specific
acceptance assumption, not the required semantic outcome.

## 7. Review gate

Complete the representation-dependent acceptance edits
before independent acceptance Review.

The reviewer must check old-to-new test correspondence,
coverage counts, semantic equivalence, negative witnesses
and the authenticity of the execution discriminators.

No weakened test, additional operation or privileged
inspection is authorized by this mapping.

Execute remains blocked until the amended acceptance
contract and public inspection interface are approved.

## 8. Generated nested-record acceptance

The following Plan-owned module is mandatory for T5:
    tests/constraint_functions_nested_record_acceptance.py

Execute must register and run every test in this module alongside
the existing T5 acceptance modules.

The independent semantic-path oracle derives expected values from
original semantic fixtures, not candidate results or private
CanonicalNode serialization.

Required coverage:

- Deterministic generated collections nested in Cell.initial.
- Generated collections nested in Relation.payload.
- Nested constraint forms and operand paths.
- Mixed record, map, list and tuple traversal.
- Both named and positional record-field access.
- Authenticated SHEAR execution for every selected path.
- Canonical semantic equivalence of selected values.

The existing adversarial module remains mandatory and unchanged.
Neither module substitutes for the other.

The new module is candidate-dependent and is not considered passed
by ordinary incumbent-only CI.

Independent Review must verify that generated samples actually
reach nested semantic contents, including values canonicalized
during record construction. Passing shallow paths alone is
insufficient.

## 9. Generalized operation and resource acceptance

The following additional Plan-owned modules are mandatory for T5:

    tests/constraint_functions_sequence_acceptance.py
    tests/constraint_functions_resource_acceptance.py

Together with the nested-record module in section 8, they extend
the candidate-dependent inventory to 18 modules and 78 test methods
at HEAD f8ccc488f4d2424672b02d3894fb428efc588914.

These counts describe the current Plan inventory, not executed
test results. Earlier inventory counts remain historical baselines.

### Generalized sequence operations

Execute must supply:

    sequence_projection(value, operation, *arguments)

The supported operations are "len" and "slice". They must execute
through authenticated ordinary SHEAR computation.

Mandatory witnesses include semantic result kinds, Unicode code
points, bytes, maps, record field ordering, half-open bounds,
invalid inputs and ordinary LanguageError behavior.

Machine-result perturbation must use actual authenticated VM
returns without imposing a single-invocation architecture.

Independent source-path auditing must establish that the requested
operations, rather than unrelated admitted code or Python host
projection, determine the observations.

### Resource efficiency

Execute must supply:

    prepare_resource_probe(canonical_value, operation)
    INSPECTION_RESOURCE_BOUNDARIES

These are test instrumentation contracts, not additional public
SHEAR language operations.

Preparation and input canonicalization must be separated from
measured inspection.

Resource measurements must be obtained independently of
candidate-reported counters.

The acceptance must enforce bounded attributable inspection
work and allocation across different collection sizes, including:

- Repeated canonical-order map indexing.
- Indexed access to large sequences.
- Large relation-role collections.
- Large constraint-operand collections.
- Shallow inspection of large canonical values.

Complete semantic results must be verified independently.

The registered instrumentation boundaries must cover all
relevant generic execution work, including delegated helpers,
native operations, sorting, serialization and allocation.

Python opcode tracing alone does not establish these guarantees.
Independent source-path review must validate boundary completeness
and identify any unmeasured work.

Candidate execution, authenticated admission, compiler preparation
and initial canonicalization costs must be accounted for separately.

### Acceptance gates

All three new T5 modules are mandatory and candidate-dependent.

No new module may be skipped, silently excluded or counted as
passing solely because ordinary CI succeeds.

The original T5 semantic, security and execution-authenticity
obligations remain unchanged.

Independent Review must explicitly assess instrumentation
completeness, machine-result dependency and the absence of
host-side semantic fallback before approving Execute.
