# Handoff

## Current state

- Issue: #123 – complete constraint semantics with ordinary SHEAR functions.
- Branch: `task/123-complete-constraints`.
- Baseline: `f994a2d59b0f6f890f4800effe209d88e1c838c1`.
- Earlier approved Plan: `90426a708152364fa8289324c0ea1bcedb5e6f8b`.
- Architectural Plan Review at `23b4559a0111f2a8409d1f8b5bac256f927050a5`: REQUEST RESOLVE.
- Latest substantive Resolve: `6a59b8724a5438900244dbbccbd28a8270695054`.
- Execute paused. No accepted implementation or PR.

The earlier Plan was independently approved, then superseded
by architectural amendments requiring renewed Review.

## Architecture

Task 24 demonstrated missing generic canonical inspection.
Task 32 established authenticated restricted execution but
deferred complete inspection and constraint replacement.

The updated capability matrix distinguishes the original
vision, decided semantics, available mechanisms and
unverified end-to-end capabilities.

D123-7a – Approved: ordinary SHEAR functions may inspect
the immutable semantic structure of supplied values across
all 15 canonical kinds. Inspection preserves types and
opacity and grants no additional runtime or graph authority.

D123-7b – Pending: select the generic inspection interface
and its compiler/VM implementation after feasibility evidence.

No new opcode, public operation or naming change is approved.
Naming decisions prioritize clarity for human programmers
without unnecessary changes to settled semantics.

## Decisive experiment

Demonstrate one compiled, authenticated SHEAR evaluator:

Raw canonical subject
→ generic semantic inspection
→ composite constraint computation
→ exact semantic budgeting
→ Satisfied / Violated / Unknown.

Use independent strings, bytes, maps and nested values.
Verify G1–G6, G8 and G10 together, including compiler,
verifier and VM support, without host-side projection
or Python predicate substitution.

Also verify:
- G7 – External dispatch and failure provenance.
- G9 – genuine admission, writes, activation and trials.

Existing authorized host-boundary dispatch may be reused.
New invocation authority requires owner approval.

## Latest Review findings and Resolve

Review at `23b4559` approved the architectural direction
but identified three blocking defects:

1. P1 – Two unapproved projection modules broke the
   mandatory mutation inventory. Both were deleted.
2. P2 – The capability matrix had a leading empty line.
   Its heading is now the first line.
3. P2 – The preflight-denial test incorrectly prohibited
   compilation during evaluator preparation. That guard
   was removed from this test; denial and the prohibition
   on machine entry remain.

The separate test against late lowering remains intact.
The changed Plan-owned acceptance test requires fresh
independent verification.

P3 – Corrected handoff chronology and removed its own
leading empty line.

The deleted experimental modules remain available through
Git history; neither is an approved architectural solution.

## Preserved requirements

- 15 candidate-dependent acceptance modules, 56 tests.
- Task 24 frozen oracles and 17 boundary cases.
- Task 32 authentication and security guarantees.
- Canonical identities and golden records.
- Approved 1000x warm median and p95 performance ceilings.
- Independent source-path, authority and fallback auditing.

Candidate-dependent suites have not executed.

## CI evidence

- `7fc26f3` – ordinary CI passed.
- `6a59b87` – CI running at the last check.

Exact final-head CI and independent Review are still required.
No unexecuted test is considered passed.

## Next action

1. Confirm CI on the latest Resolve.
2. Obtain fresh independent read-only Plan Review.
3. Resolve any remaining blockers.
4. Obtain owner decision D123-7b before introducing
   normative inspection operations.
5. Resume the integrated feasibility experiment.

The owner retains architectural and publication authority.
