
# Handoff

Read `CLAUDE.md`, the Workflow section and Task 24 in
`docs/roadmap.md`, issue #56, and both Task 24 experiment specifications.
Verify this checkpoint against GitHub before relying on it.

## Current state

- Task: 24 – constraints as functions.
- Issue: GH-56, https://github.com/NadOby/shear/issues/56.
- Branch: `task/24-constraints-as-functions`.
- Role: Plan – revised following independent Plan Review.
- Baseline main: `697b2d73b538ad38b57f12beffd7724fda64a871`.
- Frozen revised Plan head: `a2c5205a40ea03169c0fa4933e6bfc4f5c2319a1`.
- The next commit changes only this handoff.
- Original Plan head `e2f87fa` is superseded.
- Next role: independent Plan Review, then Execute only if accepted.
- No production implementation or experimental candidate exists.
- No adopt-or-kill verdict has been reached.
- No golden records or production semantics have changed.

## Goal

Determine experimentally whether evaluating semantic constraints
through ordinary SHEAR functions preserves the current semantics
while strictly reducing independent fixed mechanisms.

The null hypothesis is that no candidate satisfies both conditions.

A negative result is a valid completed experiment.

## Independent Plan Review and corrections

The independent review of the original Plan head `e2f87fa`
requested changes for three blocking acceptance weaknesses,
one mechanism-accounting ambiguity and one runner cleanup.

### P1 – Candidate access to expected results

Resolved in the Plan interface.

`tests/constraint_function_acceptance.py` now passes
`CandidateInput`, containing only:

- expression;
- subject;
- constraint-node budget;
- external configuration.

Expected results, fixture names and replay seeds remain in
the grader, not in the candidate input.

The harness makes detached copies of mutable inputs.
Regression tests check isolation and independent grading.

This prevents direct use of `vector.expected` through the
candidate interface. It is not proof against malicious
introspection of the test framework; independent execution-path
inspection remains mandatory.

### P2 – Incomplete semantic fixtures

Expanded the independent oracle.

Fixed candidate-facing cases now include:

- All 15 canonical semantic kinds.
- All existing constraint primitives.
- Complete binary strong-Kleene AND/OR combinations.
- All three NOT outcomes and empty compositions.
- Canonical duplicate and operand-order cases.
- Explicit node-budget and short-circuit cases.

Each generated seed produces:

1. An unbudgeted logical tree.
2. A budget-sensitive primitive/composite case.

`KindSample` represents semantic record kinds symbolically.
Candidate adapters must materialize genuine semantic values.

The oracle imports no production SHEAR semantics.
The incumbent control tests compare observations against its
independently specified expectations.

### P2 – Missing candidate integration contract

Added Plan-owned candidate boundary acceptance:

- `tests/constraint_function_boundary_acceptance.py`
- `tests/test_constraint_function_boundary_acceptance.py`

Fourteen frozen scenarios cover:

- External failure and language catch.
- Missing external evaluators.
- Initial loading and rejected writes.
- Relation constraint rejection.
- Activation and trial rejection.
- Owned-subtree subjects.
- Constraint identity and evaluation context.
- Call-depth and tail-recursion distinctions.
- Unauthorized effects.
- Version-independent constraint identity.

Execute supplies the `BoundaryCandidate` adapter and executes
these scripts through actual candidate runtime/language paths.

Expected observations belong to Plan. Unsupported scripts,
exceptions, invalid routes and mismatches fail grading.
Passing a subset is not a complete boundary pass.

The boundary protocol and its test doubles are not themselves
evidence of a working candidate. Independent Review must verify
that the adapter implements the prescribed transitions faithfully
rather than fabricating observation fields.

### P2 – Mechanism-accounting counterfactual

Clarified in
`docs/spikes/constraints_as_functions_mechanisms.md` section 6.

Two distinct boundaries are required:

1. Isolated candidate execution path – evidence that incumbent
   mechanisms are used, duplicated, avoided or unresolved.
2. Hypothetical migrated production architecture – the scored
   counterfactual including all production consumers, required
   adapters, retained mechanisms and new facilities.

Only verified counterfactual removals receive R credit.
All additions necessary in the same migrated architecture
contribute to A.

Bypassing incumbent code in an isolated prototype does not
by itself count as removal.

Unresolved removals receive zero credit.

### P3 – Unrelated runner edit

Resolved.

`tests/lanes.py` registers the new boundary test module in
`core-model` and restores the original single unpacking of
`future.result()`.

