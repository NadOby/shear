# Handoff

## Current state

- Issue: #124 – decisive experiments and planning maintenance.
- Branch: `task/124-decisive-experiments`.
- Baseline: `9dc13c7b97084631b9c451b2f24c587fc4cd77eb`.
- Initial reviewed Plan: `7121fbbdb6ec6f7785c0f98396d2929b4e894a16`.
- Independent Plan Review: REQUEST RESOLVE (three P2, one P3).
- Final substantive Resolve head: `d035ba139ef40846546e455617b01d49250ca3bc`.
- Role: Resolve complete; independent re-Review pending.
- Execute unnecessary: documentation-only deliverable.
- No PR opened.

## Resolution

### P2 – Roadmap maintenance

- GitHub issues are authoritative for task definitions and completion.
- `docs/roadmap_active.md` is a short priority/dependency index.
- Completion alone requires no roadmap update.
- Historical roadmap entries are not moved at completion.
- Tasks 25–26 have stable references to issues #61 and #62.

### P2 – Plan head

The reviewed Plan was `7121fbb`. The substantive Resolve content
is pinned above at `d035ba1`. This handoff update is metadata only.

### P2 – Task 25 experimental control

Issue #61 now explicitly requires varying one experimental dimension
at a time. Its full experiment and completion criteria are preserved.

### P3 – Unnumbered follow-ups

Workflow supports commands such as `Plan issue #123`.
Follow-ups retain their GitHub issue labels and close through PRs.
The active index changes only when priorities or dependencies change.

## Additional improvements

- Planning favors decisive, falsifiable architectural experiments.
- Mobile editing supports complete replacement below roughly 300 lines
  or verified, bottom-to-top line-numbered edits in larger files.
- `CHANGES.md` remains append-only.
- No new workflow stage, template or mandatory synchronization.
- No production code, tests or golden records changed.

## Verification

- Task 32 (#119) merged through PR #125.
- Its restricted-execution results remain bounded; full constraint
  equivalence is open under #123.
- Task 32's frozen technical acceptance and historical evidence remain
  unchanged.
- CI at `a73e3fb` passed.
- Final Resolve CI must be verified before Publish.

## Next action

1. Independently re-Review the complete diff against the baseline,
   including issues #61 and #62 and the original Review findings.
2. Verify final CI and documentation checks.
3. Resolve new findings only if required, followed by re-Review.
4. After approval, Publish through a PR containing `Closes #124`.

The owner retains architectural and publication authority.
