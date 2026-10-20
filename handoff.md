# Handoff

## Current state

- Issue: #123 – complete constraint semantics with ordinary SHEAR functions.
- Branch: `task/123-complete-constraints`.
- Baseline: `f994a2d59b0f6f890f4800effe209d88e1c838c1`.
- Proposed frozen Plan content head: `2ae3099b2a9c0bbadce3bde4266fe593caa5a2ea`.
- Role: Plan – independent Review pending.
- No production implementation or PR yet.

## Plan-owned files

- `docs/constraint_functions_complete.md`
- `tests/test_constraint_functions_complete.py`
- `tests/lanes.py`

Task 24's frozen oracles and 17 boundary cases remain unchanged.

## Architectural experiment

Implement complete constraint semantics through ordinary SHEAR
functions using Task 32 restricted execution.

Initial hypotheses:
- No new syntax.
- No new VM instructions.
- Generic canonical-content projection.
- Existing compiler, VM and restricted runner.
- Exact semantic budget propagation through ordinary computation.

These are falsifiable hypotheses, not mandatory architectural
restrictions. Language-shaping decisions remain with the owner.

## Acceptance

- Complete Task 24 semantic/property oracles.
- All 17 frozen boundary scenarios.
- Genuine load, write, activation and trial.
- Independent proof of no Python constraint fallback.
- Preserved identity, errors, isolation and atomicity.
- Mechanism accounting and reproducible execution costs.
- Explicit positive, negative or inconclusive conclusion.

The acceptance tests deliberately fail until Execute supplies
the candidate implementation.

## Next action

1. Obtain independent Plan Review.
2. Resolve any blocking findings.
3. Freeze the approved Plan.
4. Execute the complete experiment in one coherent effort.

No applicable CI success is claimed.

The owner retains architectural and publication authority.
