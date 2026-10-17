# Handoff

Read `CLAUDE.md`, the Workflow section of `docs/roadmap.md`,
issue #118, relevant Task 24 evidence, roadmap Tasks 25 and 26,
and issues #89 and #116.

Verify claims against the repository. This handoff is a checkpoint,
not independent evidence.

## Current state

- Task: Issue #118 – actionable outcomes from negative and inconclusive tasks.
- Issue: https://github.com/NadOby/shear/issues/118.
- Branch: `task/118-actionable-outcomes`.
- Role: Plan revised after independent Review – repeat Review next.
- Baseline main: `2f6b3963fc392fcf096b0c9c38627821c13b73ab`.
- Original Plan content head: `ea8c70b93dc1dddd917af775cca8f92bcb6377e4`.
- Revised Plan content head: `18e4dbfc576d1bcd98d2347d265c3856b2a833c2`.
- Plan-owned file: `docs/roadmap.md`.
- No production, test, normative language or golden-record changes.
- No PR opened. Publish approval remains pending.

## Motivating problem

A bounded research task can correctly reject an experiment without
resolving the architectural question that motivated it.

Task 24 rejected its tested A/B/C constraint-function candidates,
but the failure did not determine which missing generic language
capabilities should be implemented next.

A correct negative result must remain publishable when it satisfies
the frozen terminal acceptance criteria. The additional requirement
is an explicit, evidence-based disposition of the unanswered question.

Actionability cannot substitute for mandatory acceptance.

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
   or justify stopping with the required owner approval.
8. Require satisfaction of frozen terminal acceptance criteria before
   a task can conclude, regardless of the outcome's actionability.
9. Reuse existing tracking issues instead of creating duplicates.
10. Preserve frozen acceptance criteria and historical evidence.

A research task can finish with a valid negative outcome without
modifying production semantics, provided its terminal acceptance
criteria permit that outcome.

## Evidence used for validation

### Task 24 – issue #56

The bounded A/B/C rejection stands. Successful candidate-integrated
boundary execution was not demonstrated.

Canonical content inspection, generic execution budgeting, external
authority, effect isolation and pre-activation execution remain
capability or integration questions. Candidate failure does not
establish universal impossibility.

The bounded kill decision satisfied the historical research contract.
The broader architectural question remains unresolved and needs
a separately prioritized successor or an explicit owner disposition.

Historical Task 24 evidence remains unchanged.

### Task 25 – issue #61

The field-identity experiment is postponed until records are planned.

Its frozen completion requirement calls for determining which
field-identity model holds and what records need from it.

An inconclusive result may identify useful next experiments, but
does not automatically satisfy that requirement. The task must
remain incomplete or return to Plan for an explicitly revised
contract if its evidence cannot satisfy terminal acceptance.

The absence of record support is a dependency, not proof that a
particular field model cannot work.

### Task 26 – issue #62

Content consolidation depends on Task 23 measurements and relevant
Task 24 and Task 25 findings.

Its outcome must support a decision to consolidate or retain the
current representation, or establish that an explicit deferral
satisfies its applicable terminal contract.

An actionable but insufficiently supported decision cannot
substitute for that contract.

A positive consolidation decision creates a separate implementation
task; it does not authorize an implicit refactor.

### Issue #116

Artifact reuse has a measurable performance cost. Revalidation against
the candidate currently lacks a test witness.

Missing test coverage is not evidence that revalidation is redundant.
Any optimization removing it must first establish the required
behavior or obtain an explicit architectural decision.

The existing issue tracks this work. No duplicate is required.

## Independent Plan Review – first pass

Review examined branch head `4b855aa` against baseline `2f6b396`
and original frozen Plan content head `ea8c70b`.

Verdict: changes required before Plan → Execute.

P0: None.
P1: None.

### P2 – Terminal acceptance

Finding: An actionable negative or inconclusive conclusion could be
mistaken for completion of a mandatory implementation or a research
task whose frozen acceptance requires a determinate answer.

Resolution: `docs/roadmap.md` now explicitly requires satisfaction
of frozen terminal acceptance criteria. Otherwise the task remains
incomplete and returns to Plan for an explicitly revised contract.

### P2 – Indefinite deferral authority

Finding: Publish could indefinitely defer an unresolved
architectural question without owner approval.

Resolution: Explicit owner approval is now required to stop or
indefinitely defer a substantive unresolved architectural question.
Publish may recommend that disposition but cannot decide it alone.

### P3 – Duplicate follow-up issues

Finding: The original requirement could create another issue
for work already tracked, such as issue #116.

Resolution: Publish now links existing issues and creates new
follow-ups only for genuinely new work.

### P3 – Stale handoff

Finding: The handoff instructed the owner to commit a file
that had already been committed.

Resolution: This handoff records the completed Plan Review,
subsequent correction and next independent Review.

## Revised Plan acceptance criteria

Independent Review must verify:

- The new requirements apply to research and implementation tasks.
- A negative or inconclusive task outcome can be accepted only when
  the frozen terminal acceptance criteria permit it.
- Actionability never replaces mandatory acceptance.
- A bounded result does not automatically resolve its motivating question.
- Capability gaps cannot be presented as impossibility proofs.
- Implementation defects remain distinguishable from incomplete prototypes.
- Tasks 24, 25 and 26 and issue #116 produce defensible dispositions.
- Next actions have priorities, dependencies and decision criteria.
- Existing tracking issues are reused instead of duplicated.
- Stopping or indefinitely deferring a substantive unresolved
  architectural question requires explicit owner approval.
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

The new workflow explicitly reserves permanent abandonment or
indefinite deferral of substantive unresolved architectural questions
for owner approval.

## Independent Plan Review – next pass

Use a fresh context and read-only GitHub access.

1. Verify baseline `2f6b396`, original Plan head `ea8c70b`
   and revised Plan content head `18e4dbf`.
2. Check the complete branch diff against main.
3. Confirm the four previous P2/P3 findings are resolved.
4. Verify terminal acceptance cannot be bypassed by actionability.
5. Verify substantive indefinite deferral requires owner approval.
6. Verify existing follow-up issues can be reused.
7. Apply the rules independently to Tasks 24, 25 and 26 and issue #116.
8. Verify frozen acceptance, independent Review and historical evidence.
9. Check unnecessary bureaucracy, contradictions and scope expansion.
10. Classify remaining defects P0–P3 and give a Plan → Execute verdict.

One non-blocking unrelated line-wrap change remains in the
historical Task 29 section of `docs/roadmap.md`, near line 1008.
Restore it before Publish if Review confirms that it is outside scope.

Do not modify files during independent Review.

## Next step

Request a fresh independent Plan Review against the revised Plan
content head `18e4dbf`.

If blocking defects remain, resolve them and repeat Review.

Do not open a PR until Publish.
