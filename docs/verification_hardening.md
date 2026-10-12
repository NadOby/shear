# Verification hardening

**Status: implemented** (roadmap task 18, PR #42).

Task 18 strengthens the evidence that SHEAR's semantics are correct before
task 19 changes the architecture. It remains verification hardening rather
than an architectural refactor. During mutation review it exposed two
production-semantic defects, which were fixed: closure capture values are
canonicalized when captured so later host mutation cannot change the captured
semantic value, and malformed closure capture names are rejected with
`LanguageError`. Apart from those defect fixes, the task changes tests, test
infrastructure, documentation and CI rather than redesigning production
semantics.

This document records the resulting verification architecture and policies.
One-off CI timings, workflow run IDs and campaign measurements are historical
evidence and belong in `CHANGES.md` and the PR record rather than in this
document.

## 1. Goals

Task 18 has four goals:

1. make cross-subsystem semantic failures harder to hide behind individually
   correct components;
2. discover counterexamples and missing invariants rather than merely increase
   the test count;
3. make generated failures reproducible and reducible into permanent
   regressions;
4. keep normal feedback practical while allowing substantially heavier
   verification campaigns when needed.

Task 19 can therefore change architecture against a stronger baseline without
mixing verification work into the refactor itself.

## 2. Verification layers

**Decided:**

SHEAR uses several independent kinds of evidence rather than one universal
test framework:

- focused unit tests for local contracts;
- minimized deterministic regressions for discovered defects;
- corpus and whole-program acceptance tests;
- invariant and generated property tests;
- generated malformed and negative inputs;
- differential tests between independent implementations;
- metamorphic tests for semantics-preserving relationships;
- bounded exhaustive checks over small complete state spaces;
- deterministic stateful operation sequences;
- mutation testing that checks whether the rest of the suite notices planted
  implementation faults.

Coverage and raw test count are diagnostics, not correctness metrics.

## 3. Cross-boundary testing

**Decided:**

Subsystem seams are first-class verification targets.

Important paths include:

    text
      ↕
    input form
      ↕
    semantic graph
      ↕
    bytecode
      ↕
    host machine

and the independent paths:

    semantic graph → embedded compiler → bytecode
    bytecode       → SHEAR VM

as well as:

    edited text → parse → reconcile → continuity → activation
    transform   → mapping → reference transfer → runtime cells
    activation  → code in flight → version holds → closures

Tests deliberately cross several boundaries in one case when that is where the
semantic contract lives.

Examples include:

    text
    → parse
    → graph
    → render
    → reconcile

and:

    input form
    → graph form
    → collapse
    → execute malformed code
    → LanguageError

and:

    graph
    → embedded compiler
    → bytecode
    → SHEAR VM
    ↕
    host execution

and:

    transform
    → trial / activate
    → runtime cell transfer
    → holds and version lifecycle

A subsystem agreeing with itself is weaker evidence than independent semantic
paths agreeing.

## 4. Differential testing

**Decided:**

Differential tests use independently implemented paths already present in the
project.

Where their domains overlap, the suite checks relationships including:

    host lowering == embedded compiler lowering
    host machine behaviour == SHEAR VM behaviour
    graph execution before transform == graph execution after
        semantics-preserving transform
    trial behaviour == activation behaviour where specified

Failures are compared where relevant, not only successful return values.

Task 18 adds deterministic closure-heavy differential generation across host
execution and the embedded compiler/VM path. Cases exercise:

- direct closure calls;
- `applyv`;
- nested closures;
- closures capturing ordinary values;
- closures capturing other closures.

The generator stays within the common host/embedded-VM subset.

Generated cases identify their seed and can be replayed with:

    SHEAR_SEED=<seed> \
        python -m unittest tests.test_closure_differential

Larger generated budgets belong to the manual/heavy verification tier.

## 5. Metamorphic testing

**Decided:**

Metamorphic tests check relationships whose expected result is known without a
separate reference interpreter.

Task 18 checks low-level transformation relationships including:

- independent value changes commute;
- batching independent changes agrees with applying them sequentially;
- repeating the same semantic change is idempotent.

It also checks language-level relationships that exercise substantially more of
SHEAR:

- rendering an authoritative graph-form program and reconciling that rendered
  source back into the same program is a no-op;
- projecting a loaded function through `function_at` and defining that same
  function again is a no-op;
- rebasing two independent function definitions produces the same language
  projection and observable execution as defining both edits together.

The last relation deliberately does not require exact `StateID` equality.
Independent and batched edits may allocate graph nodes through different
histories even when their source projection and observable language semantics
agree. Metamorphic tests must assert the semantic contract, not accidental
allocation history.

Existing tests independently cover other metamorphic relationships such as
canonical mapping order, matching order independence, folding twice,
render/reparse and trial/activation agreement.

Generated metamorphic cases use the common deterministic replay mechanism.

## 6. Negative and malformed generation

**Decided:**

Generated verification includes invalid inputs rather than constructing only
valid programs.

Task 18 generates malformed language cases including:

- unknown operations;
- wrong arity;
- malformed `let` names;
- wrong arithmetic and condition operand kinds;
- malformed tuple operations;
- non-callable values;
- malformed closure parameter/capture containers;
- malformed closure names;
- duplicate closure names;
- overlapping parameter/capture names;
- missing declared captures.

Each malformed case is loaded into graph form and collapsed back to input form.
The malformed body must survive that round trip rather than being normalized
away.

Execution must then fail with `LanguageError`, not a leaked host exception.

These tests do not impose transactional rollback on arbitrary language errors.
Effects that occur before a later error remain governed by the language's
normal effect-ordering semantics. Atomicity is asserted separately only for
operations whose contracts promise it, such as rejected writes and rejected
activations.

Replay is:

    SHEAR_SEED=<seed> \
        python -m unittest tests.test_malformed_generation

Existing targeted tests continue to cover malformed semantic records,
ownership, mappings, links, relations and other subsystem-specific invalid
states.

## 7. Stateful semantic simulation

**Decided:**

Task 18 adds deterministic generated operation sequences over a live runtime.

Operations include:

    write
    rejected write
    enter frame / hold
    keep reference
    release hold
    trial
    activate

These deliberately cross state, runtime-cell, transformation, reference and
version-lifecycle boundaries.

After every generated operation the harness checks global invariants including:

- the runtime owns an active version;
- at most two main runtime versions are loaded;
- the active version is not retired;
- the `previous` view agrees with version ownership;
- recorded holds are live and belong to exactly one version;
- runtime cell content belongs only to declared cells;
- runtime cell content satisfies its constraint;
- the harness's live hold handles agree with runtime hold records;
- the independently tracked cell content agrees with the runtime;
- the independently tracked semantic value agrees with the active state;
- rejected writes and rejected activations are atomic;
- trials leave the main runtime unchanged.

Failures report the operation step and seed.

Replay is:

    SHEAR_SEED=<seed> \
        python -m unittest tests.test_stateful_sequences

A failing sequence is passed through deterministic delta-debugging reduction
before it is reported. Reduction preserves the underlying failure fingerprint
rather than merely preserving the fact that some assertion fails.

The harness is intentionally extensible. Future semantic features can add
operations such as reconcile, explicit merge/split/disappearance and old/new
callable invocation without replacing the framework.

## 8. Bounded exhaustive testing

**Decided:**

Small semantic domains are checked exhaustively where practical.

Task 18 exhaustively checks continuity composition over a two-entity universe.

For each source entity, each relation can independently be:

- absent;
- known disappearance;
- mapped to the first entity;
- mapped to the second entity;
- split to both entities.

This produces a complete finite set of two-step relation compositions.

The raw finite relation domain is defined independently of
`TransformationDefinition.create()`. Construction is checked against that raw
domain, and the expected composition is computed from the raw relations rather
than by reading production-normalized objects back into the oracle.

The implementation is compared against a small independent relational oracle
that distinguishes:

    absent
    known continuation/disappearance
    unknown continuity

This complements generated testing by completely covering a small semantic
domain rather than sampling it.

## 9. Failure reproduction and reduction

**Decided:**

Generated failures must be reproducible and reducible before being promoted to
permanent regressions.

`tests/generation.py` provides shared infrastructure.

`SHEAR_SEED` accepts one integer or a comma-separated list:

    SHEAR_SEED=37 \
        python -m unittest tests.test_stateful_sequences

or:

    SHEAR_SEED=7,11,19 \
        python -m unittest tests.test_metamorphic

`SHEAR_CASES` changes the deterministic generated-case budget:

    SHEAR_CASES=1000 \
        python -m tests.lanes cross-boundary

Unset, empty, or `0` means that each test uses its ordinary default budget.

An explicit replay seed takes precedence over the case budget.

The shared helper also implements deterministic sequence delta-debugging. It
repeatedly removes chunks while the supplied failure predicate still holds,
producing a smaller sequence suitable for diagnosis.

Every real defect discovered by generated verification should become a small,
ordinary deterministic regression. A seed may remain as provenance, but the
regression should not depend on rediscovery.

## 10. Mutation testing

**Decided:**

Mutation testing covers the semantic implementation broadly enough that new
model modules cannot silently disappear from the campaign.

Before Task 18 the mutation campaign targeted eight implementation files.
Task 18 expands this to 23 targets, including identity records, the independent
embedded compiler and the SHEAR VM.

`tests/mutation_catalog.py` is the explicit inventory.

Every top-level production Python module and every example module must either:

- be a mutation target; or
- appear in `OMITTED` with a written reason.

Ordinary tests enforce this accounting.

The mutation engine uses Python's standard `ast` module to mutate the Python
reference implementation. That AST is test-tool implementation machinery only;
it is not a SHEAR program representation or compiler IR.

Before planting mutants, a campaign runs the exact mutation test command
against an unmodified repository copy made with the same copy and environment
rules used for mutant execution. A failing baseline aborts the campaign rather
than allowing unrelated infrastructure failures to count as killed mutants.

Baseline and mutant child suites run with
`SHEAR_MUTATION_SUBPROCESS=1`. Source-tree and mutation-catalog integrity
tests are harness meta-tests rather than semantic kill oracles, so they are
excluded identically from both child-suite kinds while remaining mandatory in
ordinary CI. This prevents a mutant, or the whole-file `ast.unparse()` rewrite
used to emit it, from being counted as killed merely because it changed source
text inspected by the mutation harness itself.

Campaign selection is deterministic. For a fixed target source,
`mutation_count`, seed and batch number, mutation sites are shuffled once by
the seed and the batch selects one consecutive slice of that ordering.
Successive batch numbers are therefore disjoint and running batches until they
become empty covers every mutation site exactly once.

The heavy CI campaign builds the complete selected mutation work set first.
That work set is deterministically shuffled from the campaign seed and
individual mutants are distributed round-robin across the configured shards.
Changing the shard count therefore changes only which job owns each selected
mutant, not which mutants were selected. Shards are disjoint and exhaustive
and differ in selected mutant count by at most one. Every individual mutant
still runs the complete semantic test suite, so sharding does not weaken the
kill criterion.

### Mutant outcomes

**Decided:**

A mutant run ends in one of five outcomes, and only a failing test is a kill.
The oracle (`tests/mutation_oracle.py`) writes a small status file
(`--status`) that `tests/mutation_verdict.py` defines and the campaign reads:

- `killed`: a test failed or errored;
- `timeout`: the run reached its limit (`--limit`, enforced by a watchdog in
  the oracle that also covers hangs while test modules import), so nothing was
  noticed in time;
- `resource_kill`: the first failure was `MemoryError` from the oracle's
  address-space cap;
- `abnormal_exit`: the process ended without a usable verdict, or the verdict
  contradicts the exit status;
- `survived`: every test passed.

A timeout, resource kill or abnormal exit is reported as such (with the test
running at the time) and is not counted as a kill. An unclassified survivor or
an abnormal exit fails the campaign; a timeout or resource kill is reported
but does not fail it, because a hang or memory exhaustion is a legitimate
effect of some mutants that no test is expected to name. Before this change
the engine counted a timeout as a kill, so one hanging mutant cost the full
900 s and was reported as killed.

A mutant's time limit is `max(180 s, 3 x the baseline run)`, not a fixed 900 s;
the baseline run itself has no limit. The engine's own timeout is a backstop
30 s longer, for a run that cannot report.

A mutant that makes a test module fail to import (with any exception, not only
`ImportError`) is a failing test, not a crash. Memory exhaustion that escapes
the test runner is a `resource_kill`, not an abnormal exit.

**Provisional:** the baseline records how long each test takes, and a mutant
run reports `timeout` as soon as one test runs longer than
`max(30 s, 10 x its baseline time)` (`--times`), instead of waiting for the run
limit. On CI the 12 hung mutants of a 2646-mutant campaign were about 79 % of
the campaign time at the 3 x baseline limit. The cost is a narrow gap: a mutant
that makes one test at least ten times slower but would still finish and pass
is reported as a non-failing `timeout` where it used to be an unclassified
survivor. Every timeout is printed with the test it stopped in and a `replay`
command, and replay does not apply the per-test budget. The baseline's slowest
tests are recorded in the report's `campaign_start` event, so a test that
becomes slow is visible there.

### Coverage-ordered runs and the coverage diagnostic

**Provisional:**

`python -m tests.mutation_coverage build --out map.json` runs each oracle
module once in its own process under `sys.monitoring` and records which lines
of the mutation targets it executes. A campaign given the map
(`SHEAR_MUTATION_COVERAGE=<path>`) runs, for each mutant, the modules that
execute its line first, then the modules that might (those that start
processes, whose lines the tracer cannot see, or that did not run cleanly),
then the rest. The oracle still runs every module and stops at the first
failure, so only the order changes and the outcome of a mutant does not. The
map carries a fingerprint of every file under `shear/` and `tests/` and a
campaign refuses a map that does not match its tree; CI builds it once in the
plan job and the shards download it. Without a map the default order runs.

`python -m tests.mutation_coverage report [target prefixes]` (workflow input
`coverage_diagnostics`) lists the executable lines of the targets that no
module executes. It is a diagnostic and gates nothing; lines it lists may
still be reached by the modules that start processes.

`python -m tests.mutation_performance mutation-report-*.jsonl` summarizes
reports as one campaign: wall time (slowest shard), CPU time (sum), outcomes,
kill-time distribution and in which stage mutants died. The workflow prints it
per shard and for the whole campaign.

### Reviewed survivors are not run again

**Decided:**

A survivor whose classification is current (its target and the engine match
their pins, which a campaign checks before it starts) cannot fail the campaign
and costs a whole oracle run. A campaign therefore reports it as `pinned, not
run` and does not execute it. `SHEAR_MUTATE_REVALIDATE=1` (workflow input
`mutation_revalidate`) runs them anyway; it is required after repinning a
target or the engine, since a changed review is exactly when a reviewed
survivor might now be killed or might no longer survive. Replay always runs
the mutant.

### Accepted and rejected optimizations

Measured on one local campaign: 76 mutants (`SHEAR_MUTATE=2`, seed 1, one
shard, two workers; 7 of them reviewed survivors), same tree apart from the
change. Wall time is the elapsed time of the whole test command, CPU the
children's user plus system time.

| | before | after |
| --- | --- | --- |
| wall | 2156 s | 655 s |
| CPU | 4103 s | 1024 s (+149 s once for the coverage map) |
| mean kill time | 31.7 s (excluding the hang) | 6.7 s |
| median kill time | 4.5 s | 0.8 s |
| hanging mutant | 900 s, "killed" | 440 s, `timeout` |
| outcomes | 69 killed, 7 reviewed survivors | the same, except the hanging mutant is `timeout` |

The same change on CI (`mutation_count` 150, seed 1, 16 shards, 2646
mutants; before = `main`, after = this branch before the per-test budget):
slowest shard 65.2 min to 17.6 min, median shard 48.3 min to 12.7 min, all
shards 724 to 191 shard-minutes; 2533 kills, 97 reviewed survivors not run,
12 timeouts, 2 resource kills. Shard balance did not change (slowest over
median 1.35 before, 1.38 after), so cost-aware sharding (#51) was not built:
the imbalance comes from the hung mutants, and a better assignment would save at
most a few minutes while needing per-mutant cost history that a fresh run does
not have and breaking the plain round-robin that replay relies on.

The mean kill time fell 4.7 times; the aim was 5 times, so the target was
narrowly missed and the change is kept because it also removes the survivor
re-runs and bounds hangs. 65 of 68 kills were found in the modules that
execute the mutant's line.

- Accepted: the outcome protocol (correctness); the 3 x baseline limit
  (a hang costs 440 s here instead of 900 s); coverage ordering (mean kill time
  31.7 s to 6.7 s); not re-running reviewed survivors (7 runs of about 140 s,
  roughly 980 s of the 4103 s CPU); the performance summary.
- Rejected: skipping modules that do not execute the mutant's line. Five oracle
  modules start processes whose lines the tracer cannot see, so "uncovered"
  cannot be proven for every line, and skipping would change kill decisions.
  Ordering gets most of the benefit without that risk.
- Rejected: a shared baseline for all shards. Each shard still has to show its
  own runner is healthy; the baseline is about 150 s per shard.
- Rejected for now: fork-per-mutant and de-duplicating mutants that compile to
  the same code. Over all 4056 sites 223 (5.5 %) compile to the same code as
  another mutant and none to the original, a small saving that needs an engine
  change, and any engine change repins and revalidates every reviewed
  survivor. If an engine change is ever needed, group these with it.
- Not decided here: Python 3.14 (#53). A local sample ran about 15 % faster and
  passed the oracle, but the survivor catalog needs one confirming exhaustive
  campaign under the new version before CI moves.

Limitations: the coverage map costs one traced run of every oracle module
(about 76 s wall, 149 s CPU here) per campaign; it needs Python 3.12 or newer;
a timeout is bounded by 3 x the baseline, so a campaign with many hangs is
still slow; the map cannot see code that child processes run.

### Survivor identity

A reviewed survivor has a compact site key:

    target file
    mutation kind
    complete stripped source line
    occurrence among sites with the same kind and source line

The occurrence distinguishes multiple mutable constructs represented by the
same line, including nested constructs.

That key is deliberately valid only for one reviewed target-source version
under one reviewed mutation-engine version. It is not treated as a persistent
identifier across edits to either the target source or the machinery that
discovers and interprets mutation sites.

Every file containing one or more reviewed survivor classifications is
therefore pinned in `SURVIVOR_SOURCE_BLOBS` to the Git blob ID of the exact
source bytes under which those classifications were reviewed.

The mutation engine itself is separately pinned in `SURVIVOR_ENGINE_BLOB` to
the exact Git blob ID of `tests/mutation.py` under which the classifications
were reviewed. Site-discovery order, occurrence assignment and mutation
operator semantics are part of the meaning of a survivor key, so changing the
engine can invalidate a classification even when the production source is
byte-for-byte unchanged.

Any edit to a pinned production file – including an unrelated edit or
insertion of another identical mutable line – changes its blob ID and
invalidates all reviewed survivors in that file. Any edit to
`tests/mutation.py` invalidates the reviewed survivor catalog as a whole.
Affected classifications must be explicitly re-reviewed before the
corresponding source or engine pin is updated.

Ordinary catalog tests require:

- source pins to cover exactly the targets that have classified survivors;
- every source pin to name a current mutation target;
- each pinned source to match its reviewed Git blob ID;
- the mutation engine to match its reviewed Git blob ID;
- every survivor key to identify exactly one mutation site under those
  reviewed source and engine versions.

Direct mutation campaigns perform both source-pin and mutation-engine-pin
validation before baseline or mutant execution and refuse to run with missing,
obsolete or stale survivor review pins.

This deliberately conservative version pinning prevents a compact
occurrence-based key from silently rebinding to a different semantic construct
after a source edit or silently changing meaning after a mutation-engine edit.

### Survivor classification

The useful historical survivor knowledge from earlier mutation campaigns was
migrated to exact current keys where the reason remained defensible.

Historical entries are not copied blindly:

- semantically equivalent mutations are classified `equivalent`;
- behaviour deliberately outside the semantic contract may be classified
  `unspecified`;
- a known semantic test gap is never classified as a permitted survivor;
- an old entry that cannot be mapped confidently to one current mutation site
  remains unclassified until a campaign rediscovers an exact survivor.

In particular, the historical `Function` equality survivor was documented as
an open test gap, not an equivalence, so it is not whitelisted.

Generation-allocation mutations are likewise not whitelisted: graph-form
generation numbers are part of node identity, so changing initial generation,
next-generation allocation or collision advancement changes specified semantic
identity and must be killed by regression tests.

Every survivor classification carries a written reason.

A new unclassified survivor therefore means one of three things must happen:

1. prove it equivalent and record the reason;
2. establish that the changed behaviour is intentionally unspecified and
   record the reason;
3. treat it as a test gap, add a regression, and kill the mutant.

A test gap is never resolved by adding it to the survivor catalog.

Mutation operators remain intentionally simple. New operators should be added
when a concrete missing fault class justifies them rather than to increase a
nominal mutation score.

## 11. Practices borrowed

Established verification practices are used selectively rather than treating
another project's test architecture as a template.

Relevant influences include:

- LLVM – separation of focused regressions and whole-program suites;
- Rust – first-class negative testing;
- Csmith – valid-program differential generation;
- EMI – equivalence-modulo-inputs compiler testing;
- Alive2 – validating transformations against semantic contracts;
- SQLite – independent harnesses, malformed inputs and boundary testing;
- Hypothesis/QuickCheck-style systems – generation, state machines and
  shrinking;
- deterministic simulation used in complex stateful systems – long,
  reproducible operation sequences with invariant checking.

SHEAR's own graph identity and continuity rules take precedence over
assumptions from conventional languages.

## 12. CI structure

**Decided:**

The ordinary deterministic suite is partitioned into eight semantic lanes:

    core-model
    language-runtime
    transform-continuity
    syntax-reconcile
    compiler-self-hosting
    vm-bootstrap
    cross-boundary
    mutation

`tests/lanes.py` owns the exact partition. Every ordinary `test_*.py` module
must belong to exactly one lane. Missing, duplicate and stale assignments are
errors.

CI runs every lane in one job with `python -m tests.lanes --all`: each lane is
its own process, as many at a time as the runner has CPUs, and every lane runs
to completion, so one semantic failure does not hide results from unrelated
lanes. The job prints each lane's result and duration.

The ordinary `mutation` lane runs mutation-engine and catalog integrity tests.
It does not launch the expensive planted-mutant campaign by default.

Heavy mutation verification is a separate multi-shard job. The complete
selected work set is built before sharding, deterministically shuffled from the
campaign seed, and individual mutants are distributed round-robin across the
configured shards. Each mutant still runs the complete semantic suite.

Manual workflow dispatch exposes:

    generated_cases
    mutation_count
    mutation_seed
    mutation_batch
    mutation_shards

`generated_cases=0` uses ordinary generated-test budgets.
`mutation_count=0` skips the heavy mutation campaign.
`mutation_shards` sets how many jobs share the campaign. Left empty, a small
plan job counts the selected mutants with the campaign's own selection
(`python -m tests.mutation_campaign plan`) and uses one shard per 150
mutants, between 1 and 16: each shard pays runner setup and one baseline
oracle run before its first mutant, so small campaigns stay on few runners.
An explicit value from 1 to 16 overrides the sizing. The cap of 16 keeps a
campaign and the test job within the account's concurrent-job limit with
room to spare, so other runs are not starved.

A positive mutation count selects that many sites per target in the requested
deterministic batch. A count larger than the number of sites in a target
selects all of that target's sites in batch 0.

The purpose of parallelization is lower development/PR latency while preserving
deterministic results. Hosted-runner queueing is not treated as semantic test
runtime.

## 13. CI tiers

**Decided:**

Use different budgets for different feedback loops.

Every PR runs:

- the complete ordinary deterministic suite, split into the eight semantic
  lanes;
- deterministic generated differential and cross-boundary tests at their
  ordinary budgets;
- bounded exhaustive checks;
- deterministic stateful/adversarial tests at their ordinary budgets;
- mutation-engine, target-accounting, survivor-catalog, source-pin and
  mutation-engine-pin integrity tests.

Larger manually triggered verification runs may use:

- substantially larger generated-case budgets;
- broader deterministic stateful campaigns where configured;
- planted-mutant campaigns across selected deterministic batches;
- exhaustive mutation selection by choosing a per-target count larger than the
  current mutation-site population.

A heavy-run failure must remain reproducible from its recorded seed, batch,
target and site identity.

Historical timings and campaign results belong in `CHANGES.md` and the PR
record rather than becoming normative CI requirements here.

## 14. Acceptance

**Decided:**

Task 18 is done when:

- the verification boundaries and their test methods are documented;
- the ordinary suite is split into meaningful parallel CI jobs;
- before/after ordinary-suite wall time is recorded;
- important independent implementations have differential coverage over
  generated cases where their domains overlap;
- malformed generation exercises important semantic boundaries;
- a deterministic stateful sequence harness checks global invariants;
- at least one bounded-exhaustive test family covers a small semantic domain;
- mutation targets cover the semantic implementation substantially more
  completely, with survivors explicitly reviewed and fail-closed against
  target-source and mutation-engine version drift;
- generated failures can be reproduced and reduced;
- discovered real defects are preserved as minimized regression tests;
- no production semantic behaviour is intentionally changed.

Task 19 may then refactor architecture against this stronger verification
baseline.

## 15. Mutation workflow reference

Moved from CLAUDE.md's Testing section; no rule changed.

- Mutation target policy and explicit omissions live in
  `tests/mutation_catalog.py`. Reviewed survivor classifications and exact
  target-source pins live in per-target TOML files under
  `tests/mutation_catalog_data/`; its manifest pins the mutation-engine version
  and inventories every target with classified survivors. The Python loader
  validates that serialized catalog fail-closed.
- A survivor classification is valid only for the exact pinned target-source
  version and pinned mutation-engine version under which it was reviewed. Any
  edit to a target file invalidates all survivor classifications for that file
  until explicit re-review and repinning; any edit to `tests/mutation.py`
  invalidates the survivor catalog as a whole until explicit re-review and
  repinning.
- Run a seeded mutation sample with, for example:

      SHEAR_MUTATE=1 SHEAR_MUTATE_SEED=1 \
          python3 -m tests.test_mutation

  `SHEAR_MUTATE` is the number of mutants sampled per target. A survivor may
  be catalogued only when it is reviewed as semantically equivalent or
  intentionally unspecified, with a reason. A semantic test gap receives a
  regression test and must not be whitelisted as a survivor.
- Mutation work is selected before sharding. The complete selected set is
  deterministically shuffled from `SHEAR_MUTATE_SEED`, then individual
  mutants are distributed round-robin across `SHEAR_MUTATE_SHARDS`.
  Changing the shard count must not change the selected mutation set, and shard
  sizes differ by at most one mutant.
- The mutation subprocess semantic oracle is centralized in
  `tests/mutation_oracle.py`. The ordinary `mutation` lane contains harness,
  catalog and infrastructure checks and remains mandatory CI, but it is
  excluded from mutation-kill decisions. Baseline and mutant subprocesses must
  use the same semantic oracle command.
- Mutation campaigns emit flushed human progress plus JSONL evidence. Set
  `SHEAR_MUTATION_REPORT=<path>` to choose the report path. Each report pins
  the mutation engine and target sources, records campaign inputs and exact
  selected keys, records every mutant outcome, and ends with reconciled counts
  and diagnostic timing summaries.
- Replay one reported mutation directly from its key and pins:

      python3 -m tests.mutation_campaign replay \
          --key-json '["shear/example.py","constant","value = False",0]' \
          --source-blob <source-blob> \
          --engine-blob <engine-blob>

- After a large failed campaign, replay only the previously unclassified
  survivors from one or more downloaded shard reports:

      python3 -m tests.mutation_campaign replay-failures \
          mutation-report-*.jsonl

  Report-driven replay validates completed reports and their recorded pins,
  runs the semantic baseline once, and then executes only the recorded
  unclassified survivors. It does not reconstruct their original seed, batch,
  or shard.
- Larger generated and mutation campaigns are available through manual
  workflow dispatch; ordinary PR CI keeps the deterministic default budgets.
  Mutation campaign shards publish their JSONL evidence as workflow artifacts,
  including when a shard fails after finding unclassified survivors.
- Mutant outcomes, the time limit, coverage ordering and the coverage and
  performance diagnostics are described in section 10. Commands:

      python3 -m tests.mutation_coverage build --out map.json
      SHEAR_MUTATE=2 SHEAR_MUTATION_COVERAGE=map.json \
          python3 -m tests.test_mutation
      python3 -m tests.mutation_coverage report shear/reconcile.py
      python3 -m tests.mutation_performance mutation-report-*.jsonl

  `SHEAR_MUTATE_REVALIDATE=1` runs reviewed survivors too; use it after any
  repin. The dispatch inputs `mutation_revalidate`, `coverage_diagnostics` and
  `coverage_targets` do the same in CI.
