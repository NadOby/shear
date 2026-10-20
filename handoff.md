# Handoff

## Current state

- Issue: #123 – complete constraint semantics with ordinary SHEAR functions.
- Branch: `task/123-complete-constraints`.
- Baseline: `f994a2d59b0f6f890f4800effe209d88e1c838c1`.
- Reviewed Plan starting head: `b95c05a1822a688264d3aab96d58d40fa5c38134`.
- Latest substantive Plan head: `ca3454f156fc3bc95691d4c80557673dfee72098`.
- Role: Plan Resolve – independent re-review required.
- No production implementation or PR yet.
- CI results for this head have not been independently verified.

## Plan-owned contracts

- `docs/constraint_functions_complete.md`
- `docs/constraint_functions_complete_coverage.md`
- `docs/constraint_functions_complete_benchmarks.md`
- `tests/constraint_functions_complete_acceptance.py`
- `tests/constraint_functions_complete_projection.py`
- `tests/constraint_functions_projection_adversarial.py`
- `tests/constraint_functions_semantic_adversarial.py`

Acceptance modules remain outside ordinary test discovery.
Execute must provide the candidate implementation and register
the acceptance tests. Missing executable obligations are not passes.

Task 24's frozen semantic oracles, all 17 boundary cases,
and existing golden records remain unchanged.

## Architectural experiment

One decisive end-to-end experiment implementing complete
constraint semantics through ordinary SHEAR functions and
Task 32 restricted execution.

Initial falsifiable hypotheses:
- No new syntax.
- No new VM instructions.
- Generic canonical-content projection.
- Existing compiler, VM and restricted runner suffice.
- Exact semantic budgeting through ordinary computation.

Failure of a hypothesis permits an evidence-based architectural
decision; it does not authorize silent constraint-specific fallback.

## Resolve summary

- Removed premature CI discovery of candidate-dependent tests.
- Added admitted evaluator entry and artifact-provenance checks.
- Added machine fault injection and verdict perturbation.
- Added mandatory T1–T9 coverage matrix.
- Added canonical projection and adversarial structural tests.
- Added deterministic semantic stress acceptance.
- Defined reproducible benchmark methodology.
- Recorded owner-approved initial 1000x warm latency ceiling.
- Removed fixed generic mechanism-count cap.

## Acceptance

- Complete Task 24 semantic and generated-vector obligations.
- All 17 frozen runtime boundary cases.
- All additional T1–T9 tests and applicable existing corpora.
- Genuine load, write, activation and trial.
- Independent authentication and anti-fallback evidence.
- Preserved canonical identity, error provenance and atomicity.
- Reproducible performance and mechanism accounting.
- Explicit positive, negative or inconclusive conclusion.

The independent reviewer must verify actual Python APIs,
test correctness, complete coverage, and feasibility.
The new acceptance suites have not yet been demonstrated
against a working candidate.

## Next action

1. Independently re-review the complete branch diff and Plan.
2. Resolve any remaining P0–P2 findings.
3. Freeze the approved Plan.
4. Execute the decisive experiment in one coherent effort.

The owner retains architectural and publication authority.
