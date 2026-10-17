# Handoff

Read `CLAUDE.md`, the Workflow and Task 24 sections of
`docs/roadmap.md`, issue #56, both frozen Task 24 specifications,
and `docs/spikes/constraints_as_functions_execute.md`.

Verify every claim against GitHub. This handoff is a checkpoint,
not independent evidence.

## Current state

- Task: 24 – constraints as functions.
- Issue: GH-56 – https://github.com/NadOby/shear/issues/56.
- Branch: `task/24-constraints-as-functions`.
- Role: Execute complete – independent Review next.
- Baseline main: `697b2d73b538ad38b57f12beffd7724fda64a871`.
- Frozen Plan head: `97e429787a22e2f76ef142713535e0c74fc4ae9a`.
- Execute evidence head: `cac07b092993caab40ef7cd71589115d3e56ba6e`.
- Proposed result: kill A, B and C; retain S.
- No production constraint semantics were changed.
- No normative language changes or golden changes were authorized.
- No Publish approval has been given.

This handoff update is the final Execute checkpoint. Its own commit
will follow the evidence head.

## Goal and frozen decision rule

Determine whether semantic constraints can be evaluated through
ordinary SHEAR functions while preserving observable semantics and
strictly reducing independent fixed mechanisms.

Adoption requires all mandatory semantic and boundary discriminators,
no hidden incumbent evaluator fallback, correct effect and authority
boundaries, and a verified migrated-architecture mechanism count
with R strictly greater than A.

A negative result is a valid experiment outcome.

The frozen predictions P1–P7, acceptance contracts and counting
taxonomy remain unchanged.

## Frozen Plan-owned files

Specifications:

- `docs/spikes/constraints_as_functions.md`
- `docs/spikes/constraints_as_functions_mechanisms.md`

Independent oracle and graders:

- `tests/constraint_function_oracle.py`
- `tests/constraint_function_acceptance.py`
- `tests/constraint_function_boundary_acceptance.py`

Regression and acceptance infrastructure:

- `tests/test_constraint_function_oracle.py`
- `tests/test_constraint_function_acceptance.py`
- `tests/test_constraint_function_boundaries.py`
- `tests/test_constraint_function_boundary_acceptance.py`
- `tests/lanes.py`

The diff from frozen Plan head `97e4297` to Execute head
`cac07b0` changes none of these files.

Review must verify this independently.

## Execute-owned changes

Experimental probes:

- `tests/constraint_function_a_probe.py`
- `tests/constraint_function_b_probe.py`
- `tests/constraint_function_c_probe.py`
- `tests/constraint_function_disqualification_probe.py`

Evidence:

- `docs/spikes/constraints_as_functions_execute.md`

CI:

- `.github/workflows/semantic-model.yml`

The CI change adds a separate experimental-probe step using
`unittest discover`. It does not alter the frozen `tests/lanes.py`.

No production SHEAR modules were changed.

## Candidate A – direct callable substitution

Seven executable witnesses examine canonical identity, callable
representation, deployment dependence, execution before runtime
admission, and independence from external evaluator context.

Direct callable substitution fails prerequisite compatibility:
ordinary functions and entity references are not cell constraints,
callable deployment affects program identity, and ordinary function
execution requires a loaded runtime.

These observations support P3 and aspects of P5.

No complete A implementation or boundary adapter was built.

Verdict: kill direct callable substitution within the bounded scope.

This is not proof that every conceivable callable design is impossible.

## Candidate B – ordinary-function interpretation

The positive witness executes tuple-form interpretation through a
genuine SHEAR function and the ordinary VM.

Negative witnesses demonstrate missing canonical-data operations:

- Constraint-field projection.
- Canonical map and role access.
- Complete Length semantics.

The full frozen semantic grader was invoked with all fixed cases
and 100 generated seeds from each family.

The bounded B adapter does not pass semantic acceptance.

All 17 frozen boundary cases were submitted to the grader.
Every script was rejected as unsupported because B has no
candidate-integrated runtime admission path.

The boundary scripts were not executed as successful runtime
transitions. Rejections are disqualification evidence only.

Verdict: kill the bounded B interpreter as a replacement.

## Candidate C – compilation into ordinary functions

The compiler materializes canonical constraints and emits
ordinary SHEAR function bodies for:

- OneOf.
- Not.
- AllOf.
- AnyOf.

These generated bodies execute through the real VM.

Missing functionality includes required primitives, node-budget
equivalence, External authority and failure semantics, admission
integration, and verified effect isolation.

The full frozen semantic grader was invoked with all fixed cases
and both default generated families.

The bounded C adapter does not pass semantic acceptance.

