# Hosted Bootstrap Implementation

**Status: implemented** (roadmap.md task 30, issue #66; live evolution, task
31, issue #67, section 6 and the live measurements in section 4.1). The contract is
[`hosted_pipeline.md`](hosted_pipeline.md) and, for live evolution,
[`live_evolution.md`](live_evolution.md), written by Plan and not changed
here. This document records how Execute built it, what is provisional, what
it covers and how to measure it.

## 1. Module map

`shear/examples/compiler_source.py` holds the one SHEAR compiler: a single
lowering core, `lower_op(e, mode)`, with two entries. `lower(e)` is mode 0
(expanded chunks, as before). `compile_node(d)` is mode 1 (a node-aware chunk
whose children and call targets are entity ids). `self_hosting.py` keeps the
self-rewriting programs and re-exports the compiler's names.

`shear/hosted_bootstrap/`:

| Module | Responsibility |
|---|---|
| `seed.py`, `manifest.json`, `seed_cli.py` | The generation-0 seed: the compiler nodes the host lowers, derived from the source and checked in. `SeedGate` is the only door to host lowering. `python3 -m shear.hosted_bootstrap.seed_cli [--write]` checks or regenerates the manifest. |
| `generations.py` | Builds generations 1 to 3, each by running `compile_node` on the machine over the previous generation's admitted artifacts. |
| `descriptors.py` | Builds the argument of `compile_node` for a node and decodes the answer. Makes no lowering decision. |
| `validation.py` | Structural admission checks on a chunk: known instructions and operand types, children and links of the node and its owner, and a single pass over the operand stack (no underflow, empty at a handover, nothing after a handover or raise, exactly one result). No host re-lowering. Every fact about an instruction is read from `shear/instructions.py` when a chunk is validated. |
| `artifacts.py` | Admitted artifacts (with `reused_from` for a reused one), content-derived ids and the per-set chunk resolver. |
| `target.py` | One target program: produce, admit, run, and the artifact sets its versions own (section 6). Opaque evidence handles bind an admission to one compiler run. |
| `session.py`, `command.py` | The public boundary (`HostedSession`) and the documented command. |
| `trace.py`, `errors.py` | Provenance events (`reuse` and `release` among them, and `source_artifact_id`); `AdmissionRejected`, which is not a program error. |
| `diagnostics.py`, `live_diagnostics.py` | Section 10 measurements; the live evolution measurements (section 4.1). |

`shear/instructions.py` is the one table of the instructions lowering emits
(operand counts, which operands are children, link targets, names or counts,
and the stack effect). It is metadata: admission reads it, the SHEAR-written
VM's generator (`examples/vm.py`) reads operand positions from it where it
already encoded them, and the machine's dispatch stays separate execution.

`machine.run` takes an optional `resolver`, scoped to the run by a context
variable. When given, every chunk the machine opens comes from it; without
one, behaviour is unchanged. A resolver failure is not a `LanguageError`, so
a program cannot `catch` it.

## 2. Operation coverage

In node mode the SHEAR compiler lowers every input-form operation of
`operations.py`, including `activate`, `function`, `quote`, `trial` and
`unquote` (task 31), plus `catch`, `raise` and the host's `invalid` node
(`compiler_source.NODE_LOWERED`). Expanded mode (`lower`) still lowers the
five to the `RAISE` it emitted before, because its chunks feed only route A,
whose VM cannot run them. A node whose kind the compiler does not lower
(nothing in the corpus now) is recorded as a `reject` event when the target
is prepared, and running it fails closed with `AdmissionRejected`; nothing
falls back to host lowering. The `activate` and `trial` descriptors carry
the operation's entries, link targets and problems; host lowering keeps a
problem (an unresolved link, a non-function value) in the instruction, and so
does the compiler, so the machine fails exactly as it does for host chunks.

`tests/test_hosted_bootstrap.py` also runs `applyv` and `linksof`, which the
corpus subset lacks, on admitted artifacts against ordinary execution, and
compares the compiler's chunk with
`bytecode.lower` for every supported node of every corpus program.

## 3. Provisional integration choices

**Provisional:**

These were chosen to satisfy the contract and are open to Review.

- The descriptor is `(operands, (state_id, node, version, owner))`. Children
  and call targets are entity ids; link names are replaced by their targets.
  The specification has descriptors carry the permitted linked function and
  cell identities; here admission checks them instead, on the host side in
  `validation.py`, against the node's and its owner's links.
- The operand of `LIT` stays in canonical form, as a node's payload does in
  host lowering. Other identities and tuples are decoded to plain values.
- A change of the active state by the host API, outside a run, is not
  reported to the target: the new version owns no set, and a caller must
  `prepare` again. A change made by the running program (`activate`,
  `trial`) is reported and handled as section 6 describes.
- An artifact is keyed by (entity, version) and bound to the state id, the
  owner and the producing compiler generation.
- Execution events are recorded on the first use of an artifact in a
  session, not on every use.
- Admission establishes origin and structure, not compiler correctness
  (D3). Correctness is evidenced by the differential test above.

## 4. Diagnostics

    python3 -m shear.hosted_bootstrap.diagnostics --repeats 5

prints environment, initialization, generations 1 to 3, production,
admission, independent verification against host lowering, cold and warm
execution, the phases of a small edit, peak memory (a separate traced pass)
and artifact counts and sizes. Observations and medians are reported per
workload and never combined into ratios. D4's targets are diagnostic only.
Task 23 and Task 29 measurements are unchanged.

Medians of 5 repeats at revision `df87eec`, on a 2-vCPU Intel Xeon 2.8 GHz
container, Python 3.13, Linux 6.18 (indicative; the `hosted_diagnostics` CI
dispatch records the same on a CI runner):

| Measurement | Median | D4 target (aspiration) |
|---|---|---|
| Seed: derive and verify manifest (682 nodes) | 1.7 ms and 3.7 ms | |
| Compiler generation 1 | 0.34 s | 10 s (1 s) |
| Compiler generation 2 | 0.28 s | 10 s (1 s) |
| Compiler generation 3 | 0.27 s | 10 s (1 s) |
| Small edit: reconcile, prepare and admit, run, activate | 1.8, 4.1, 0.3 and 0.03 ms | 50 ms (10 ms) |
| Peak memory, generations 1 to 3 and one run | 2.9 MB | |

Each generation has 682 artifacts of 223,295 bytes in total. Per workload,
production and admission of every supported node, then cold and warm
execution, with ordinary host execution shown for reference only:

| Workload | Nodes | Produce | Admit | Cold run | Warm run | Host run |
|---|---|---|---|---|---|---|
| factorial | 11 | 2.7 ms | 1.3 ms | 0.27 ms | 0.021 ms | 0.054 ms |
| insertion_sort | 45 | 11.9 ms | 5.4 ms | 1.56 ms | 0.14 ms | 0.18 ms |
| compiler | 686 | 220 ms | 101 ms | 2.3 ms | 0.13 ms | 0.23 ms |

The workloads differ, so no ratios are formed. These are inside D4's
aspirations; they do not reinterpret Task 29's falsified cold-cost
prediction, whose workload was different.

### 4.1 Live evolution measurements

    python3 -m shear.hosted_bootstrap.diagnostics --repeats 5 \
        [--live-updates 20] [--live-sizes 10,100,1000]

also prints `live` (`live_diagnostics.py`, live_evolution.md section 7), by
task 23's method: untraced observations with medians, peak memory in a
separate traced pass, no ratios between workloads, D4's targets diagnostic
only. The workload is a small live image (a cell, `handle`, `plus`, which
builds a changed `handle` from `code(handle)`, `update`, which activates it,
`rejected`, which tries a wrong candidate, and unrelated one-line functions).
Three kinds of update run on it:

- **valid**: `update` changes `handle` only;
- **trial-rejected**: the image's own rejection. `rejected` tries a candidate
  whose answer is wrong and does not activate it; the candidate is compiled
  and admitted, run in the trial and released;
- **refused**: an injected failure. The valid update runs while admission
  refuses `ADD`, so the activation ends with `AdmissionRejected` after the
  compiler produced a chunk. Every reused chunk with `ADD` is refused too,
  which is why it reuses nothing. It measures the cost of failing late, not
  of a program's rejection.

Phases are timed by wrapping the functions that perform them. The task 23,
29 and 30 workloads are unchanged. The smoke test is
`LiveDiagnosticsTests` in `tests/test_hosted_pipeline.py`.

Medians at revision `7f39921` (clean tree), on a 2-vCPU Intel Xeon 2.8 GHz
container, Python 3.13.16, Linux 6.18 (indicative, one run). Twenty updates
of each kind, in sequence, on one 16-function image, in milliseconds. The
trial has no switch, and the valid update's first call is the next run of
`handle`:

| Update | Construct | Stage | Compile | Reuse | Admit | Switch | First call | Whole run |
|---|---|---|---|---|---|---|---|---|
| valid | 4.2 | 0.38 | 0.79 | 18.1 | 0.27 | 0.006 | 1.9 | 26.0 |
| trial-rejected | 5.1 | 0.41 | 0.78 | 21.8 | 0.28 | n/a | n/a | 32.8 |
| refused | 5.1 | 0.39 | 0.48 | 0.12 | 0.10 | n/a | n/a | 6.6 |

Every valid and trial-rejected update produced 2 artifacts and reused the
rest (82 to 120 for the valid ones, which grow `handle` by two nodes each;
122 for the trial-rejected ones, whose candidate is released); every refused
update produced 1 and reused none. After each of the 60 updates there was 1
loaded version and 1 retained set. The set held 84 to 122 artifacts after
the valid updates and 122 after the other two kinds: a rejected trial or a
refused activation adds nothing to what is retained. Peak memory over
prepare and 20 valid updates and calls was 4.1 MB (2.5 MB held after
prepare, 4.0 MB after the updates; one retained set at the end).

One small edit at three sizes (fresh image per repeat, 5 repeats), in
milliseconds:

| Functions | Nodes reused | Prepare | Construct | Stage | Compile | Reuse | Admit | Switch | First call | Whole run |
|---|---|---|---|---|---|---|---|---|---|---|
| 16 | 82 | 560 | 2.7 | 0.32 | 0.77 | 14.3 | 0.26 | 0.008 | 0.93 | 20.2 |
| 106 | 352 | 647 | 9.2 | 1.2 | 0.85 | 61.6 | 0.34 | 0.007 | 1.2 | 76.2 |
| 1006 | 3052 | 3355 | 93 | 10.7 | 1.5 | 1169 | 0.92 | 0.009 | 4.8 | 1309 |

The sizes are different workloads and no ratios are formed. What the numbers
show: compilation and admission cost depend on the changed nodes only; the
switch is negligible; the cost that grows with the program is the reuse of
unchanged nodes (rule 4.3 re-verifies each source artifact, revalidates its
chunk against the candidate and derives a new content id), and the
construction of the candidate. Reuse is the dominant phase at 100 functions
and more. A cheaper reuse check is a possible follow-up, not part of this
task.

The same run measured the older workloads again at this revision (medians of
5): seed 907 nodes (derive 1.9 ms, verify 6.9 ms), generations 1 to 3 in
0.49, 0.35 and 0.39 s with 907 artifacts each, the compiler workload 911
nodes (produce 410 ms, admit 147 ms), the small edit in 1.7, 4.5, 0.33 and
0.05 ms, and peak memory of 3.9 MB. The seed grew from 682 to 907 nodes
because node mode now lowers every kind. The table in section 4 is the
task 30 record at its own revision and is not replaced.

## 5. Mutation decisions

`compiler_source.py` and the `hosted_bootstrap` modules are mutation
targets, except `__init__.py`, `__main__.py`, `errors.py`,
`diagnostics.py` and `live_diagnostics.py`, whose omissions are justified in
`tests/mutation_catalog.py`. `shear/instructions.py` is a target: its table
is checked against the machine's dispatch, the chunks host lowering produces
and the VM, and admission reads it. The Task 29 spike and its test are removed.
Because the seed manifest pins the compiler source, any change to
`compiler_source.py` fails the manifest check at once; behavioural coverage
of the compiler is the differential test and the self-hosting suite.

## 6. Live evolution (task 31)

**Provisional:**

The choices below are Execute's within live_evolution.md; the contract
itself is not changed.

- **Hook.** `runtime.listening(listener)` attaches a `VersionListener` to
  every runtime for the block, through a context variable; `None` detaches.
  The runtime tells it of a staged and accepted candidate of `activate` or
  `trial` before anything changes (so a language rejection, which comes
  first, never reaches it, and an exception from it leaves the runtime as it
  was), of a version that retires, and of the end of a trial. `HostedTarget`
  is the listener for `run`. The compiler runs of `generations.py` detach
  it, so a compiler run does not report to the target it serves. Nothing is
  exported from the golden API modules; `runtime.py` is not among them.
- **Ownership.** The target holds one `ArtifactSet` per `Version` object (the
  prepared set belongs to the active version). The machine asks the resolver
  `for_version(version, entity, owner)` with the version of the frame that
  opens the node, so two loaded versions with one state (`same_activate`)
  have separate sets. The chunk boundaries `_open`, `_open_closure` and
  `_child_chunk` stay as they were. A set is released, invalidated and traced
  with `release` when its version retires (`"retired"`) or its trial ends
  (`"trial"`). A version can also retire outside a run, when the host
  releases the hold that kept it; the runtime does not tell the target then,
  so the target releases the set of every retired version whenever it is
  asked about sets (`retained_versions()`, `admitted()`) or starts a run.
- **Compilation.** `candidate()` builds the new set locally: for each code
  node it reuses the active version's artifact if the rule holds (same
  entity and version, same owner, produced by this session's compiler
  generation, and the chunk still validates against the candidate), else runs
  the SHEAR compiler and admits the result. Only when every node is admitted
  does the set become the version's. On a failure it traces `reject`,
  invalidates the partial set and re-raises `AdmissionRejected`, before the
  switch or the trial run. Host-API activations are not reported and reuse
  nothing; a trial's candidate reuses from the active version only, never from
  another trial's set.
- **Reuse.** A reused artifact is a new `Artifact` bound to the candidate's
  state, sharing the chunk object, with `reused_from` and a content id that
  includes the source's id, so a state admitted twice gets two ids. The
  `reuse` event carries `source_artifact_id`.
- **Trials.** `machine` ends a trial in a `finally`
  (`Runtime.end_trial`), so a failing trial run releases its set too.
- **`run`.** A run is refused with `AdmissionRejected` when the runtime's
  active version owns no set (the host API changed it); the run uses the
  resolver over the target's sets inside `listening(self)`.
- **Tables.** `INSTRUCTIONS` field names beyond `operands`, `children` and
  `linked` (`grouped`, `optional`, `names`, `counted`, `sized`, `taken`,
  `taken_by`, `left`, `handover`, `raises`) and the descriptors' layout for
  `activate` and `trial` are Provisional.
