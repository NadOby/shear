
# Handoff

## Current state

- Issue: #123 – complete constraint semantics with ordinary SHEAR functions.
- Branch: `task/123-complete-constraints`.
- Original baseline: `f994a2d59b0f6f890f4800effe209d88e1c838c1`.
- Previously approved Plan: `90426a708152364fa8289324c0ea1bcedb5e6f8b`.
- Provisional Execute head: `26327534a146fd261770c2b655f78c6e41b1dd02`.
- Latest substantive amended Plan: `46f6c6f297ee809b60334774e23b1f361f8895b6`.
- Role: Plan – independent Review pending.
- Execute paused. No PR or accepted implementation yet.

## Architectural finding

Task 24 already identified missing generic canonical-content
inspection. Task 32 explicitly deferred resolving it.

The existing tuple operations cannot inspect all 15 canonical
semantic kinds. Host-side projection cannot substitute for
the raw subject required by frozen direct-result acceptance.

Two provisional Execute files remain unapproved:
- `shear/canonical_projection.py`
- `shear/constraint_function_projection.py`

They are experimental implementation attempts, not proof
that the architectural blocker has been resolved.

## Amended Plan

Plan-owned documents:
- `docs/constraint_functions_complete.md`
- `docs/constraint_functions_complete_coverage.md`
- `docs/constraint_functions_complete_benchmarks.md`
- `docs/constraint_functions_capability_matrix.md`

The matrix traces requirements from the original vision,
decided semantics, previous experiments and current code.

G1–G10 define capability-feasibility discriminators.

The amended `docs/roadmap.md` requires critical inherited
dependencies to be demonstrated, explicitly experimental,
blocked or legitimately out of scope.

Human-facing naming clarity is part of Plan Review.
Renames or prefixes are possible, but no semantic changes
or naming decisions have been authorized.

## Pending owner decision

D123-7: Select the smallest generic canonical-inspection
mechanism after validating the complete capability matrix.

A shallow structural-view operation is a candidate,
not an approved design.

Any language-shaping change requires owner approval.

## Frozen requirements

- 15 original candidate-dependent acceptance modules.
- 56 test methods.
- Task 24 semantic and boundary oracles.
- Task 32 authenticated execution and security guarantees.
- Existing canonical identities and golden records.
- 1000x warm median and p95 performance ceilings.

The candidate-dependent suites have not executed.
Execute must register the complete acceptance inventory in CI.

## Independent Review priorities

1. Verify the amended Plan against the original vision.
2. Check inherited blockers and their dispositions.
3. Independently assess G1–G10 feasibility and evidence.
4. Audit naming clarity without changing semantics.
5. Verify the two provisional Execute files are not
   treated as proof of implementation sufficiency.
6. Confirm frozen acceptance and security remain intact.
7. Identify any additional required owner decisions.
8. Verify exact-head CI evidence without assuming success.

## Next action

Obtain independent read-only amended-Plan Review.

Do not resume dependent Execute work before Review
and necessary owner decisions.

The owner retains architectural and publication authority.
