# Handoff

Read `CLAUDE.md`, the Workflow section of `docs/roadmap.md`, roadmap task 31
and D5, issue #67 and `docs/live_evolution.md`. Verify this checkpoint
against GitHub and the repository before relying on it.

## Current state

- Issue: #67 (`task`), roadmap task 31, live evolution on the bootstrap
  route. Follow-up opened by Plan: #115 (VM instructions).
- Branch: `task/31-live-evolution`, from `main` at `4ed6e14`.
- Role: Plan done, revised after two Plan reviews (below). Next: Execute.
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
- `tests/live_support.py` (new): the image program, step tables, oracles.
- `tests/test_live_evolution.py`, `tests/test_live_artifacts.py` (new, lane
  `cross-boundary`) and `tests/test_instruction_table.py` (new, lane
  `language-runtime`): 26 tests.
- `tests/test_hosted_bootstrap.py`: four task-30 tests that used `quote` as
  the unsupported kind (live_evolution.md section 8); each says so in a
  comment.
- `tests/lanes.py`: three lines.
- `tests/golden_changes/GH-67.txt`: `programs/compiler`,
  `programs/bootstrap`, `programs/instrument`.

## Plan revision after two Plan reviews

The owner relayed two reviews of the first Plan head (`82a6a69`). Each
finding was checked against the repository.

Accepted and fixed:

- R1 P1: two more task-30 tests,
  `test_a_program_error_and_a_refusal_both_exit_with_one` and
  `test_a_seed_needs_the_compiler_functions_and_only_lowerable_ops`,
  depended on `quote` being unsupported. Both now patch `SUPPORTED_KINDS`.
  Node mode gets its own kind set, separate from expanded `LOWERED`
  (section 2.3).
- R1 P2: problem-carrying `activate`/`trial` forms (`MALFORMED`) are
  compared with host lowering and run against the host.
- R1 P2: a trial of the active state itself has the same `StateID`. Sets
  belong to versions or trials, not to a `StateID`, and `release` says which
  (sections 4.1, 4.2 and 6; `same_trial`, `SameStateTrial`).
- R1 P2: reuse sources must be the active version's artifacts, and the tests
  assert it. The admitted-whole test now uses distinct trial and activation
  states.
- R1 P3:
  - docstrings name the two tests that pass before implementation;
  - the `extract_function` citation points to `shear/continuity.py`;
  - reuse rule 2 is called conservative;
  - section 3.2 no longer promises "no compilation" for runtime-checked
    rejections;
  - continuity is said to be inferred;
  - validation must read the table, and a test deletes an entry to prove it;
  - measurements get an Execute-owned smoke test;
  - the lane-time concern is recorded.
- R2 P1, and R2 P2 on trial cleanup, now tested:
  - a failure partway through a candidate (`SUPPORTED_KINDS` without `add`);
  - trial release after a rejected answer and after a crash inside the trial;
  - a heap count of target artifacts and a holds check after each.
- R2 P2 (provenance): every chunk the machine opens is recorded at the
  machine's own chunk boundaries, then compared with host lowering and with
  the admitted object. The trace check stays as a separate assertion.
- R2 P2 (table): the minimum metadata is defined (section 5.2), and
  `operands`, `children` and `linked` are checked against host chunks.
- R2 P3: the module was split into three test modules plus a support
  module.

Rebutted:

- R1 P3, "`SUPPORTED_KINDS` is a superset of `NODE_KINDS`": `invalid` is in
  `NODE_KINDS`, so the sets are equal once the five kinds are added. Section
  2.3 now says so.

## State of the tests on the Plan head (Python 3.13)

- The three new modules: 26 tests. All fail or error against the task-30
  route except two, which check the declared sets and the host oracle:
  `test_every_corpus_example_is_claimed` and
  `test_the_oracle_catches_what_the_route_must_not`.
- Every hand-written expectation holds on ordinary host execution.
- The table tests pass against a stand-in table built from `validation.py`'s
  own facts, and they catch three planted table bugs.
- `tests.test_hosted_bootstrap`: one failure,
  `test_every_node_kind_is_lowered`. The three other changed tests pass.
- `python3 -m tests.lanes --all`: only `language-runtime` (the table tests)
  and `cross-boundary` fail, as intended.
- `python3 -m tests.golden --against main`: 55 unchanged. The three
  declarations fail until the compiler changes, as intended.
- `tests.test_docs`: passes.

## Execute contract

Implement live_evolution.md. Suggested order:

1. `shear/instructions.py` and validation reading it when it validates; the
   VM generator reads operand positions from it only where it already
   encodes them.
2. Node-mode lowering of `quote`, `unquote`, `function`, `activate`, `trial`
   in `compiler_source.py` (with a node-mode kind set), descriptors and
   validation; expanded mode unchanged. Regenerate the seed manifest
   (`seed_cli --write`).
3. Candidate handling:
   - artifact sets owned by versions and trials;
   - candidate compilation at `activate`/`trial`, as a separate compiler run
     (section 3.3);
   - the reuse rule (4.3);
   - trial sets (4.2) and release at retirement (4.1);
   - cleanup after a failed attempt (3.2);
   - `retained_states`, `admitted`, the `reuse`/`release` events and
     `TraceEvent.source_artifact_id`.
4. Measurements (section 7) in `diagnostics.py` and `hosted_bootstrap.md`,
   with a smoke test.
5. Docs: `hosted_bootstrap.md` (implementation), `bootstrap.md` (matrix note:
   node mode covers every kind), `activation_model.md` sections 10 and 12
   (derived artifacts per version, reuse rule), and the `CHANGES.md` entry.

Execute may choose the following, and marks each Provisional:

- the hook mechanism between the machine or runtime and the session. No new
  public name may appear in the golden API modules: `shear`, `shear.lang`,
  `shear.syntax`, `shear.bytecode` and `shear.machine`;
- the names of the table's fields beyond `operands`, `children` and
  `linked`;
- the diagnostics layout.

The tests observe chunks by wrapping `machine._chunk_for` and
`machine._child_chunk`, as task 30's tests wrap `machine._open`. Keep those
two as the machine's chunk boundaries.

Execute must not:

- change Plan-owned files or expectations;
- let a candidate become active, or run in a trial, before every code node
  is admitted;
- make `AdmissionRejected` catchable;
- reuse on host-API activations or from trial sets;
- add VM instructions;
- change expanded-mode output.

If any of these proves necessary, return to Plan.

Also required:

- mutation-catalog re-review for `compiler_source.py`, the changed
  `hosted_bootstrap` modules and `shear/instructions.py` (a target or a
  justified omission), run in CI by workflow dispatch, not locally;
- golden declarations that match exactly; a mismatch goes back to Plan;
- all lanes passing (`python3 -m tests.lanes --all`), with the time of
  `cross-boundary` recorded.

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

`f11706d4e7fea1e9d7eb4cdc96c29b0cf8fb65bc`
("GH-67 Change the task 31 contract and tests after two Plan reviews").
The first Plan head was `82a6a69`. Execute starts from the commit that
records this file.
