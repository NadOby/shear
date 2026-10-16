# Handoff

Read `CLAUDE.md`, the Workflow and Task 24 sections of `docs/roadmap.md`, issue #56, and the Task 24 specifications. Verify this checkpoint independently against the repository.

## Current state

- Task: 24 – constraints as functions.
- Issue: GH-56 – https://github.com/NadOby/shear/issues/56.
- Branch: `task/24-constraints-as-functions`.
- Role: Plan – corrections committed; awaiting independent Plan Review.
- Baseline main: `697b2d73b538ad38b57f12beffd7724fda64a871`.
- Revised frozen Plan head: `97e429787a22e2f76ef142713535e0c74fc4ae9a`.
- This handoff must be committed alone, after the Plan-owned files.
- No production implementation, experimental candidate, or adopt-or-kill result exists.
- No golden changes or normative language changes are authorized.

The earlier Plan checkpoints `e2f87fa` and `a2c5205` are superseded. Execute must use the revised frozen Plan head above, subject to independent Review approval.

## Goal and decision rule

Test whether evaluating canonical semantic constraints through ordinary SHEAR functions preserves the incumbent observable semantics while strictly reducing independently fixed mechanisms. The null hypothesis predicts that no candidate will meet both conditions. A negative experimental result is valid.

Adoption requires all of the following:

1. Complete independent semantic-vector and boundary acceptance, plus remaining T1–T9 obligations and applicable corpora.
2. Genuine ordinary-function execution without hidden incumbent evaluator fallback or unauthorized effects.
3. A scored hypothetical migrated-production architecture with independently verified mechanism removals R exceeding additions A; prototype avoidance alone earns no R credit.
4. At most one generic external-authority boundary and one generic execution budget, with no retained duplicate constraint evaluator.
5. No unapproved change to canonical identity, three-valued logic, budgets, runtime admission, failure provenance, public language semantics, or golden records.

The competing designs remain S (incumbent control), A (callable constraint values), B (ordinary-function interpreter), and C (constraint data compiled to ordinary functions). B and C are the primary bounded experiments. Predictions P1–P7 and the counting rules are unchanged.

## Plan-owned files

Specifications:

- `docs/spikes/constraints_as_functions.md`
- `docs/spikes/constraints_as_functions_mechanisms.md`

Independent oracle and candidate-facing graders:

- `tests/constraint_function_oracle.py`
- `tests/constraint_function_acceptance.py`
- `tests/constraint_function_boundary_acceptance.py`

Acceptance and control tests:

- `tests/test_constraint_function_oracle.py`
- `tests/test_constraint_function_acceptance.py`
- `tests/test_constraint_function_boundaries.py`
- `tests/test_constraint_function_boundary_acceptance.py`

Lane registration:

- `tests/lanes.py`

These files are Plan-owned as of the revised frozen Plan head. Execute must not silently change expectations, scripts, contracts, or specifications.

## Review history and corrections

The earlier review found candidate expectation leakage, incomplete semantic fixtures, missing executable candidate boundary acceptance, ambiguous mechanism accounting, and an unrelated test-runner edit. Corresponding corrections were committed before the previous Plan checkpoint.

An independent Plan Review of branch head `6a6b38c` then identified three blocking defects and a formatting issue. The subsequent Plan revisions address them as follows:

### P1 – Complete boundary-contract qualification

`BoundaryReport.passed` now requires `complete_contract`, the full case count, and no failures. `assess_boundaries` sets `complete_contract` only when the selected cases equal the entire frozen `BOUNDARY_CASES` inventory, including each name, script, expected observation, and order. Diagnostic subsets remain possible but cannot qualify.

Regression tests exercise the prior 14-duplicate counterexample and altered, omitted, or reordered contract content. Independent Review must verify fail-closed behaviour and look for remaining bypasses.

### P2 – Owned-subtree canonical expectation

The `owned_subtree` expected subject is now an independently specified tagged canonical map, including nested `__type__` tags, canonically ordered map entries, and a tagged child `EntityID` key. Grading ignores only the `CanonicalNode` tuple subclass, not tags, ordering, primitive types, or nested content.

Control tests compare this fixed expectation to the incumbent `canonicalize()` output and reject malformed, untagged, reordered, or type-changed subjects. Independent Review must confirm both the expectation and normalization are correct.

### P2 – Positive runtime admission acceptance

The candidate-facing boundary inventory was extended from 14 to 17 mandatory cases, adding:

- `write_satisfied` – accepted write; live content changes to 7 without changing the active version.
- `activation_satisfied` – accepted one-to-one widening; active version changes while cell content remains 4.
- `trial_satisfied` – accepted isolated widening trial; staged trial content is 4, while the main live runtime and active version remain unchanged by the trial.

The grader now compares frozen live-cell content, trial-cell content, active-version change, and staged-trial version agreement, as applicable. Regression tests reject incorrect positive outcomes and transitions. The experiment specification explicitly requires all 17 cases.

### P3 – Formatting

This replacement begins immediately with `# Handoff`, without a leading empty line. No formatting-only edit of Plan-owned files is required.

## Other preserved Plan contracts

- The independent oracle covers all 15 canonical kinds, all existing constraint primitives, complete binary strong-Kleene combinations, and budget-sensitive cases.
- Candidate input does not expose expected outcomes, names, or replay seeds. Candidate adapters must materialize real semantic values from symbolic kind descriptors.
- Every generated seed exercises both unbudgeted logical and budget-sensitive families.
- Mechanism scoring uses the hypothetical migrated production architecture, not just the isolated prototype execution path. Retained production consumers, adapters, and new facilities must all be included.
- `tests/lanes.py` registers all four Task 24 ordinary test modules in `core-model` and restores the single `future.result()` tuple unpacking.
- Plan-owned test doubles validate graders but are not evidence of a candidate implementation. Claimed execution routes, zero fallback calls, and effect isolation require independent instrumentation.

## Verification status

Verified through read-only GitHub inspection:

- Plan specifications, grader, and regression changes are committed through `97e4297`.
- The boundary contract contains 17 scenarios and the test inventory expects 17.
- The revised experiment specification describes all 17 scenarios and their qualification requirements.
- The frozen Plan head above exists and precedes this handoff-only commit.

Not verified:

- Green ordinary CI for the branch; no workflow checks were returned by the available query.
- Execution of the full repository test suite or new boundary regressions.
- Mutation testing for the revised Plan.
- Any experimental candidate's behaviour or a genuine mechanism reduction.

Do not infer test success from the presence of regression tests or from an empty checks result.

## Independent Review obligations

Review in a fresh context, read-only. Check the branch history and all Plan-owned files against main. In particular:

1. Reproduce the 14-duplicate bypass attempt and other full-contract tampering tests.
2. Verify the exact canonical owned-subtree shape against the actual incumbent boundary, not merely against fixture expectations.
3. Confirm successful write, activation, and trial scripts represent executable runtime transitions and the frozen observations exclude incorrect rejection or state changes.
4. Check candidate-input isolation, generated budgets, semantic oracle independence, mechanism-accounting consistency, lane registration, and any available CI.
5. Distinguish verified defects from limitations and hypotheses; classify remaining findings by severity and give a Plan → Execute verdict.

Do not treat this handoff as evidence or begin Execute before independent Plan approval. If approved, start Execute in a separate fresh chat from Plan head `97e429787a22e2f76ef142713535e0c74fc4ae9a`.
