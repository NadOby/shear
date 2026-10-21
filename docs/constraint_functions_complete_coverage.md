# GH-123 Complete Acceptance Coverage

Status: Plan Resolve – pending independent re-review.
Baseline: f994a2d59b0f6f890f4800effe209d88e1c838c1.

Task 24 (#56) supplies the frozen semantic and boundary oracles.
Task 32 (#119) supplies the authenticated restricted execution
implementation and existing security acceptance.

## 1. Qualification rules

T1–T9 are mandatory. The fixtures, expected observations,
Task 24 oracles, boundary scripts and golden records must not be
weakened to accommodate the candidate.

All `tests/constraint_functions_*acceptance.py` modules and the
projection and semantic adversarial modules are Plan-owned.
Their filenames deliberately avoid ordinary `test_` discovery.

Execute must implement the real candidate, register every frozen
suite in CI and complete all applicable existing regressions.

An unexecuted, skipped or unsupported check is not a pass.
An adapter-reported route, verdict or artifact identity is not
independent proof of execution.

## 2. T1 – Three-valued composition

Frozen:
- `CompleteConstraintAcceptance.test_complete_semantic_oracle`
- `CompleteConstraintAcceptance.test_evaluator_fault_propagates_for_every_operation`
- `CompleteConstraintAcceptance.test_evaluator_verdict_controls_semantic_result`
- `DirectEvaluatorAcceptance.test_prepared_evaluators_return_actual_verdicts`
- `CandidateBindingAcceptance.test_selected_expression_and_subject_control_result`
- `CandidateBindingAcceptance.test_valid_verdict_perturbation_reaches_observation`
- All tests in `constraint_functions_semantic_adversarial.py`

Expected:
- Task 24's complete fixed and generated oracle inventory passes.
- Strong Kleene composition, negation and empty operators agree.
- Canonical deduplication and permutation invariance hold.
- Genuine admitted SHEAR computation produces the verdict.
- Subject-dependent answers cannot be supplied by a constant
  evaluator followed by an unrelated Python computation.
- A controlled valid machine verdict changes the observation.

## 3. T2 – Primitive and kind semantics

Frozen:
- Task 24 primitive and kind vectors.
- `FrozenPrimitiveBudgetAcceptance.test_malformed_constraint_inputs`
- `GenericProjectionAcceptance.test_all_fifteen_kinds`
- `GenericProjectionAcceptance.test_type_sensitive_equality`

Expected:
- All nine constraint families and 15 semantic kinds.
- Correct primitive boundaries and type-sensitive equality.
- Invalid construction inputs raise the pinned error classes.
- Missing or wrongly typed roles are not silently accepted.
- Unsupported syntax and host errors cannot become Unknown.

## 4. T3 – Exact semantic budgets

Frozen:
- Task 24 generated-budget vectors.
- `FrozenPrimitiveBudgetAcceptance.test_budget_consumption_trace`
- Semantic adversarial budget/depth/width tests.

Expected:
- Exact consumed constraint-node counts for fixed witnesses.
- Budgets 0, 1, 2, sufficient and unbounded are distinguished.
- Short circuits and deduplication follow Task 24 ordering.
- Semantic budgets do not masquerade as machine fuel limits.
- Budget traces originate in admitted ordinary SHEAR execution.

## 5. T4 – External evaluators

Frozen:
- Task 24 external vectors and boundary cases.
- All seven tests in `constraint_functions_external_acceptance.py`
- Evaluator machine-fault propagation tests.

Expected:
- Missing, Satisfied, Violated and Unknown external verdicts.
- Evaluators receive precisely canonicalized subjects.
- Zero-budget evaluation never calls an external evaluator.
- Escaped host exceptions retain type and identity.
- The blocking external runs in a separate process.
- A supervisor kills it after timeout and verifies both
  admitted evaluator entry and actual callback entry.
- Semantic node budgets do not imply external termination.

## 6. T5 – Semantic inspection, identity and reconstruction

Owner-approved representation correction:
- `docs/constraint_functions_t5_semantic_mapping.md`
  defines the mandatory old-to-new test correspondence.
- Private CanonicalNode paths are superseded by public
  semantic inspection and demand-driven field access.
- The correction does not relax canonical identity,
  execution authenticity or adversarial test strength.

Mandatory:
- All amended tests in `constraint_functions_complete_projection.py`
- All amended tests in `constraint_functions_projection_adversarial.py`
- All amended tests in `constraint_functions_identity_acceptance.py`
- Task 24 `constraint_identity` and `candidate_version` cases.

Expected:
- All 15 kinds retain canonical identities and semantic types.
- Admitted ordinary SHEAR computation performs inspection,
  semantic-path selection and type-sensitive equality.
- Opaque values remain leaves without private serialization,
  identity-payload or closure-internal access.
- Nested data and semantic constraints reconstruct identically
  wherever reconstruction is semantically meaningful.
- Reordering and duplicate composition preserve identity.
- Bool/int, byte/text and sequence-kind distinctions survive.
- Unicode code points and byte values remain distinct.
- Map entries follow canonical-key ordering without exposing
  serialized keys or host insertion order.
- Cell, constraint and relation access uses approved fields.
- Deep, wide, nested, generated, collision and large-value
  adversaries retain or strengthen their prior coverage.
- Demand-driven access avoids eager proportional copying and
  repeated whole-map sorting or serialization.
- Controlled VM output determines the selection, inspection,
  equality or reconstruction result, or triggers explicit
  fail-closed validation.
- A validation rejection identifies the operation and the
  exact rejected VM output.
- Independent source-path review verifies that rejection arose
  from validation and not an unrelated processing failure.
- No subject-dependent Python projection, incumbent fallback
  or forged machine-entry evidence is permitted.
- Constraint identity remains independent of deployment.
- Existing state and version identity rules are unchanged.

## 7. T6 – Runtime admission and continuity

Frozen:
- `CompleteConstraintAcceptance.test_all_frozen_runtime_boundaries`
- `FrozenRuntimeAcceptance.test_t6_runtime_scenarios`
- Task 32 runtime-boundary regression suites.

Expected:
- All 17 frozen Task 24 boundary scenarios pass.
- Seven additional fixed relation, rename and staging cases.
- Initial and subsequent cell/relation checks use the candidate.
- Successes and rejections have exact observed outcomes.
- Explicit continuity rewrites actual relation endpoints.
- Rename is not simulated by an adapter-only name table.
- Failed writes, activations and trials preserve live state.
- Trials preserve existing unrelated cell content.
- Existing references, holds, active versions and artifact
  bindings retain their normative atomicity guarantees.

## 8. T7 – Failure boundaries

Frozen:
- Task 24 exception, catch, Unknown and machine-limit cases.
- All tests in `constraint_functions_failure_acceptance.py`
- `FrozenExternalAcceptance.test_host_failure_escapes_unchanged`
- Task 32 admission/policy/host-failure regressions.

Expected:
- Unknown and Violated remain distinct from host failures.
- Real Runtime exceptions expose the expected entity,
  semantic result and public exception class.
- Runtime admission, restricted-policy and machine-limit
  failures retain distinct provenance.
- Escaped evaluator exceptions cannot become catchable
  SHEAR language errors.
- Rejected operations do not commit effects.
- Tail recursion and depth-limit behavior stay unchanged.

## 9. T8 – Existing language and semantic corpora

Frozen:
- `CandidateCorpusAcceptance.test_complete_existing_example_corpus`
- `CandidateCorpusAcceptance.test_existing_regressions_remain_mandatory`
- Original `shear.examples.EXAMPLES` and all step expectations.
- Existing ordinary CI lane inventory.
- Existing golden records and comparison procedures.

Execute requirements:
- Replay every existing corpus example and scenario.
- Construct actual candidate-backed Runtime instances.
- Check initial constraint admission and subsequent operations.
- Compare every result and expected live-cell observation.
- Run `python -m tests.lanes --all` successfully.
- Run applicable golden, hosted and Task 24 checks.
- Preserve existing public APIs and golden records.
- Record exact SHAs, CI runs and any excluded diagnostic jobs.

The existing corpus and CI are fixed acceptance inputs,
not a new set of scenarios delegated to Execute.
A green incumbent-only CI run is necessary but insufficient.

## 10. T9 – Adversarial authority and isolation

Frozen:
- All tests in `constraint_functions_authority_acceptance.py`
- All tests in `constraint_functions_candidate_effect_acceptance.py`
- Task 24 `candidate_effect` and `candidate_version` cases.
- Existing Task 32 security, boundary and lifecycle suites.
- `CandidateFreshImportAcceptance.test_import_under_poisoning_in_fresh_process`

Expected:
- Wrong issuer, invalidated deployments and rehashed artifact
  substitutions fail without unauthorized machine execution.
- Validly structured but unauthorized code is still rejected.
- Forbidden effects and indirect calls fail closed.
- Candidate-derived dynamic dispatch and forced preflight
  denial fail before unauthorized machine execution.
- Existing Task 32 source, opcode, replacement and admission
  adversaries remain mandatory.
- The operation's selected evaluator remains pinned even if
  registry replacement occurs during its execution.
- No hidden fallback or late lowering rescues rejection.
- Candidate imports under incumbent poisoning in a fresh
  process, not only from an existing Python module cache.
- Unauthorized reads, writes, activation, trials, reflection
  or undeclared external dispatch must not gain authority.

## 11. Candidate-to-machine binding

The authenticated execution evidence must identify:
- Actual selected function entry and semantic operation.
- Canonicalized subject and expression-associated preparation.
- Source state, version and compiler generation.
- Admitted node and exact artifact/chunk identity.
- Actual returned verdict from the selected machine execution.
- No unrestricted machine execution or host lowering during
  observed evaluation.

The direct-result acceptance prepares an evaluator without
receiving the subject or expected verdict and invokes that
same admitted implementation on multiple subjects.

The binding acceptance instruments the adapter's preparation,
restricted invocation, machine invocation, artifact opening
and valid-verdict perturbation.

These are executable discriminators, not a substitute for the
mandatory independent source-path and fallback audit.

## 12. Evidence and completion

Record for every applicable acceptance suite:
- Candidate and baseline SHAs.
- Exact executable test inventory.
- Passed, failed, skipped and unexecuted counts.
- Candidate deployment, evaluator selection and operation.
- Real machine-entry and admitted-artifact observations.
- Expected and observed semantic outcomes.
- Effects, state/version transitions and failures.
- Reproduction commands and CI run URLs.

Performance and mechanism accounting follow
`docs/constraint_functions_complete_benchmarks.md`.

A positive verdict requires all T1–T9 obligations, the
existing frozen graders, complete applicable CI and
independent provenance review.

A failed candidate implementation alone does not establish
architectural impossibility. A negative verdict needs a
minimal reproducible discriminator. An inconclusive verdict
must identify the next decisive experiment.

The owner retains authority over language-shaping changes,
accepted performance exceptions and publication.

## 13. Expanded T5 acceptance inventory

This section extends the mandatory T5 inventory in section 6.
No earlier test or obligation is superseded.

Additional mandatory modules:

- `tests/constraint_functions_nested_record_acceptance.py`
- `tests/constraint_functions_sequence_acceptance.py`
- `tests/constraint_functions_resource_acceptance.py`

The expanded Plan inventory comprises 18 candidate-dependent
modules and 78 test methods.

The original 15 modules and 56 tests remain mandatory.
Inventory counts are not execution results.

Execute must register and run all 18 modules. Unexecuted,
skipped or unsupported tests do not constitute acceptance.

### Nested semantic records

Generated nested-record tests must establish traversal of
actual semantic contents, including canonically normalized
nested values.

Expected paths and values must be derived independently from
original semantic fixtures, not candidate-generated paths or
private canonical serialization.

Named and positional field access, mixed container nesting,
canonical identities and semantic result kinds remain mandatory.

### Generalized sequence operations

Generalized len and slice must preserve Unicode code-point
semantics, bytes, canonical map order, record field ordering,
half-open bounds, result kinds and LanguageError behavior.

Independent causal dependency is required separately for each
supported indexable semantic kind:

- str
- bytes
- tuple
- list
- map
- cell
- constraint
- relation

A machine-result perturbation for one kind cannot establish
dependency for another.

The perturbation must substitute genuine authenticated machine
returns of a compatible machine-level contract.

No fixed number of evaluator invocations or assumption about
the complete adapter-return shape is permitted.

### Constraint reconstruction

Preserve all original canonical reconstruction witnesses,
equivalence cases and type-sensitive distinctions.

Independently establish machine-result dependency for each
of the nine supported constraint forms:

- is_kind
- int_range
- length
- one_of
- all_of
- any_of
- not
- role
- external

For each form, compatible genuine machine-output substitution
must change the observation or produce explicit fail-closed
validation rejection with exact substituted-output provenance.

A single successful form cannot qualify the complete inventory.

### Resource efficiency

The resource acceptance uses test-owned whole-invocation
measurement, not candidate-reported counters or nominated
Python tracing boundaries.

Execute supplies reusable prepared operations through:

    prepare_resource_probe(canonical_value, operation)

A test-only "control" mode provides matched admitted invocation
overhead without subject inspection.

Resource measurements must account for:

- Input canonicalization and preparation before measurement.
- Authenticated execution and invocation overhead.
- Whole-invocation process CPU time.
- Peak Python-traced allocation.
- Python and native call coverage.
- Matched control overhead.
- Measurement noise and calibration sensitivity.

Synthetic large-copy and native-sort controls must demonstrate
that the measurement can detect relevant scaling defects.

Required witnesses include repeated map indexing, large sequence
access, relation-role contents, constraint operands and shallow
inspection.

Complete semantic contents and ordering must be verified,
not merely result sizes.

Resource bounds must distinguish avoidable copying from storage
and processing necessarily required to materialize explicitly
requested proportional-size results.

An implementation satisfying the public semantic and resource
contract must not fail merely because its representation
requires legitimate output materialization.

Independent source-path auditing must examine delegated helpers,
native operations, sorting, serialization, control equivalence
and possible unmeasured or host-side semantic work.

Whole-invocation measurement is not independent proof of
execution authenticity.

### Preserved requirements

The expanded T5 suite introduces no additional public SHEAR
operation beyond the separately approved inspection interface.

Task 24 semantics, Task 32 security, all 17 frozen boundary
cases, canonical identities and golden records remain unchanged.

All authenticated execution, no-fallback and independent
provenance requirements remain mandatory.

### Review and approval

Independent Review must verify:

- Test completeness and non-vacuity.
- Per-kind and per-form causal dependency.
- Genuine VM returns and unchanged-return controls.
- Measurement completeness and noise sensitivity.
- Correct treatment of proportional-size requested outputs.
- Compatibility with `docs/semantic_inspection.md`.
- Registration of the complete acceptance inventory.

Candidate-dependent suites remain unexecuted during Plan.
Ordinary CI success does not establish their correctness.

Execute remains blocked until independent Plan approval.
