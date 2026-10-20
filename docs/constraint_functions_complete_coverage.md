# GH-123 Complete Acceptance Coverage

Status: Plan-owned acceptance contract, pending independent Review.
Baseline: f994a2d59b0f6f890f4800effe209d88e1c838c1.
Task 24 (#56) remains the normative semantic oracle.
Task 32 (#119) remains the restricted-execution authority.

## Rules

Every T1–T9 obligation is mandatory. Existing Task 24 oracles,
expected results, scripts, order and golden records are immutable.

The candidate must execute ordinary SHEAR functions through
authenticated Task 32 artifacts. Passing incumbent tests alone
does not establish candidate equivalence.

The following named tests are required Execute deliverables.
Implement them under non-discovered Plan-owned acceptance
modules; register an ordinary CI wrapper only when the candidate
exists. An unimplemented test is missing evidence, not a pass.

## T1 – Three-valued composition

Existing:
- `CompleteConstraintAcceptance.test_complete_semantic_oracle`

Required observations:
- All frozen logical vectors and both generated families pass.
- Both operand orders, empty compositions, nested compositions,
  deduplication and short-circuit outcomes agree with Task 24.
- All cases execute the intended admitted SHEAR evaluator.

## T2 – Primitive and kind semantics

Existing:
- `CompleteConstraintAcceptance.test_complete_semantic_oracle`

Add:
- `test_malformed_constraint_inputs`
- `test_generic_projection_all_kinds`

Required observations:
- Every existing primitive and all 15 semantic kinds.
- Invalid construction arguments retain existing error classes.
- Type-sensitive equality, including bool versus int.
- Missing and incorrectly typed role maps are distinguished.
- Unsupported candidate syntax is never reported as Unknown.

## T3 – Exact semantic budgets

Existing:
- All frozen Task 24 budget and generated-budget vectors.

Add:
- `test_budget_consumption_trace`

Required observations:
- Exact visited-node counts for 0, 1, 2, sufficient and
  unbounded budgets.
- Deduplication and short-circuiting preserve existing counts.
- Exhaustion never creates an unsupported decisive verdict.
- Machine execution limits remain separate from semantic budgets.

## T4 – External evaluators

Existing:
- Task 24 External vectors and boundary scripts.
- `test_evaluator_fault_propagates_for_every_operation`

Add:
- `test_external_dispatch_and_failure_provenance`
- `test_nonterminating_external_isolated`

Required observations:
- Absent, decisive, Unknown and raising evaluators.
- Named evaluator selection and preserved canonical subjects.
- Escaping host failures do not become semantic Unknown.
- Nonterminating external execution runs in an isolated process
  with a supervisor timeout and forced process termination.
- Record whether execution reached the external evaluator.
- Do not assert universal termination: the incumbent node
  budget does not bound external computation.

## T5 – Canonical identity and reconstruction

Add:
- `test_generic_projection_roundtrip`
- `test_constraint_reconstruction_identity`
- `test_constraint_identity_across_versions`

Required observations:
- Every kind preserves canonical serialization and kind tags.
- Projection is immutable, generic and independently testable
  outside constraint evaluation.
- Nested tuples, lists, maps and semantic records round-trip.
- Map insertion order cannot change semantic identity.
- Bytes, text, identifiers and sequence kinds stay distinct.
- Reconstructed constraints remain canonical semantic data.
- Evaluation and ordinary unrelated edits cannot change
  constraint identity or program/version identity.

## T6 – Runtime admission and continuity

Existing:
- `CompleteConstraintAcceptance.test_all_frozen_runtime_boundaries`

Add:
- `test_rename_and_reference_continuity`
- `test_successful_relation_admission`
- `test_atomicity_and_staged_artifacts`

Required observations:
- Genuine initial cell and relation checks.
- Successful and rejected writes.
- Successful and rejected activation and trial.
- Rename continuity under the existing normative rules.
- Owned-subtree canonical subject preservation.
- Rejected operations preserve live state, active version,
  registered references and admitted artifact bindings.
- Trials never commit staged changes to the live runtime.

## T7 – Failure boundaries

Existing:
- Task 24 exception, Unknown, call-depth and catch scenarios.
- `test_evaluator_fault_propagates_for_every_operation`

Add:
- `test_failure_provenance_matrix`

Required observations:
- Distinct Unknown, violation, runtime admission rejection,
  host failure, machine limit and restricted-policy rejection.
- Every failure retains its prescribed provenance.
- No host failure becomes catchable SHEAR error.
- No failed admission causes observable mutation.

## T8 – Existing language and semantic corpora

Add:
- `test_existing_corpora_through_candidate_layer`
- `test_public_api_and_golden_compatibility`

Required observations:
- Run all applicable existing semantic/language corpora with
  candidate-backed admission, not only incumbent admission.
- Compare results, failure classes, state transitions and
  relevant canonical identities to baseline observations.
- Run the complete ordinary CI suite.
- Preserve existing public APIs and golden records.
- Report every skipped or inapplicable corpus explicitly.

## T9 – Adversarial execution and version authority

Existing:
- Task 24 candidate-effect and candidate-version scenarios.
- Task 32 restricted-execution regression suites.

Add:
- `test_adversarial_candidate_authority`
- `test_admitted_artifact_authentication`
- `test_evaluator_replacement_and_isolation`

Required observations:
- Attempt unauthorized reads, writes, activation, trials,
  reflection, dynamic dispatch and undeclared external calls.
- Reject invalid or unauthorized emitted chunks before effects.
- No late compilation or fallback following rejection.
- Verify authenticated node, version, chunk and generation.
- Replacement cannot alter the selection pinned for an
  in-progress operation.
- Constraint identity is independent of deployment identity.
- Reject mutated, substituted and invalidated artifacts.

## Generic projection discriminator

The projection tests are independent of constraint truth results.

They must inspect projected content using ordinary SHEAR
functions and verify their authenticated machine execution.

They must cover:
- All 15 canonical semantic kinds.
- Nested collections and semantic records.
- Maps with reversed insertion order.
- Type-sensitive unequal values.
- Round-trip canonical byte equivalence.
- Unchanged EntityID, StateID and VersionID identities.
- Original canonical values remain unchanged.

A Python-only projection test is insufficient.

## Execution evidence

For each test record:
- Candidate commit and admitted deployment identity.
- Evaluator entry and opened machine node.
- Authenticated artifact/version/compiler generation.
- Actual observation and independent expected result.
- Zero incumbent constraint-evaluator calls.
- Whether a failure occurred before or during VM execution.

Do not substitute adapter declarations or runner-call counts
for evidence of execution.

A test with no observed candidate machine entry cannot establish
candidate execution. For scenarios intentionally rejected by
preflight, verify zero machine entry and no observable effects.

## Qualification

Positive qualification requires every existing frozen grader
and every additional named test in this document to pass.

A missing, skipped, unsupported or unimplemented obligation
prevents a positive verdict.

A negative verdict requires a reproducible discriminator,
not merely missing implementation.

An inconclusive verdict must identify the missing evidence
and the next decisive experiment.
