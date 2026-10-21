# Handoff

## Current state

- Issue: #123 – complete constraint semantics with ordinary SHEAR functions.
- Branch: `task/123-complete-constraints`.
- Baseline: `f994a2d59b0f6f890f4800effe209d88e1c838c1`.
- Earlier approved Plan: `90426a708152364fa8289324c0ea1bcedb5e6f8b`.
- Approved architectural Resolve: `a1a4bfca115feca4d0e21bb39ce8d785445a9261`.
- Approved D123-7b refinement: `995667f90511a4545e2006b252822be4b4505932`.
- Latest capability-matrix update: `8eb6836a11c452bed54a669c2c254e24fc6c5b3f`.
- Execute paused pending public inspection-interface design and Review.
- No accepted complete constraint implementation or PR.

## Architectural decisions

D123-7a – Approved.

Ordinary SHEAR functions may inspect immutable semantic
structure across all 15 canonical kinds.

Inspection preserves semantic identity, type, opacity
and authority boundaries.

D123-7b – Approved, with demand-driven refinement.

One generic pure operation is authorized:

`("inspect", expression)`

The previous eager `(kind, members_tuple)` representation
is superseded.

Approved requirements:
- No eager proportional-size materialization.
- Demand-driven element and semantic-field access.
- Unicode code-point semantics without normalization.
- Deterministic canonical-key map ordering.
- Preservation of identity, immutability and opacity.
- No additional graph, runtime or external authority.
- Inspection resource costs separate from semantic budgets.

The operation is not yet implemented.

## Pending interface design

Before implementing the public interface, resolve:

1. Exact demand-driven result representation.
2. Element, map-entry and field access operations.
3. Lifetime and ownership of inspected views.
4. Semantic-record field names, ordering and exposure rules.
5. Compiler, verifier, VM and restricted-policy integration.

Record schemas must cover:
- `cell`
- `constraint`
- `relation`
- `closure`

The interface must be independently reviewed before
production implementation.

Additional normative language operations require owner
approval.

## Decisive integrated experiment

Demonstrate one authenticated compiled SHEAR evaluator:

Raw canonical subject
→ generic semantic inspection
→ composite constraint evaluation
→ exact semantic budget accounting
→ Satisfied / Violated / Unknown.

Test independent strings, bytes, maps and nested values.

Verify G1–G6, G8 and G10 together.

Then verify:
- G7 – External dispatch and failure provenance.
- G9 – initial admission, writes, activation and trials.

The candidate must perform actual SHEAR computation.
Host-side subject preprojection, Python constraint
predicates and fallback evaluation are prohibited.

Existing authenticated host-boundary dispatch may be reused.
New invocation authority requires owner approval.

## Previous Review findings

All P0–P2 Plan blockers were resolved and independently
reviewed.

- Unapproved projection modules were deleted.
- Capability-matrix leading blank line was corrected.
- Preflight fixture now permits legitimate compiler
  preparation while prohibiting evaluator entry before
  restricted preflight.
- Earlier Plan approval chronology was corrected.
- Demand-driven inspection replaced eager materialization.

The latest independent Review approved the revised Plan
with only P3 documentation synchronization findings.

## Frozen acceptance

Preserve:
- 15 candidate-dependent acceptance modules and 56 tests.
- Task 24 semantic oracles and 17 boundary cases.
- Task 32 security and authentication guarantees.
- Canonical identities and golden records.
- Approved 1000x warm median and p95 ceilings.
- Independent source-path, authority and fallback audits.

Candidate-dependent acceptance remains unexecuted.

## CI evidence

- `995667f` – exact-head ordinary CI passed.
- `8eb6836` – CI running at the last check.

Ordinary CI does not establish candidate equivalence.

## Next actions

1. Complete P3 documentation synchronization.
2. Define the demand-driven inspection interface,
   including semantic-record field schemas.
3. Obtain independent interface Review.
4. Implement the approved generic mechanism.
5. Run the complete integrated #123 experiment.
6. Verify frozen acceptance, authenticity, security,
   performance and mechanism accounting.

The owner retains architectural and publication authority.
