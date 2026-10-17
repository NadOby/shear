# Handoff

Read `CLAUDE.md`, the Workflow section of `docs/roadmap.md`,
issue #118, the relevant Task 24 evidence, roadmap Tasks 25 and 26,
and issues #89 and #116.

Verify claims against the repository. This handoff is a checkpoint,
not independent evidence.

## Current state

- Task: Issue #118 – actionable outcomes from negative and inconclusive tasks.
- Issue: https://github.com/NadOby/shear/issues/118.
- Branch: `task/118-actionable-outcomes`.
- Role: Plan – documentation change committed; independent Plan Review next.
- Baseline main: `2f6b3963fc392fcf096b0c9c38627821c13b73ab`.
- Frozen Plan content head: `ea8c70b93dc1dddd917af775cca8f92bcb6377e4`.
- Plan-owned file: `docs/roadmap.md`.
- No production, test, normative language or golden-record changes.
- No PR opened. Publish approval remains pending.

## Motivating problem

A bounded research task can correctly reject an experiment without
resolving the architectural question that motivated it.

Task 24 rejected its tested A/B/C constraint-function candidates,
but the failure did not determine which missing generic language
capabilities should be implemented next.

A correct negative result must remain publishable. The missing
requirement is an explicit, evidence-based disposition of the
unanswered question.

## Plan scope

Change only the existing Workflow section of `docs/roadmap.md`.

The change introduces no new role, mandatory production work,
new testing infrastructure or retroactive evidence requirements.

Requirements:

1. Separate the motivating question from bounded acceptance.
2. Specify what positive, negative and inconclusive results establish.
3. Distinguish proven limitations, missing capabilities, architectural
   obstacles and implementation defects.
4. Require Execute to identify unsupported and unexecuted scenarios.
5. Require independent Review to verify conclusions and next actions.
6. Allow Resolve to correct conclusions without altering evidence.
7. Require Publish to record the result, remaining question and
   concrete successor, priority, dependencies and discriminator,
   or justify stopping.
8. Preserve frozen acceptance criteria and historical evidence.

A task can finish with a valid negative outcome without modifying
production semantics.

## Evidence used for validation

### Task 24 – issue #56

The bounded A/B/C rejection stands. Successful candidate-integrated
boundary execution was not demonstrated.

Canonical content inspection, generic execution budgeting, external
authority, effect isolation and pre-activation execution remain
capability or integration questions. Candidate failure does not
establish universal impossibility.

The appropriate conclusion distinguishes the successful bounded
kill decision from the unresolved broader architectural question.

Historical Task 24 evidence remains unchanged.

### Task 25 – issue #61

The field-identity experiment is postponed until records are planned.

Its outcome must identify an evidence-supported field-identity model,
or state what further discriminator is required. The absence of
record support is a dependency, not proof that a particular field
model cannot work.

### Task 26 – issue #62

Content consolidation depends on Task 23 measurements and relevant
Task 24 and Task 25 findings.

Its outcome must support consolidation, rejection or explicit
deferral with the missing evidence and prerequisites identified.
A positive consolidation decision creates a separate implementation
task; it does not authorize an implicit refactor.

### Issue #116

Artifact reuse has a measurable performance cost. Revalidation against
the candidate currently lacks a test witness.

Missing test coverage is not evidence that revalidation is redundant.
Any optimization removing it must first establish the required
behavior or obtain an explicit architectural decision.

## Plan acceptance criteria

Independent Review must verify:

- The new requirements apply to research and implementation tasks.
- Every task can publish a negative or inconclusive conclusion.
- A bounded result does not automatically resolve its motivating question.
- Capability gaps cannot be presented as impossibility proofs.
- Implementation defects remain distinguishable from unsupported prototypes.
- The four evidence cases above yield actionable dispositions.
- Next steps have priorities, dependencies and decision criteria.
- A justified decision to stop is permitted.
- Frozen Plan ownership, independent Review and Resolve remain intact.
- No historical evidence or normative language behavior changed.

These are documentation and review acceptance criteria. No executable
test is warranted unless Review identifies a concrete recurring
mechanical failure that a repository check would prevent.

## Owner decisions

No new language architecture or semantic decision is requested by
this task.

Issue #89, concerning a Plan-to-Review shortcut for spec-only tasks,
remains separate. This task does not silently adopt that exception.

Priorities for future implementation remain owner decisions.
The workflow requires proposals and explicit dispositions, not
automatic authorization to implement them.

## Independent Plan Review

Use a fresh context and read-only GitHub access.

1. Verify the base and frozen Plan content commit.
2. Check the complete diff against main.
3. Confirm that only the intended Workflow changed.
4. Audit Plan, Execute, Review, Resolve and Publish obligations.
5. Apply the new rule independently to Tasks 24, 25, 26 and #116.
6. Test the distinctions between negative, inconclusive and defective.
7. Check preservation of falsifiability and frozen acceptance.
8. Check for unnecessary bureaucracy, conflicting rules and
   accidental scope expansion.
9. Classify defects P0–P3 and give a clear Plan Review verdict.

Do not modify files during independent Review.

## Next step

Commit this handoff alone.

Then request independent Plan Review of issue #118 against baseline
`2f6b396` and frozen Plan content head `ea8c70b`.

If Review finds blocking defects, resolve them and repeat independent
Review before proceeding.

Keep the branch unpublished. No PR until Publish.
