# Handoff

## Current state

- Issue: #123 – complete constraint semantics with ordinary SHEAR functions.
- Branch: `task/123-complete-constraints`.
- Baseline: `f994a2d59b0f6f890f4800effe209d88e1c838c1`.
- Latest substantive Plan head: `e35bcb54fec478e7b530b6504a7c2cb9d488401b`.
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

Initial review findings:
- P1: insufficient evaluator-to-machine result authenticity.
- P1: T1–T9 acceptance obligations lacked concrete fixtures.
- P2: projection perturbations could pass for wrong reasons.
- P2: candidate import poisoning could reuse module cache.

Resolve introduced direct admitted execution, machine-result
binding, concrete T1–T9 fixtures, projection perturbations
and fresh-process import testing.

Subsequent review findings:
- P1: incorrect budgeted AllOf short-circuit expectation.
- P2: projection perturbation overconstrained validation.
- P2: forbidden-effect tests did not exercise candidate code.
- P3: external acceptance count was outdated.

Corrections:
- Corrected budget-2 subject-20 outcome to Violated.
- Used independently observed valid alternative VM outputs.
- Added candidate-derived dynamic-dispatch and preflight-denial
  acceptance.
- Registered candidate-effect tests in the main Plan and T9.
- Corrected T4 external acceptance inventory to seven tests.

Documentation and evidence audit:
- Strengthened projection-rejection provenance requirements.
- Clarified T5 output propagation versus fail-closed validation.
- Verified all 15 acceptance modules exist and are documented.
- Retained independent source-path auditing as mandatory.

## Latest independent Plan re-review

Reviewed head:
`0b05d545025e6693999fc624b923c084921ffb7b`

Substantive Plan head:
`0564041b2ab68aeb15f67c8366445eb98a8b1eff`

Verdict: REQUEST RESOLVE – one new P1.

The reviewer confirmed previous findings were resolved at the
Plan level but identified a candidate-independent fixture defect:

- A projection stress fixture nested 256 levels deep exceeds
  Python's standard recursion limit during the existing
  canonicalization and serialization of expected values.
- The failure occurs before candidate execution.
- Task 24 does not require this additional nesting depth.

Latest Resolve corrections:
- Projection nested depths are now 8, 64 and 128.
- Semantic negation depths are now 8, 9, 64, 65, 127 and 128.
- Semantic nested-role depths are now 8, 64 and 128.
- Width-256 projection and semantic stress cases are preserved.
- Exact semantic-budget expectations are preserved.
- Task 24 frozen fixtures and production code are untouched.

These fixes have not yet been independently re-reviewed.
The candidate-dependent suites remain unexecuted.

## Independent re-review priorities

1. Verify the latest two recursion-bound corrections.
2. Check that remaining mandatory stress fixtures are feasible
   under the supported Python recursion limit.
3. Confirm all previously resolved findings remain resolved.
4. Verify the exact budget expectations and Task 24 ordering.
5. Confirm projection rejection is not accepted solely because
   an adapter fabricates provenance metadata.
6. Check candidate-specific effects and preflight isolation.
7. Reconcile all 15 modules and 56 methods with T1–T9.
8. Verify the baseline-to-head diff changes no production code,
   Task 24 oracle, Task 32 security test or golden record.
9. Inspect exact CI evidence and identify unexecuted suites.

Independent source-path and fallback auditing remains mandatory
during Execute.

## Next action

1. Obtain independent read-only Plan re-review.
2. Resolve any remaining P0–P2 findings, if required.
3. Freeze the independently approved Plan.
4. Execute the complete architectural experiment.
5. Independently review implementation and evidence.

The owner retains architectural and publication authority.
