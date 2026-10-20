# Handoff

## Current state

- Issue: #123 – complete constraint semantics with ordinary SHEAR functions.
- Branch: `task/123-complete-constraints`.
- Baseline: `f994a2d59b0f6f890f4800effe209d88e1c838c1`.
- Latest substantive Plan head: `0564041b2ab68aeb15f67c8366445eb98a8b1eff`.
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

The Plan owns 15 candidate-dependent acceptance modules
containing 56 test methods.

They remain outside ordinary Plan-time test discovery.
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

Resolve introduced direct admitted execution, machine-result
binding, concrete T1–T9 fixtures, projection perturbations
and fresh-process import testing.

The subsequent independent review at `e814375` reported:
- P1: incorrect budgeted AllOf short-circuit expectation.
- P2: projection perturbation overconstrained validation.
- P2: forbidden-effect tests did not exercise candidate code.
- P3: external acceptance count was outdated.

Subsequent Resolve changes:
- Corrected budget-2 subject-20 outcome to Violated.
- Reworked projection perturbations to use alternative outputs
  independently observed from valid candidate executions.
- Added candidate-derived dynamic-dispatch and actual adapter
  preflight-denial acceptance.
- Registered candidate-effect tests in the main Plan and
  T9 coverage matrix.
- Corrected the T4 external acceptance inventory to seven.

A final documentation audit identified:
- P2: generic processing exceptions could still count as
  projection validation without sufficient provenance.
- P3: T5 documentation overstated output propagation.

Latest corrective changes:
- Projection rejection now requires the operation and exact
  rejected VM output to be identified on the exception.
- T5 documentation permits output propagation or explicit
  fail-closed validation and requires independent verification
  of the rejection mechanism.
- The actual file inventory, main Plan and handoff agree on
  all 15 acceptance modules.

These changes have not received independent Plan approval.
Structured rejection metadata alone does not prove genuine
validation. No candidate execution success is claimed.

## Independent re-review priorities

1. Verify the complete Plan diff and the latest fixes.
2. Check Task 24 budget ordering and exact expected outcomes.
3. Verify projection-output alternatives are legitimate and
   rejection handling is neither trivially permissive nor
   unnecessarily implementation-specific.
4. Determine whether the projection rejection provenance
   contract is feasible without imposing unapproved architecture.
5. Verify candidate-derived unauthorized dispatch is genuinely
   deployable and rejected before machine entry.
6. Verify forced candidate preflight denial cannot be bypassed.
7. Check all 15 acceptance modules for valid Python APIs,
   internally consistent fixtures and executable expectations.
8. Reconcile T1–T9 coverage with the immutable Task 24 oracles
   and Task 32 security and boundary tests.
9. Confirm the branch contains no unintended production,
   original test or golden-record changes.
10. Check applicable CI against the exact reviewed SHAs.

Independent source-path and fallback auditing remains mandatory
during Execute, including verification that projection rejection
really originates in validation rather than incidental failure.

## Next action

1. Independently re-review the final Plan head, read-only.
2. Resolve any remaining P0–P2 findings if required.
3. Freeze the independently approved Plan.
4. Execute the complete architectural experiment.
5. Independently review implementation and evidence.

The owner retains architectural and publication authority.
