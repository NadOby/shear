# Handoff

Read `CLAUDE.md`, the Workflow section of `docs/roadmap.md`, issue #95 and
`docs/verification_hardening.md` sections 10 and 15. Verify this checkpoint
against GitHub and the repository before relying on it.

## Current state

- Task: #95 – mutation testing reliability and performance. Execute, without
  a separate Plan (the owner allowed it).
- Branch: `workflow/mutation-reliability`, on `main` at `0994e70`.
- Role: Execute done; waiting for an independent Review. This session does
  not certify its own work.

## What was built

- `tests/mutation_verdict.py` (new): the status-file protocol and `classify`.
  Outcomes `killed`, `timeout`, `resource_kill`, `abnormal_exit`, `survived`;
  only a failing test is a kill.
- `tests/mutation_oracle.py`: `--status`, `--limit` (watchdog, also while
  test modules import), `--first` (module order); a module that fails to
  import with any exception is a failed test; no-argument `main()`/`suite()`
  still work.
- `tests/mutation_reporting.py`, `tests/mutation_campaign.py`: run the oracle
  with the protocol, limit `max(180, 3 x baseline)`, untimed baseline, report
  new outcomes and counts, skip reviewed survivors (`rerun_classified`),
  replay prints the outcome. The legacy 3-argument `_execute_one` path is kept
  for the existing tests.
- `tests/mutation_coverage.py` (new): coverage map (`sys.monitoring`, one
  traced process per oracle module, opaque-module detection, tree
  fingerprint), ordering, and a non-gating report.
- `tests/mutation_performance.py` (new): campaign summary from reports.
- `.github/workflows/semantic-model.yml`: plan job builds the map (failure
  only costs speed), shards download it, per-shard and campaign summaries,
  inputs `mutation_revalidate`, `coverage_diagnostics`, `coverage_targets`.
- Tests: `test_mutation_verdict`, `test_mutation_outcomes` (real subprocesses
  over a fixture oracle), `test_mutation_coverage`,
  `test_mutation_performance`; all in the `mutation` lane.
- Docs: `docs/verification_hardening.md` section 10 (outcomes, ordering,
  revalidation, accepted and rejected optimizations, numbers) and 15;
  `CHANGES.md`.

## Pins and revalidation

- The engine `tests/mutation.py` and every target source are unchanged, so
  the engine blob pin (`cf45fbb`) and all 156 classifications stay valid; no
  repin, no revalidation was needed. Any later engine edit needs
  `SHEAR_MUTATE_REVALIDATE=1` for one campaign.

## Evidence

- Local 76-mutant sample (`SHEAR_MUTATE=2`, seed 1), before on `main` vs
  after: wall 2156 s to 655 s, CPU 4103 s to 1024 s (+149 s once for the
  map), mean kill 31.7 s to 6.7 s (4.7 times; the 5 times aim was narrowly
  missed). Outcomes identical for 75 of 76; the hanging `reconcile.py` mutant
  was "killed" after 900 s and is now `timeout` after 440 s.
- Regression tests were checked against planted bugs (timeout counted as a
  kill, status file ignored, baseline timed, pinned survivors re-run, `--first`
  ignored, uncertain modules dropped, opaque detection off, stale map
  accepted, watchdog off, import errors uncaught): each is caught.
- Python 3.14 (#53): about 15 % faster locally and passes the oracle; not
  adopted (needs an exhaustive campaign for the survivor catalog).
- De-duplicating mutants by compiled code: 223 of 4056 sites (5.5 %).
- CI (150 per target, seed 1, 16 shards, run 38188546294 vs baseline run
  38184400290 on `main`): slowest shard 65.2 to 17.6 min, total 724 to 191
  shard-minutes. That run failed in shards 6 and 9 on two `abnormal_exit`
  mutants (`matching.py`, MemoryError escaping the runner): fixed, with a
  regression test. 12 timeouts were ~79 % of campaign time, hence the
  per-test budget below. A re-run on the final commit is the CI evidence to
  attach.

## Edits to existing tests (call-outs)

- `tests/test_mutation_campaign.py`: `test_exact_replay_runs_resolved_mutant`
  became `..._and_reports_its_outcome` (replay returns an outcome, not a bool).
- `tests/test_mutation.py`: uses the timed baseline, the mutant limit, the
  optional map and revalidation, and asserts there are no abnormal exits.
- `tests/lanes.py`: registers the four new test modules.

## Provisional choices for Review

- Per-test budget `max(30 s, 10 x baseline)`: a test over it is reported as a
  non-failing `timeout`. A mutant that slows one test tenfold but would
  still pass is no longer an unclassified survivor. Replay has no such budget.
  Say if an unexplained timeout should fail a campaign instead.
- Cost-aware sharding (#51) dropped: imbalance is unchanged and comes from
  hangs. Suggest closing #51 as not planned.
- Workflow input `python_version` (default 3.12) exists so an exhaustive
  campaign can be run on 3.14 (#53); CI is not moved.
- An `abnormal_exit` fails a campaign; a `timeout` and a `resource_kill` are
  reported but do not (owner decision wanted if this is too lax).
- Reviewed survivors are not re-run by default.
- Coverage map: "uncertain" modules (those that start processes or fail) run
  right after the covering ones; nothing is ever skipped.

## Known limitations

- A hang is still bounded only by 3 x baseline (about 8 minutes on CI).
- The map needs Python 3.12+ and costs one traced run of every oracle module.
- Engine-level ideas (fork per mutant, de-duplication) are not done.

## Follow-ups

- #51 (shard balance), #53 (Python 3.14), #49 (carried-key check): see the PR
  for what the CI evidence says; none is closed by assertion here.

## Next action

Independent Review of the PR for #95.
