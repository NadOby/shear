# Handoff

Read `CLAUDE.md`, the Workflow and D3/D4 sections of
`docs/roadmap.md`, `docs/hosted_pipeline.md` and `docs/hosted_bootstrap.md`.
Verify this checkpoint against GitHub before relying on it.

## Current state

- Task: 30 – Hosted-bootstrap pipeline. Issue: #66. PR: #98.
- Branch: `task/30-hosted-bootstrap`; protected Plan head `fbbb32379c327c1e29f5646e89d30fd1bb8a8084`.
- Role: Publish (PR opened); two independent Reviews accepted
  `248a5e1` (full 16-shard mutation campaign green). Waiting for the owner to merge.

`docs/hosted_pipeline.md` is authoritative. This handoff is a checkpoint,
not evidence.

## What was built

- `shear/examples/compiler_source.py`: the one SHEAR compiler (`lower_op`
  core, `lower` expanded, `compile_node` node-aware, with `catch`/`raise`).
- `shear/hosted_bootstrap/`: seed and manifest, generations 1–3, descriptors,
  structural validation, artifacts and resolver, target, session, command,
  trace, diagnostics. Module map: `docs/hosted_bootstrap.md`.
- `machine.run(..., resolver=)`: optional per-run chunk source. Unchanged
  behaviour without it.
- Removed: `shear/execution_route_spike.py`, `tests/test_execution_route.py`,
  its workflow job. Added a `hosted_diagnostics` dispatch input and job.

## Verification performed

- `python3 -m tests.lanes --all`: all 8 lanes ok locally (Python 3.13);
  CI on 3.12 passed for `1b77784` and `7c99964`.
- Protected Plan tests pass unmodified. Golden changes are exactly the three
  declared (`programs/compiler`, `programs/bootstrap`, `programs/instrument`).
- `tests/test_hosted_bootstrap.py` (Execute-owned) compares the SHEAR
  compiler's chunk with `bytecode.lower` for every supported node of every
  corpus program, and covers bad admission evidence, seed manifest, the
  resolver hook and trace deduplication.
- Diagnostics: 5-repeat local run recorded in `docs/hosted_bootstrap.md`;
  CI dispatch at `7c99964` and push run at `1b77784` succeeded.

## Edits to Plan-owned or existing files (call-outs)

- `tests/lanes.py` (Plan-owned): registered `test_hosted_bootstrap`; removed
  `test_execution_route`.
- Existing tests edited to follow the compiler: `test_self_hosting.py`,
  `test_bootstrap_boundary.py` (catch/raise now lowered),
  `test_vm.py` (one size check now compiles `lower_op`, since `lower` is
  small), `content_baseline_evidence.py` (compiler file path),
  `docs/bootstrap.md`.
- `shear/examples/vm.py`: swaps `named_tail`, `child`, `lower_op`; derives
  retained-source links from the compiler instead of a hand-written table.
- No other Plan-owned file changed.

## Provisional choices (Review to examine)

- Descriptor `(operands, (state_id, node, version, owner))`; `LIT` operand
  kept canonical, other identities decoded.
- Nodes of kinds the compiler does not lower (`activate`, `function`,
  `quote`, `trial`, `unquote`) are recorded as `reject` and fail closed at run.
- Any state change makes all artifacts stale; `prepare` again.
- Execute events record first use per artifact.
- Admission checks origin and structure only, not compiler correctness.

## Mutation decisions

- New targets: `compiler_source.py` and every `hosted_bootstrap` module
  except `__init__`, `__main__`, `errors`, `diagnostics` (omissions justified
  in `tests/mutation_catalog.py`). Repins of `self_hosting.py`, `vm.py` and
  `machine.py` are confirmed by the green campaign.
- Mutants of `compiler_source.py` all die at the manifest check; behavioural
  coverage rests on the differential test.
- The oracle owns its 900 s limit and a 3 GiB address-space cap; the engine
  `tests/mutation.py` is unchanged. A mutant that times out counts as killed (#95).

## Known limitations

- Cross-activation reuse and live evolution: Task 31 (#67).
- Generation ancestry is witnessed for function bodies only; events record
  first use of an artifact; recorded timings predate the last fixes.

## Follow-ups (not part of Task 30)

- #94: maintainability of oversized production modules.
- #95: coverage diagnostic and faster mutation campaign.
- #96: split `tests/test_hosted_bootstrap.py`.
- #97: record the per-example operation inventory.

## Next action

The owner merges #98. Then Plan task 31 (#67) in a fresh chat.
