# Handoff

Read `CLAUDE.md`, the Workflow section of `docs/roadmap.md`, roadmap task 31
and D5, issue #67 and `docs/live_evolution.md`. Verify this checkpoint
against GitHub and the repository before relying on it.

## Current state

## Current state

- Issue: #67 (`task`), roadmap task 31, live evolution on the hosted
  bootstrap route. Branch: `task/31-live-evolution`, originally from
  `main` at `4ed6e14`.
- Role: Resolve following independent implementation Review. The review
  of `23d390a` accepted the implementation with one nonblocking P3
  changelog correction, subsequently resolved.
- Plan-owned acceptance tests, specifications and golden declarations
  were unchanged in that review. Plan head is recorded below.
- Full mutation campaign: workflow-dispatch run `38414508331`, commit
  `f68e3a9`, 16 shards, 4,212 mutations: 4,042 killed, 152 classified
  survivors, 18 timeouts, zero unclassified survivors. Reviewed
  survivors were revalidated.
- Of the 12 previously unclassified survivors, ten were killed by new
  regressions and two `_reuse()` returns were classified equivalent.
  The remaining timeouts are not counted as kills.
- Commit `23d390a` added a G0 caching and generation-identity regression
  targeting two compiler-generation timeouts. Their targeted mutation
  replay has not yet been verified; this test postdates the campaign.
- Ordinary CI passed on `23d390a` (run `38425454911`) and on the
  changelog correction `5a3b6f7` (run `38455730847`).
- Review's P3 documentation drift was corrected: `CHANGES.md` now
  distinguishes immediate retirement cleanup during a run from cleanup
  at the next run or query after host-held retirement outside a run,
  as allowed provisionally by `docs/live_evolution.md` section 4.1.
  Duplicate changelog text was removed in `7cea8a4`.
- Before Publish: verify CI for `7cea8a4` (run `38456474960`),
  verify the two compiler-generation timeout mutations on the final
  test revision, and independently confirm the final reviewed diff.
- Follow-ups: #115 (VM instructions), #116 (reuse cost). No unresolved
  P0–P2 implementation defects were found by the accepted static review.

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
  `language-runtime`): 30 tests.
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

## Second revision, after a third and a fourth Plan review

The owner relayed two reviews of `f11706d`. One accepted it with two P3
notes; the other requested changes. Each finding was checked.

Accepted and fixed:

- P2, error precedence: a compilation failure could have masked
  `activation_rejected`. Language rejections now take precedence. A
  candidate is compiled only after the runtime's own checks accept it
  (section 3.2). `bound_first` plus
  `test_a_language_rejection_wins_over_a_compilation_failure` witness it.
- P2, two loaded versions with one `StateID`: confirmed on the host
  (`same_activate`). The API is now per version: `retained_versions()` and
  `admitted(version)` (sections 4.1 and 6). A test checks that both loaded
  versions own separate records.
- P2, direct `bytecode.lower`: `no_host_lowering` now forbids it too.
- P2, same-state trial ownership: `observed_chunks` records the version of
  the frame that opened each chunk. It wraps `_open`, `_open_closure` and
  `_child_chunk`, since `_chunk_for` sees only a state. Every opened chunk
  must be the admitted object of its own version's set, a trial's included.
  The same-state trial test checks that the trial's records are separate
  from the active set's, and that the chunks are shared.
- P3, partial failure: the injected failure now refuses the produced chunk
  at admission (`LEN` removed from the table). `grow` makes `len` the only
  new node kind, so the test requires a `produce` event before the failure.
- Test-side references to versions and artifacts are dropped before every
  heap count, so the orphan check cannot be inflated by the tests.

On the P3 notes of the accepting review:

- The stand-in table check was local, and the script is not on the branch.
  Treat it as a sanity check of the tests, not as evidence about any
  implementation.
- The shared-record hypothesis is now settled by the tests: separate
  admission records with a shared chunk are required (sections 4.2 and 4.3).

## Combined review of `51c9612`

The review approved the plan after one fix, and both points below were
checked.

- P2, verified test defect, fixed: in
  `test_a_trial_of_the_active_state_has_its_own_set`, the loop variable
  `artifact` kept a released trial record alive, so `assert_no_orphans`
  would fail on a correct implementation. The cleanup now also deletes
  `artifact` and `chunk`. The same was done for `artifact` in
  `test_two_loaded_versions_of_one_state_have_separate_sets`. That one held
  an active record, so it was harmless there, but the cleanup is now
  uniform.
- P3, Execute and Review checkpoint (no Plan change): candidate
  compilation and admission must finish before `Runtime.activate` mutates
  any live runtime state, not merely before `_active` changes. That means
  before `kept._move(new)`, before `self._versions`, `self._active` and
  `self._history` are assigned, and before `_retire_if_unused`. The same
  holds in `Runtime.trial` before the isolated runtime is returned for
  execution.
