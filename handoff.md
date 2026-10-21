
# Handoff

## Current state

- Issue: #123 – complete constraints with ordinary SHEAR functions.
- Branch: `task/123-complete-constraints`.
- Baseline: `f994a2d59b0f6f890f4800effe209d88e1c838c1`.
- Earlier Plan head: `90426a708152364fa8289324c0ea1bcedb5e6f8b`.
- Provisional Execute head: `26327534a146fd261770c2b655f78c6e41b1dd02`.
- Latest Plan Resolve head: `ed41f70106a6af4867bbf6b265aa33fa7f0dc10`.
- Role: Plan Resolve – independent re-review required.
- Execute paused. No accepted implementation or PR.

The earlier Plan was not independently approved;
Review requested Resolve.

## Architectural findings

Task 24 identified missing generic canonical inspection.
Task 32 established restricted execution but deferred
those capabilities.

The existing tuple operations are insufficient.
Host-side subject projection cannot replace genuine
SHEAR inspection of the original canonical value.

Two provisional Execute files remain unapproved:
- `shear/canonical_projection.py`
- `shear/constraint_function_projection.py`

## Plan Resolve

Updated:
- `docs/constraint_functions_capability_matrix.md`
- `docs/constraint_functions_complete.md`
- `docs/roadmap.md`

The capability matrix now separates:
- Host capabilities.
- VM operations.
- Compiler support.
- Restricted-execution permissions.
- End-to-end evidence.

The new repository-wide workflow gate remains provisional
pending independent Review.

## Owner decisions

D123-7a – Approved.

Ordinary SHEAR functions may inspect the semantic structure
of supplied values across all 15 canonical kinds.

Inspection is immutable, generic and type-preserving.
It exposes semantic fields, not serialization internals.

This does not authorize privileged graph reflection,
runtime-state access, external resources or expansion
of opaque representations.

D123-7b – Pending.

Select the generic inspection interface and its
compiler/VM implementation based on feasibility evidence.

No new opcode, public operation or naming change
has been approved.

## Decisive experiment

The first integrated witness must demonstrate:

Raw canonical subject
→ authenticated SHEAR execution
→ generic inspection
→ composite constraint
→ exact semantic budget
→ three-valued result.

Use one compiled evaluator on independently selected
strings, bytes, maps and nested values.

Verify G1–G6, G8 and G10 together.

Then demonstrate:
- G7 – named external dispatch and failure provenance.
- G9 – genuine admission, writes, activation and trials.

Existing authenticated host-boundary dispatch is permitted
where it satisfies the frozen External contract.

A new invocation mechanism requires a demonstrated need
and owner approval.

## Frozen requirements

Preserve:
- 15 candidate-dependent acceptance modules and 56 tests.
- Task 24 semantic oracles and 17 boundary cases.
- Task 32 authentication and security guarantees.
- Canonical identities and golden records.
- 1000x warm median and p95 performance ceilings.

Candidate-dependent tests have not executed.
No successful final-head CI run has been established.

The reported preflight-denial fixture issue requires
independent verification before any test correction.

## Independent Review priorities

1. Verify D123-7a visibility and opacity boundaries.
2. Check capability classifications against implementation.
3. Assess the integrated feasibility experiment.
4. Verify External authority and failure requirements.
5. Check that D123-7b remains owner-controlled.
6. Review the provisional repository workflow amendment.
7. Confirm frozen tests and specifications were preserved.
8. Verify exact-head CI evidence and remaining defects.

## Next action

Obtain independent read-only Plan re-review.

Do not resume dependent implementation until the amended
Plan and required architectural decisions are accepted.

The owner retains architectural and publication authority.
