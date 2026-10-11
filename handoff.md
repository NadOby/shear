# Handoff

Read `CLAUDE.md`, the Workflow and D3/D4 sections of
`docs/roadmap.md`, `docs/hosted_pipeline.md` and `docs/hosted_bootstrap.md`.
Verify this checkpoint against GitHub before relying on it.

## Current state

- Task: 30 – Hosted-bootstrap pipeline. Issue: #66.
- Branch: `task/30-hosted-bootstrap`.
- Protected Plan head: `fbbb32379c327c1e29f5646e89d30fd1bb8a8084`.
- Role: Resolve of the first independent Review (2 P2 findings) done; ready for confirmation.
- Execute commits: `504daa8` (compiler move and unification), `f678c00`
  (machine resolver), `1592f09` (pipeline and tests), `1b77784` (spike
  removal, mutation catalog, workflow, `CHANGES.md`).
- No PR opened by Execute.

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

- `python3 -m tests.lanes --all`: all 8 lanes ok locally (Python 3.13).
  CI uses 3.12 and has not run yet.
- Protected Plan tests pass unmodified. Golden changes are exactly the three
  declared (`programs/compiler`, `programs/bootstrap`, `programs/instrument`).
- `tests/test_hosted_bootstrap.py` (Execute-owned) compares the SHEAR
  compiler's chunk with `bytecode.lower` for every supported node of every
  corpus program, and covers bad admission evidence, seed manifest, the
  resolver hook and trace deduplication.
- Diagnostics smoke-run once (`--repeats 1`) on 2 vCPUs; no reportable
  measurements yet. Run the `hosted_diagnostics` dispatch for medians.

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
  in `tests/mutation_catalog.py`).
- `self_hosting.py`, `vm.py`, `machine.py` survivors: every classified site
  and its context were checked unchanged by inspection and repinned. They
  were **not** re-run locally; the CI campaign must confirm them.
- Locally, 68 mutants of the new resolver hook and hosted modules were
  killed; the rest are left to CI by owner's decision. Every
  `compiler_source.py` mutant is killed at once by the manifest check, so
  behavioural coverage of the compiler rests on the differential test.

## Known limitations

- Cross-activation reuse and live evolution: Task 31.
- Peak-memory and timing figures are from a 2-vCPU container only.

## Review findings resolved

- P2 admission did not check stack effects or termination: `validation.py`
  now simulates the operand stack in one pass and checks operand types;
  negative tests in `AdmissionChecksTheStack` fail on the old code.
- P2 no witnesses for `applyv` and `linksof`: `OperationWitnesses` runs both
  on admitted artifacts, host lowering forbidden, against ordinary execution.
- P3 conditional seed test: an unconditional Execute-owned test was added;
  the protected test is unchanged.
- Still open: run the `hosted_diagnostics` dispatch and retain its report
  before Publish; the mutation campaign result is pending on CI.

## Nonblocking P3 observations for Review

No further Plan revision is required for any of them.

1. **vm.py survivor pins.** `vm.py` has six blob-pinned survivors and Execute
   modified it. Execute checked by inspection that all six sites and their
   contexts are unchanged and repinned; they were not re-run locally. Review
   must re-review the classifications, as for `self_hosting.py` (two) and
   `machine.py` (eleven).
2. **Conditional seed negative test.** `test_hosted_pipeline.py` guards its
   unrelated-compiler-node check with `if unrelated_code:`. An approximate
   count by Execute found 4 such nodes in the compiler state, so the branch
   should run; Review must verify actual negative coverage and record any
   remaining limitation. Protected test not changed.
3. **Generation ancestry coverage.** The `machine._open` instrumentation
   verifies admitted compiler function-body chunks consumed during G2/G3
   production. It does not establish child-node or closure-chunk ancestry.
   Review must distinguish this from complete per-node provenance.
4. **Trace completeness; issue text.** Trace assertions show each reported
   execution has production and admission records, not that every executed
   node emits an event (events are first use per artifact). Review should
   audit execution coverage. Issue #66 still describes the pre-D4 workload;
   Publish adds a clarification referencing D4 and
   `docs/hosted_pipeline.md`.

## Follow-up (not created)

Source files over the ~500-line threshold: `lang.py`, `machine.py`, `vm.py`,
`transforms.py`, `continuity.py`. They are pinned mutation targets, so a
split needs its own `follow-up` issue (a maintainability assessment with
targeted candidates, not a mandatory split) and survivor re-review. Not part
of Task 30.

## Next action

Independent Review of Task 30 in a fresh context against the protected Plan
head, then Resolve/Publish per the roadmap.
