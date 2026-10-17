# Handoff

Read `CLAUDE.md`, the Workflow section of `docs/roadmap.md`,
issue #89 and the Task 28 and issue #118 precedents.

Verify all claims against the repository. This file is a checkpoint,
not independent evidence.

## Current state

- Issue: #89 – flexible workflow stages.
- Branch: `task/89-flexible-workflow`.
- Role: Plan complete – request independent Review.
- Baseline `main`: `9151949a652de8100cc7e6c0581b3b078269f21d`.
- Frozen Plan content head: `cf3e2d7af288112c38304d31a40644424b8c6b1b`.
- Plan-owned files: `CLAUDE.md` and `docs/roadmap.md`.
- No production, test, golden-record or language-semantic changes.
- No substantive Execute work remains.
- No PR opened for #89 at this checkpoint.

## Motivating problem

The current workflow requires separate task-role transitions even
when Plan already contains the complete deliverable, Review finds
no blocking defect, or Publish can be performed by the existing
execution context after independent approval.

Task 28 and issue #118 demonstrated unnecessary no-op transitions.

## Plan deliverable

Update the existing workflow contracts, without introducing a new
role, review infrastructure or language-design change.

- Five responsibilities remain: Plan, Execute, Review, Resolve,
  Publish. They need not run in separate chats.
- Execute is required only when substantive work remains after Plan.
- A complete Plan deliverable may proceed directly to independent
  Review and then Publish.
- Review always uses a fresh independent context, including when
  the deliverable was produced during Plan.
- Resolve is conditional on Review findings and requires re-Review.
- Publish may happen in the Plan or Execute context, or through
  the owner, after accepted independent Review.
- Substantive post-review changes require renewed independent Review.
- Publication-only metadata can be finalized after Review without
  changing the reviewed contract or evidence.
- Frozen terminal acceptance, Plan ownership, owner authority,
  independent Review and applicable CI requirements remain intact.
- Missing CI evidence must be reported, not represented as success.
- No empty Execute, Resolve, Publish chat or handoff is required.

## Acceptance

Independent Review should verify the following.

1. Task 28's specification-and-test deliverable can complete in
   Plan and proceed directly to independent Review and Publish.
2. Issue #118's completed workflow-documentation deliverable can
   follow the same path without a ceremonial Execute stage.
3. Ordinary implementation tasks still require Execute when
   substantive work remains.
4. The preparer cannot certify their own deliverable.
5. Resolve corrections and substantive post-review edits receive
   renewed independent Review.
6. Frozen acceptance criteria, Plan-owned files, owner decisions
   and historical evidence remain protected.
7. Publish may be performed in the same Plan or Execute context
   after Review approval, without a separate Publish chat.
8. Applicable CI and final-diff verification remain required.
9. The change introduces no production semantics, new bureaucracy
   or unnecessary scope expansion.

No new executable acceptance test is planned for this
documentation-only workflow clarification.

## Diff notes

The Plan consists of three commits:

- `39945c1` – align `CLAUDE.md`.
- `010b260` – revise the roadmap Workflow.
- `cf3e2d7` – restore unrelated changes outside Workflow.

One unrelated nonsemantic line-wrap change remains in the
hosted-bootstrap section of `docs/roadmap.md`, near the paragraph
beginning "The acceptance anchors". Classify it independently.
Do not alter historical contracts to resolve a formatting concern.

## Next step

Request fresh, read-only independent Plan Review against
baseline `9151949` and Plan content head `cf3e2d7`.

Review the complete branch diff, issue #89, the existing Workflow,
Task 28 and issue #118. Classify remaining defects P0–P3 and give
a clear verdict on Plan → Review → Publish without Execute.

If Review finds blocking defects, Resolve them and obtain a
new independent Review before Publish.

After approval, append the required `CHANGES.md` entry, verify
the final diff and applicable CI, and open a PR closing #89.