All 17 frozen boundary scenarios were submitted and rejected as
unsupported. No candidate-integrated admission transitions ran.

The compiler is a new independent fixed translation mechanism.
Ordinary execution of its output does not make compilation free.

Verdict: kill the bounded C compiler as a replacement.

## Mechanism accounting

The frozen taxonomy identifies:

- M1 – Dedicated constraint execution and composite dispatch.
- M2 – Constraint-node budget.
- M3 – Named External dispatch.
- M4 – Escaping host-failure provenance.

Verified migrated-production removals:

- A: R = 0.
- B: R = 0.
- C: R = 0.

The complete addition counts for hypothetical fully migrated
architectures remain unresolved.

C demonstrates at least one new fixed translation mechanism.
B would require additional canonical-data capabilities and
possibly new generic execution and authority mechanisms.

No prototype replaces all existing production consumers of
`Constraint.evaluate`, including initial loading, writes,
relation checks, activation and trial.

A numerical net mechanism score is withheld rather than
treating unimplemented facilities as zero-cost additions.

The conjunctive adoption rule rejects the candidates independently:
none passes the mandatory semantic and boundary criteria.

The bounded experiment does not establish a universal lower bound
on the mechanism cost of all possible future designs.

The full provisional ledger and counterfactual analysis are in
`docs/spikes/constraints_as_functions_execute.md`.

## Verification

Verified CI runs:

- `38971853124` – B probes and registered lanes passed.
- `38972471297` – B/C probes passed.
- `38974323233` – A/B/C probes passed.
- `38974990376` – full frozen rejection-grader tests passed.
- `38976315088` – final Execute evidence head passed.

Latest verified CI:

https://github.com/NadOby/shear/actions/runs/38976315088

The latest run completed successfully at `cac07b0`, including:

- Registered semantic lanes.
- Experimental A/B/C probes.
- Frozen disqualification tests.
- Golden-record comparison.

These are passing tests of bounded witnesses and expected failures,
not evidence of complete candidate acceptance.

No new mutation campaign specific to these experimental probes
is claimed.

## Remaining limitations

- No successful candidate-integrated execution of the 17 boundary
  scenarios.
- No complete B interpreter or C compiler supporting the entire
  semantic algebra.
- No replacement for constraint-node budgeting, named External
  authority, escaping host-failure provenance or effect isolation.
- No fully validated migrated-production architecture with exact
  numerical addition counts.
- No proof that every possible future function-based architecture
  would fail the mechanism-reduction criterion.

These are limitations of the negative experiment, not claims of
successful candidate coverage.

Independent Review must determine whether they are acceptable for
a bounded kill verdict or constitute unfinished mandatory work.

## Independent Review obligations

Review Task 24 in a fresh context, read-only.

1. Fetch the current branch and main. Read the frozen Plan, issue,
   specifications, Execute evidence, CLAUDE.md and roadmap.
2. Verify the Plan head and all Execute diffs. Confirm that no
   Plan-owned expectations, scripts or golden declarations changed.
3. Independently examine the A identity and bootstrap witnesses.
   Determine whether the claimed obstacles actually follow.
4. Inspect B's real VM path and canonical-data negative witnesses.
   Distinguish missing capability from implementation defects.
5. Inspect C's generated functions, canonical construction,
   normalization and actual execution route.
6. Verify that the full frozen semantic campaign was invoked and
   that the recorded failures are genuine, not hidden successes.
7. Verify the complete 17-case boundary inventory. Confirm that
   script rejection is not misrepresented as boundary equivalence.
8. Audit incumbent fallback, generated result claims, unauthorized
   effects and any hidden use of the dedicated evaluator.
9. Independently audit M1–M4, production consumers, candidate
   additions and the migration counterfactual.
10. Check whether failure of the mandatory criteria justifies
    terminating the bounded experiment without a complete
    numerical R-minus-A result.
11. Review CI, runner registration, reproducibility, documentation
    consistency and the evidence report's limitations.
12. Classify findings as verified defects, limitations, hypotheses
    or documentation drift, with P0–P3 severities for defects.

Explicitly assess whether the proposed kill verdict satisfies the
frozen Plan, or whether any required experiment was prematurely
terminated.

Do not modify production code, Plan-owned files or handoff during
independent Review.

## Next step

Commit this handoff alone.

Then start a fresh chat with:

`Review Task 24 on task/24-constraints-as-functions against frozen
Plan head 97e4297 and independently verify the proposed kill verdict.
Read-only. Classify findings by severity and give an Execute → Review
verdict.`

If Review identifies blocking defects, enter Resolve and repeat
independent Review.

Do not enter Publish until the independent Review accepts the final
Task 24 result.