## Frozen Plan-owned files

Specifications:

- `docs/spikes/constraints_as_functions.md`
- `docs/spikes/constraints_as_functions_mechanisms.md`

Independent oracle and candidate-facing graders:

- `tests/constraint_function_oracle.py`
- `tests/constraint_function_acceptance.py`
- `tests/constraint_function_boundary_acceptance.py`

Acceptance and regression tests:

- `tests/test_constraint_function_oracle.py`
- `tests/test_constraint_function_acceptance.py`
- `tests/test_constraint_function_boundaries.py`
- `tests/test_constraint_function_boundary_acceptance.py`

Test registration:

- `tests/lanes.py`

These files are Plan-owned as of the frozen revised Plan head.
Execute must not silently change their expectations.

## Competing designs

S – Incumbent dedicated evaluator, serving as control.

A – Directly callable constraint values.

B – Canonical constraint data interpreted by ordinary SHEAR
functions.

C – Canonical constraint data compiled into ordinary SHEAR
functions.

The primary bounded experiments are B and C.

Assess A using identity and pre-activation execution witnesses
before investing in a full prototype.

Predictions P1–P7 and acceptance requirements T1–T9 are frozen
in `docs/spikes/constraints_as_functions.md`.

## Frozen semantic requirements

- Canonical constraint identity is independent of evaluation,
  deployment, versions and execution artifacts.
- Three-valued results obey strong Kleene logic.
- Unknown is distinct from violation and execution failure.
- Primitive semantics, canonical subjects and composite set
  semantics remain unchanged.
- Existing constraint-node budget behaviour is preserved.
- Missing external evaluators yield Unknown.
- Escaping evaluator exceptions remain host/model failures,
  not catchable program errors.
- Only Satisfied permits runtime admission.
- Rejected operations preserve the relevant live state.
- Relation subjects preserve ownership and endpoint semantics.
- Public language semantics and golden records remain unchanged.

No golden changes are authorized.

## Execute requirements

1. Verify the frozen Plan head and establish baseline results.
2. Execute the Plan-owned oracle, grader and boundary tests.
3. Implement isolated candidate designs without silently
   replacing the production constraint path.
4. Supply separate semantic and boundary adapters for each
   candidate, without access to grader expectations.
5. Execute actual candidate computation for every accepted case.
6. Test remaining T1–T9 obligations, including successful
   transitions, malformed inputs, non-termination, continuity,
   encoding and relevant full corpora.
7. Independently instrument evaluator fallback, execution
   routes, authority boundaries and side effects.
8. Record candidate-path and migrated-architecture ledgers.
9. Count R and A against the same migrated architecture.
10. Compare observations with P1–P7 and record adopt or kill.

No adapter may silently substitute the incumbent evaluator.

A reported zero fallback count is not proof of independence.
A reported zero side-effect count is not proof of isolation.

Execute may add implementation tests and instrumentation, but
may not weaken Plan-owned expectations to fit candidate results.

## Owner decisions reserved

D24-1 – Constraint identity versus callable identity.

Recommendation: preserve canonical constraint identity.
Callable substitution does not authorize a normative change.

D24-2 – Generic execution budget and external boundary.

Recommendation: permit bounded prototypes for measurement.
Normative language or VM additions require owner approval.

D24-3 – Scope of experimental success.

Recommendation: successful evidence may justify a migration
proposal, not an automatic production migration.

These decisions remain Provisional.

## Verification status

Verified against GitHub:

- The revised Plan head exists at `a2c5205`.
- The Plan Review corrections are committed.
- `tests/lanes.py` registers the new test module and restores
  the single tuple unpacking.
- Current main remains at baseline `697b2d7`.

Not verified:

- Complete Task 24 ordinary CI.
- Successful execution of the expanded acceptance suite.
- Mutation-test results for this Plan revision.
- Any experimental candidate or mechanism-removal claim.

At the time of handoff preparation, the commit-status and
pull-request workflow queries returned no reported checks.
Do not interpret this as green CI.

The revised Plan requires another independent review before
Execute. Review must specifically inspect the correctness
and completeness of the new fixture expectations and the
candidate boundary protocol.

## Next step

Commit this handoff alone, leaving all Plan-owned files
unchanged.

Then conduct an independent, read-only Plan Review against
the revised frozen Plan head `a2c5205`.

If the revised Plan is accepted, start Execute in a separate
fresh chat. Do not Execute merely because this handoff says
the corrections were made.
