# Handoff

## Current state

- Issue: #123 – complete constraint semantics with ordinary SHEAR functions.
- Branch: `task/123-complete-constraints`.
- Baseline: `f994a2d59b0f6f890f4800effe209d88e1c838c1`.
- Latest substantive Plan head: `714a058e98f395d2db970083be476eb8105eb97b`.
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

The main Plan and coverage matrix identify T1–T9 executable
acceptance requirements and the independent evidence needed.

The owner-approved initial performance ceiling is 1000x
incumbent warm median and p95 latency. There is no fixed
generic mechanism-count cap.

## Frozen executable acceptance

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

These remain outside ordinary Plan-time test discovery.
Execute must supply the candidate and register all suites.

Task 24's immutable semantic oracle and 17 boundary cases,
Task 32's restricted-execution tests and all existing golden
records remain mandatory and unchanged.

## Previous Review findings

The preceding independent review requested Resolve for:
- P1: insufficient evaluator-to-machine result authenticity.
- P1: T1–T9 acceptance obligations deferred without fixtures.
- P2: projection perturbations could pass for wrong reasons.
- P2: candidate import poisoning could reuse module cache.

Resolve added:
- Fresh-process import testing.
- Valid-result projection perturbation.
- Direct admitted evaluator verdict testing.
- Adapter-to-machine argument and result binding.
- Concrete malformed-input and budget fixtures.
- External callback, failure and timeout witnesses.
- Constraint reconstruction and canonical-identity fixtures.
- Runtime relation, rename and atomicity scenarios.
- Real runtime exception-provenance checks.
- Candidate-backed complete corpus replay.
- Candidate-specific artifact authority and replacement checks.

These changes require independent verification. Their presence
does not establish that the previous findings are resolved.

## Review priorities

1. Verify the complete branch diff, exact APIs and test syntax.
2. Check all frozen expected observations against Task 24.
3. Identify impossible or unnecessarily architecture-specific
   acceptance conditions.
4. Verify genuine evaluator-machine-result dependence.
5. Verify host external dispatch does not bypass SHEAR truth logic.
6. Verify generic projection tests reject host-only implementations.
7. Verify runtime admission and corpus integration cannot fall back.
8. Verify artifact authority, effect isolation and replacement.
9. Check T1–T9 coverage and all CI registration requirements.
10. Confirm no Plan-owned fixture silently weakens existing oracles.

The T9 candidate artifact tests and existing Task 32 policy tests
have distinct scopes. An independent source-path audit remains
mandatory during Execute.

Minor editorial drift: the coverage matrix currently calls the
T4 acceptance inventory six tests; it now contains seven.
This is not evidence of an implementation or semantic failure.

## Next action

1. Independent read-only Plan re-review at the final branch head.
2. Resolve remaining P0–P2 findings, if any.
3. Freeze the approved Plan.
4. Execute the complete experiment.
5. Independently review the resulting implementation and evidence.

The owner retains architectural and publication authority.
