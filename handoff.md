# Handoff

Read `CLAUDE.md`, the Workflow section of `docs/roadmap.md`, roadmap task 31
and D5, issue #67 and `docs/live_evolution.md`. Verify this checkpoint
against GitHub and the repository before relying on it.

## Current state

- Issue: #67 (`task`), roadmap task 31, live evolution on the bootstrap
  route. Follow-up opened by Plan: #115 (VM instructions).
- Branch: `task/31-live-evolution`, from `main` at `4ed6e14`.
- Role: Plan done. Next: Execute.
- Plan head: recorded under "Plan head" below. Review diffs the Plan-owned
  files from it.

## Decisions (owner, 2026-10-12)

- **D5.1:** a candidate built by a running program is compiled by the
  image's retained compiler at `activate`/`trial`, after staging and before
  the switch; unchanged nodes reuse artifacts. Lazy or tiered production is
  Open (live_evolution.md 3.1), not built.
- **D5.2:** a candidate that cannot be compiled or admitted changes nothing;
  the run ends with `AdmissionRejected`, which `catch` cannot see.
- One instruction table shared as metadata (`shear/instructions.py`); no new
  VM instructions (#115).
- Cells: content carry-over only. Program-driven cell migration is not
  planned; no program needs it yet.

## Plan-owned files

- `docs/live_evolution.md` (new): the contract.
- `docs/roadmap.md`: D5 and the task-31 status line.
- `tests/test_live_evolution.py` (new, lane `cross-boundary`): 20 tests.
- `tests/test_hosted_bootstrap.py`: two task-30 tests renamed to what they
  now check (live_evolution.md section 8); each says so in a comment.
- `tests/lanes.py`: one line.
- `tests/golden_changes/GH-67.txt`: `programs/compiler`,
  `programs/bootstrap`, `programs/instrument`.

## State of the tests on the Plan head (Python 3.13)

- `tests.test_live_evolution`: every test fails or errors against the
  task-30 route (missing artifacts for the five kinds, missing
  `retained_states`/`admitted`, missing `shear.instructions`). The
  hand-written expectations of `MAIN`, `MIGRATE`, `TWICE`, `CLOSURES` and
  `MOVE` hold on ordinary host execution (checked separately).
- `tests.test_hosted_bootstrap`: one failure, `test_every_node_kind_is_lowered`;
  the renamed fail-closed test passes.
- `python3 -m tests.golden --against main`: 55 unchanged; the three
  declarations fail until the compiler changes, as intended.
- `tests.test_docs`: passes.

## Execute contract

Implement live_evolution.md. Suggested order:

1. `shear/instructions.py` and validation reading it; the VM generator reads
   operand positions from it only where it already encodes them.
2. Node-mode lowering of `quote`, `unquote`, `function`, `activate`, `trial`
   in `compiler_source.py`, descriptors and validation; expanded mode
   unchanged. Regenerate the seed manifest (`seed_cli --write`).
3. Per-version artifact sets, candidate compilation at `activate`/`trial`
   (a separate compiler run, section 3.3), the reuse rule (4.3), trial sets
   (4.2), release at retirement (4.1), `retained_states`, `admitted`, the
   `reuse`/`release` events and `TraceEvent.source_artifact_id`.
4. Measurements (section 7) in `diagnostics.py` and `hosted_bootstrap.md`.
5. Docs: `hosted_bootstrap.md` (implementation), `bootstrap.md` (matrix note:
   node mode covers every kind), `activation_model.md` sections 10 and 12
   (derived artifacts per version, reuse rule), and the `CHANGES.md` entry.

Execute may choose, and marks Provisional: the hook mechanism between the
machine or runtime and the session (no new public name in the golden API
modules: `shear`, `shear.lang`, `shear.syntax`, `shear.bytecode`,
`shear.machine`); the instruction table's other fields; the diagnostics
layout.

Execute must not: change Plan-owned files or expectations; let a candidate
become active or run in a trial before every code node is admitted; make
`AdmissionRejected` catchable; reuse on host-API activations or from trial
sets; add VM instructions; change expanded-mode output. If any of these
proves necessary, return to Plan.

Also required: mutation-catalog re-review for `compiler_source.py`, the
changed `hosted_bootstrap` modules and `shear/instructions.py` (target or
justified omission), run in CI by workflow dispatch, not locally; the golden
declarations must match exactly (a mismatch goes back to Plan); all lanes
pass (`python3 -m tests.lanes --all`).

`CHANGES.md` entry (Execute appends, adjusting facts it changed):

    ## Task 31: live evolution on the hosted route (GH-67)

    A running image changes itself on route B. The SHEAR compiler lowers
    every node kind; candidates built by `activate` and `trial` are compiled
    by the image's retained compiler and admitted whole before they run or
    become active (D5); unchanged nodes reuse their artifacts; a version owns
    its artifacts and releases them when it retires. All 29 corpus examples
    and the live-image scenarios run on admitted artifacts and agree with
    ordinary host execution. One instruction table is shared as metadata by
    admission, the machine's tests and the SHEAR-written VM. Update latency
    and retention are measured in hosted_bootstrap.md.

## Claims Review must verify independently

live_evolution.md section 9, claims 1 to 7.

## Plan head

`82a6a69696cb669614039f87976a66098a0a517a` ("GH-67 Add the task 31 live-evolution contract and acceptance
tests"). Execute starts from the commit that records this file.