- The earlier request to require a successful admission before an injected
  failure was withdrawn. The `produce` requirement in
  `test_a_failure_partway_through_a_candidate_leaves_nothing` stays: the
  injection refuses an already produced chunk, so a `produce` event comes
  first in every compilation order.

## Fix after Execute's report (owner-relayed)

- Verified defect in a Plan-owned test, fixed:
  `Lifetime.test_repeated_updates_release_retired_versions` called
  `upgrade(1, 2, 2 + m)`, but `handle(2)` is 3 on the initial image, so the
  m-th update answers `3 + m`. The host oracle reproduced the failure
  (`'wrong' != 'installed'`). The test now uses `3 + m` and checks every
  step against a host runtime, as `drive` does. Its expectations were the
  only ones in the module not checked against the host.
- Every other hard-coded expectation in `tests/test_live_artifacts.py` was
  rechecked on the host and holds: `migrate`, `try_wrong`, `try_crash`,
  `same_trial`, `same_activate`, `upgrade(10, 2, 13)` and `bound_first`.
- Execute rebases onto the new Plan head; no other Plan-owned file changed.

## State of the tests on the Plan head (Python 3.13)

- The three new modules: 30 tests. All fail or error against the task-30
  route except two, which check the declared sets and the host oracle:
  `test_every_corpus_example_is_claimed` and
  `test_the_oracle_catches_what_the_route_must_not`.
- Every hand-written expectation holds on ordinary host execution.
- The table tests passed a local check against a stand-in table built from
  `validation.py`'s own facts, and caught three planted table bugs. The
  stand-in is not on the branch, so this is not evidence.
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
   - cleanup after a failed attempt, and language rejections before any
     compilation (3.2); compilation and admission finish before
     `Runtime.activate` mutates any live state (`kept._move(new)` included)
     and before `Runtime.trial` returns the isolated runtime;
   - sets owned by `Version` objects, `retained_versions`,
     `admitted(version)`, the `reuse`/`release` events and
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

The tests observe chunks by wrapping `machine._open`,
`machine._open_closure` and `machine._child_chunk`, as task 30's tests wrap
`machine._open`. Keep those three as the machine's chunk boundaries.

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

## Execute notes

- Rebased onto Plan head `3d58684` (the lifetime test fix). All lanes pass
  (`python3 -m tests.lanes --all`); `cross-boundary` took 151 s (two lanes at a time).
- Mutation: `shear/instructions.py` is now a target, `live_diagnostics.py`
  an omission; survivors of `machine.py`, `runtime.py` and `examples/vm.py`
  were re-reviewed (unchanged sites) and repinned. The campaign for the
  changed targets still has to run in CI by workflow dispatch.
- Resolve (first review, `45c4446`): finding 1 fixed (the target releases the
  sets of versions that retired outside a run whenever it is asked about
  sets or starts a run; `LateRetirementTests`, failing on the old code);
  finding 2: the measurements in hosted_bootstrap.md 4.1 are rerun at a clean
  tree, revision `7f39921`; finding 3: trial-rejected updates added next to
  the injected, renamed "refused" ones. Finding 4 (reuse rule 4 has no
  witness, so removing it passes every test) stays a hypothesis; finding 5
  is follow-up issue #116 (reuse cost).
- Resolve (second review, `2b65be2`): the P3 is fixed. `prepare()` drops each
  production record after its admission, as candidate compilation does;
  `ConsumedEvidenceTests` fails on the old code. Still open: the mutation
  campaign in CI and a fresh Review against `d76708f`.
- Provisional choices are listed in hosted_bootstrap.md section 6.

## Second implementation review (`e037104`), and Plan's amendment

Two reviews of `e037104` agreed that findings 1 to 3 are resolved, CI is
green on `e037104`, and #116 covers the reuse cost. They differed on two
points.

- Deferred reclamation of a version that retires outside a run. The owner
  accepted it on 2026-10-12. Plan recorded it as a Provisional exception in
  live_evolution.md section 4.1, so it is no longer a deviation. Eager
  release waits until a real host-held workload needs it.
- P3, verified (pre-existing, now longer-lived): `HostedTarget.prepare()`
  keeps its `_Production` records, with their chunks, in `_productions`
  after admission. The candidate path deletes them, but prepare does not.
  On the image, 228 records stay alive after the prepared version has
  retired, for the target's whole life. The fix for Resolve is small: drop
  each prepare-time production once it is admitted, as the candidate path
  does, leaving the public `produce`/`admit` pair as it is. A regression
  test should count the records after the prepared version retires. Not
  blocking.

Still open before Publish: the mutation campaign by workflow dispatch, and a
fresh Review.

## Claims Review must verify independently

live_evolution.md section 9, claims 1 to 7.

## Plan head

`d76708ffbbd970ceed380d231ace0859a4d4fac1`
("GH-67 Change live_evolution.md to record the accepted deferred reclamation";
section 4.1 only). Earlier Plan heads: `82a6a69`, `f11706d`, `51c9612`,
`fc006f4`, `3d58684`. Review diffs the Plan-owned files from this one.
