
# Handoff

## Current state

- Issue: #123 – complete constraint semantics with ordinary SHEAR functions.
- Branch: `task/123-complete-constraints`.
- Baseline: `f994a2d59b0f6f890f4800effe209d88e1c838c1`.
- Latest substantive Plan head: `a689501c556b02e03e692dafa098b4fdfb662ebc`.
- Role: Plan Resolve – independent re-review required.
- No production implementation or PR yet.
- Candidate-dependent acceptance has not executed.
- Final-head CI has not been independently verified.

## Architectural decision

Run one decisive experiment implementing complete constraint
semantics through ordinary SHEAR functions and Task 32's
authenticated restricted execution.

Initial hypotheses:
- No new syntax or VM instructions.
- Generic immutable canonical-content projection.
- Existing compiler, VM and restricted runner.
- Exact semantic budgeting through ordinary computation.
- Genuine load, write, activation and trial integration.

Hypotheses are falsifiable, not unconditional restrictions.
Language-shaping decisions return to the owner.

## Plan-owned specification

- `docs/constraint_functions_complete.md`
- `docs/constraint_functions_complete_coverage.md`
- `docs/constraint_functions_complete_benchmarks.md`

The main Plan and coverage matrix define T1–T9 executable
acceptance requirements and independent evidence obligations.

The owner-approved initial performance ceiling is 1000x
incumbent warm median and p95 latency. There is no fixed
generic mechanism-count cap.

## Plan-owned executable acceptance

Primary:
- `tests/constraint_functions_complete_acceptance.py`
- `tests/constraint_functions_complete_projection.py`
- `tests/constraint_functions_projection_adversarial.py`
- `tests/constraint_functions_semantic_adversarial.py`

Additional:
- `tests/constraint_functions_import_acceptance.py`
- `tests/constraint_functions_direct_result_acceptance.py`
- `tests/constraint_functions_binding_acceptance.py`
- `tests/constraint_functions_t2_t3_acceptance.py`
- `tests/constraint_functions_external_acceptance.py`
- `tests/constraint_functions_identity_acceptance.py`
- `tests/constraint_functions_runtime_acceptance.py`
- `tests/constraint_functions_failure_acceptance.py`
- `tests/constraint_functions_corpus_acceptance.py`
- `tests/constraint_functions_authority_acceptance.py`
- `tests/constraint_functions_candidate_effect_acceptance.py`

All 15 modules remain outside ordinary Plan-time test discovery.
Execute must supply the candidate and register every suite.

Task 24's immutable semantic oracles and 17 boundary cases,
Task 32's restricted-execution tests and existing golden
records remain mandatory and unchanged.

## Independent review history

Initial review identified:
- P1: insufficient evaluator-to-machine result authenticity.
- P1: T1–T9 acceptance obligations deferred without fixtures.
- P2: projection perturbations could pass for wrong reasons.
- P2: candidate import poisoning could reuse module cache.

These were substantially resolved through direct admitted
execution, result binding, frozen T1–T9 fixtures, valid-result
perturbations and fresh-process import testing.

The subsequent independent review at `e814375` reported:
- P1: incorrect budgeted AllOf short-circuit expectation.
- P2: projection perturbation overconstrained validation.
- P2: forbidden-effect tests did not exercise candidate code.
- P3: external acceptance count was outdated.

Latest Resolve changes:
- Corrected the budget-2 subject-20 outcome to Violated.
- Allowed verified fail-closed projection validation while
  retaining controlled machine-output dependence.
- Added candidate-derived dynamic-dispatch and actual adapter
  preflight-denial acceptance.
- Registered the new tests in the Plan and coverage matrix.
- Corrected the external acceptance inventory to seven tests.

These corrections have not yet received independent approval.
No candidate execution success is claimed.

## Independent re-review priorities

1. Verify all four findings from the latest review are resolved.
2. Examine corrected budget expectations against Task 24 ordering.
3. Verify projection corruption cannot be ignored or excused by
   unrelated exceptions.
4. Verify candidate-derived forbidden dispatch is genuinely
   deployable and rejected before machine entry.
5. Verify forced preflight denial reaches the candidate's actual
   restricted execution path without hidden fallback.
6. Check all acceptance modules for correct Python APIs, syntax,
   consistent expected outcomes and unintended architectural limits.
7. Confirm T1–T9 coverage and complete test registration.
8. Confirm frozen Task 24, Task 32, production and golden records
   remain unchanged.
9. Verify applicable CI against exact commit SHAs.

An independent implementation-level source-path audit remains
mandatory during Execute.

## Next action

1. Independently re-review the final Plan head, read-only.
2. Resolve any remaining P0–P2 findings if required.
3. Freeze the approved Plan.
4. Execute the complete architectural experiment.
5. Independently review implementation and evidence.

The owner retains architectural and publication authority.
