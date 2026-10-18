# Handoff

Read `CLAUDE.md`, the Workflow section of `docs/roadmap.md`,
issue #119, `docs/restricted_execution.md`, and the Task 24
experimental evidence. Verify all claims against the repository.

This file is a checkpoint, not independent evidence.

## Current state

- Issue: #119 – Task 32, generic restricted execution and SHEAR-defined constraints.
- Branch: `task/32-restricted-execution`.
- Role: Plan complete – request independent Plan Review.
- Baseline `main`: `d50297cd44db26135bc0b3f9f95e4326c832beb9`.
- Frozen Plan content head: `819848a849c4a15da29232c911fa36c24b57bd40`.
- Substantive Execute work remains mandatory.
- No production implementation, golden-record changes or PR.
- The proposed `shear.hosted_bootstrap.restricted` module does not exist.

## Frozen Plan-owned files

- `docs/restricted_execution.md`
- `docs/roadmap.md` – Task 32 entry only
- `tests/test_restricted_execution.py`
- `tests/test_restricted_execution_boundaries.py`
- `tests/lanes.py` – test registration

The acceptance files deliberately fail before implementation.
Execute must not weaken or rewrite their frozen expectations
without an explicit reviewed Plan revision.

## Plan contract

Build generic restricted execution of ordinary SHEAR functions
through authenticated hosted artifacts. Use it to deploy named
`External` constraint evaluators independently of semantic
constraint identity.

Preserve initial admission, writes, activation and trial semantics;
three-valued results, atomicity and host-error provenance;
version and compiler-generation identity; fail-closed effect
restrictions; and independent evidence of actual machine execution.

Demonstrate non-constraint reuse and record a full mechanism audit.
Retain Task 24's oracle, negative evidence and existing evaluator.
Do not claim mechanism savings without verified removal.

Any required language-shaping decision returns to the owner.
A blocked or negative result needs reproducible evidence and an
actionable successor, not a substituted success criterion.

## Verification

GitHub Actions run `39064305280` completed with failure at the
frozen Plan content head.

Seven test lanes passed. The cross-boundary lane had two import
errors because the planned restricted-execution module is absent.
The new test assertions have not executed. Task 24's experimental
probe step and the golden comparison step were skipped because
the preceding CI step failed.

This is expected pre-Execute red acceptance, not a green CI claim.
Independent Review must examine test validity and feasibility
rather than assuming collection proves the frozen assertions.

The complete diff against the baseline contains only the five
Plan-owned files listed above.

## Independent Plan Review

Read-only. Review the complete branch against the baseline and
the frozen Plan content head.

Challenge bootstrap circularity, generic rather than special-case
execution, effect-preflight completeness, transitive and indirect
calls, canonical role-map access, artifact identity and lifetimes,
replacement during admission, actual-machine oracles, host failure
provenance, atomicity, negative/inconclusive outcomes and the
mechanism ledger.

Verify that each acceptance test expresses feasible intended
behavior, without false expectations about current runtime APIs.
Check Task 24 and issues #107/#110 for preservation and scope.

Classify findings P0–P3 and give a clear Plan verdict.
Do not modify files, Execute, or open a PR.

If Review finds blocking defects, Resolve and obtain fresh Review
before Execute. After Plan approval, Execute implements the frozen
contract and supplies independent runtime evidence.
