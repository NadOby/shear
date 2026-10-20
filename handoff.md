# Handoff

## Current state

- Issue: #107 – mutation survivor repin revalidation.
- Branch: `task/107-repin-revalidation`.
- Baseline: `4cb022747b80fa94860cb8b97d7992d468de9dde`.
- Frozen documentation deliverable: `8a0f5a90bd67fde628ea809fc74032801535dcb1`.
- Plan-owned files: `docs/roadmap.md`,
  `docs/verification_hardening.md`, `CHANGES.md`.
- Role: Resolve – independent re-Review required.
- Independent Review: REQUEST RESOLVE (one P2, one P3).
- No production, test or golden-record changes.
- No PR opened.

## Deliverable

- Review and Publish reject repins without complete same-head
  revalidation of affected classified survivors.
- Existing CI campaigns provide JSONL execution evidence.
- Review verifies every affected key actually executed and survived
  with matching source and engine pins.
- Sampling, skipped mutants and post-merge evidence are insufficient.
- Ordinary PR testing and mutation infrastructure remain unchanged.

## Review resolution

- P2 – stale handoff: replaced the #124 checkpoint with this
  #107 checkpoint. Reviewed deliverable and baseline are identified.
- P3 – historical wording in `docs/verification_hardening.md`:
  non-blocking; unchanged. It describes the earlier documentation
  move, not the new #107 requirements.
- Full campaigns remain acceptable for infrequent repins.
  No survivor-only execution mode is introduced.

## Verification

- Ordinary CI passed at `8a0f5a9`: run `39375493165`.
- The `tests` job succeeded. Optional mutation campaign was skipped,
  as expected for this documentation-only change.
- Final-head CI must be checked after this metadata correction.

## Next action

1. Verify this commit and applicable CI.
2. Obtain independent re-Review of the complete final diff.
3. After approval, Publish with `Closes #107`.

The owner retains publication authority.
