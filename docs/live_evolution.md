# Live Evolution on the Hosted Route – Task 31

**Status: Provisional Plan contract; D3, D4 and D5 Decided.**

Issue #67. Baseline: `main` at `4ed6e14`. This specification defines the
implementation and acceptance boundary for roadmap task 31. The route,
seed and generations of task 30 ([hosted_pipeline.md](hosted_pipeline.md),
[hosted_bootstrap.md](hosted_bootstrap.md)) are its starting point and are
not restated here. D5 is recorded in [roadmap.md](roadmap.md); this document
applies it.

## 1. Goal

Complete the hosted-bootstrap milestone: a running image whose program
changes itself, with every executed program-code artifact produced by the
SHEAR compiler and admitted through route B.

The image is a target runtime joined to its retained compiler: the pinned
compiler source state and the admitted compiler generation the session
compiles with (hosted_pipeline.md section 3). The compiler stays outside the
target's canonical state; the anchor "an image retains the compiler
machinery that regenerates its execution" (reviews/bootstrap_delivery.md
section 4) is met by the session, not by putting compiler entities into the
target.

Invariants carried from task 30 and unchanged: canonical source is never
rewritten by artifact work; host lowering is reachable only through the
declared seed and remains a differential oracle; admission authenticates
origin and structure, not correctness; `AdmissionRejected` is a host
failure outside every language error.

## 2. Workload

### 2.1 Corpus

Every example of `shear.examples.EXAMPLES` runs on the admitted route. Task 30
covers 20; task 31 adds the nine it deferred, with every scenario and step
and their original expectations:

| Group | Examples |
| --- | --- |
| Self-modification | `power_compiler`, `checked_compile`, `replace_self`, `sort_swap`, `instrument` |
| Historical wrapper bootstrap | `bootstrap` |
| Error canaries | `safe_install`, `account_report`, `lookup` |

`account_report` and `lookup` already pass on the task-30 route; they are
now claimed. `bootstrap` is an ordinary target program here: its wrappers
hand literal chunks to the SHEAR-written VM, which interprets them as data.
The host machine executes only SHEAR-compiled, admitted chunks of the
wrappers and the VM. This is not program-supplied bytecode in D4's sense,
and it does not make wrappers part of the image's compiler.

### 2.2 The live image

`tests/live_support.py` holds a program in text syntax version 0 (`IMAGE`),
which the acceptance tests drive as a persistent image. It:

- reads its own code with `code(handle)` and builds a candidate from it with
  `function` and `quote`/`unquote`/`literal`;
- trials each candidate under `catch` and activates only one that passes;
- rejects candidates that crash (`out_of_range`), raise a program error
  (`bad_input`) or answer wrongly (`wrong`), leaving the active version and
  the live cell `total` unchanged;
- installs a sequence of valid updates, each building on the code the
  previous one installed, while `total` keeps accumulating across them;
- continues an old frame in its starting version across an activation of
  itself (`migrate`), while its calls enter the new version;
- applies a closure created before an activation after it: with an unchanged
  body, with a body the activation continued and changed (`scaler.calc`),
  and with a body the activation removed;
- meets the two-version bound: a second activation while the first one's
  previous version is held is rejected (`activation_rejected`);
- moves nodes to another function with a program-driven activation (`move`);
- trials a candidate identical to the active program (`same_trial`), whose
  state is the active state itself (section 4.2);
- activates the active program itself inside a run (`same_activate`), so two
  loaded versions share one `StateID` until the old frame returns;
- breaks the two-version bound with a candidate that cannot be compiled
  under a test's injection (`bound_first`, section 3.2);
- grows `handle` by a node kind (`len`) that no other code node of the
  program has (`grow`, used by `guarded` and `guarded_trial`), so a test can
  make exactly the new candidate node fail to compile or to be admitted.

The trial-rejection kind `depth_limit` is covered by `safe_install`.
`MALFORMED` adds the activation and trial forms whose link does not resolve
or whose value is not a function: host lowering keeps the problem in the
instruction, and each fails as a language error.

Continuity in these activations is inferred by `define`
(continuity_inference.md); the program does not declare it. The roadmap's
"declared continuity" is met in that sense: the oracle compares the
resulting `StateID`s with host execution step by step, so every identity
decision must match.

### 2.3 Operation coverage

The SHEAR compiler's node mode lowers every graph-form node kind:
`descriptors.SUPPORTED_KINDS` equals `lang.NODE_KINDS` (which includes
`invalid`). The five kinds task 30 left out are `quote`, `unquote`,
`function`, `activate` and `trial`. Their host lowering in `bytecode.lower`
is the specification of the chunk, including the forms that carry a problem
string, an empty target tuple or no trial target. The existing differential
test (`CompilerAgreesWithHostLowering`) covers the corpus, and
`MalformedActivation` covers the problem forms.

**Provisional:**

Expanded mode (`lower(e)`) keeps lowering the five to the `RAISE` it
emits today. Expanded chunks feed only route A, whose VM cannot
run these instructions (section 5.3). `docs/bootstrap.md`'s matrix keeps
describing expanded mode and gains a note that node mode covers every kind.

Node mode therefore needs its own set of lowered kinds.
`compiler_source.LOWERED` stays the expanded-mode set, which
`tests/test_bootstrap_boundary.py` pins; node mode gets a separate set in
`compiler_source.py`, and `descriptors.SUPPORTED_KINDS` is derived from it.
`descriptors`, `seed` and `diagnostics` keep reading their module-level
`SUPPORTED_KINDS` when they run, which the fail-closed tests patch.

## 3. Candidates (D5)

### 3.1 When and by what a candidate is compiled

**Decided (D5.1):** a candidate built by a running program is compiled by the
image's retained compiler when the program runs `activate` or `trial`: after
the host has staged the candidate state and before the switch (for
`activate`) or before any candidate code runs (for `trial`). Each code node
of the candidate either reuses an admitted artifact (section 4.3) or is
compiled by the session's compiler generation and admitted against the
candidate state.

The atomicity rule is: **a candidate becomes active, or runs in a trial, only
when every one of its code nodes is admitted.** The moment a chunk is
produced is hidden behind the resolver; this contract produces them eagerly.

**Open (recorded by D5.1):** lazy or tiered production. Chunks could be
produced on first use or in the background, provided that before the switch
the host decides everything that can make a node fail to compile (supported
kind, descriptor, links, owner and children). The only failure left after the
switch would be a compiler fault or tampering, which is a host failure under
D5.2 anyway. Revisit when measured activation latency or native code makes
production cost matter.

### 3.2 Failure

**Decided (D5.2):** if a candidate node cannot be compiled or admitted, the
activation or trial does not happen. The runtime keeps its active state,
loaded versions and cell content, and the run ends with `AdmissionRejected`.
A program's `catch` cannot see it, including a `catch` around the `activate`
or `trial`. With every node kind supported, only a compiler fault, an
invalidated compiler generation or tampering reaches this path.

The failure may come after some candidate nodes were already compiled or
reused: in the tests, a chunk is refused at admission after the compiler
produced it. Nothing of the attempt survives it: no candidate artifact set,
admitted artifact record or retained version, and no hold. Only the trace
records it.

A candidate the language rejects keeps its existing failure: a missing
activation capability, a malformed definition, a constraint or a
two-version-bound rejection is raised as today.

**Language rejections take precedence.** This follows from D5.2: this path is
for host faults, never a substitute for a language rejection. A candidate is
compiled only once the language would accept it. The machine rejects the
capability and a malformed definition before any compilation. The cell,
constraint and two-version-bound checks in `Runtime.activate`, and the
staging in `Runtime.trial`, run before the candidate is compiled; the switch
or the trial run comes after. So a compilation failure can never mask a
catchable language rejection. `bound_first` witnesses this: it breaks the
bound with a candidate that cannot be compiled, and the program sees
`activation_rejected`.

### 3.3 The compiler run

The compilation of a candidate is a separate machine run on the compiler's
runtime, over the session's admitted compiler artifacts. It does not inherit
the target run's resolver, activation capability, cells or `catch` scope, and
it never reaches host lowering. The compiler generation is the one the
session was prepared with; it does not change during the image's life
(**Provisional**; evolving the image's own compiler is a later concern).

## 4. Artifact lifetime

### 4.1 Ownership

**Decided:**

By activation_model.md section 7 ("a version owns its native code"), a
loaded version owns the admitted artifacts of its state. An artifact
set lives as long as its version is loaded and is released when the version
retires. The artifacts of a state that is not loaded cannot be used.

An artifact set belongs to a version: a loaded version of the runtime, or
the version of a running trial (section 4.2). It is not an entry under a
`StateID`, because two owners can have the same state:

- a trial of a candidate identical to the active program (`same_trial`);
- an activation of the active state itself while the old frame still holds
  the previous version (`same_activate`), which leaves two loaded versions
  with one `StateID`.

At every step boundary, the versions that own a set (`retained_versions()`)
are exactly the runtime's loaded versions. During a run they include at
least those.

A released set leaves nothing in the session that keeps its artifact
records alive; the tests count target `Artifact` objects in the heap. Chunks
shared through reuse stay alive as long as some retained artifact uses them.
The trace is intentionally retained history and keeps identifiers only.

### 4.2 Trials

A trial's version gets its own artifact set, admitted before the trial runs.
It is released when the trial returns, fails inside, or cannot be admitted.
It is never used for the parent runtime's versions, and nothing is reused
from it afterwards: an activation of the same candidate compiles again
relative to the active version (**Provisional**).

A trial whose candidate equals the active state (`same_trial`) still gets
its own set, of separate admission records. Its nodes all reuse the active
version's chunks (section 4.3). Releasing it leaves the active version's set
as it was. The same holds for two loaded versions of one state: each owns
its own records.

### 4.3 Reuse

**Provisional rule.** A code node of candidate state D reuses the artifact of
the active state S when:

1. the node has the same `EntityID` and `VersionID` in S and D;
2. its owner is the same function in S and D;
3. the artifact was produced by the session's compiler generation; and
4. structural admission (`validate_chunk`) passes against D.

Otherwise the node is compiled. Reuse creates a new admission bound to D
(the artifact's identity includes the target `StateID`, task 30), recorded
as a `reuse` event naming the source artifact, and the chunk object is
shared, not copied. The source is always an artifact of the active version
S, for a trial's candidate and an activation's alike.

Why this is dependency-safe: a chunk is a function of its node's content and
the compiler alone (`bytecode.lower` takes only the node). Children, call and
apply targets, cells and closure bodies appear in it by `EntityID`. They are
resolved when they run, each to its own artifact in the frame's state; the
note of the continuity case `extract_function` in `shear/continuity.py` says
the same. Rule 2 is therefore not needed for the chunk. It is a conservative
choice: admission binds an artifact to its owner and checks the owner's
links, so a moved node is admitted afresh. Rule 4 re-checks links in D.
Nothing is inferred from a `VersionID` alone.

Reuse happens only for program-driven activations and trials. After a host
API activation outside a run, `prepare` is still required and compiles the
new state afresh, as task 30's tests pin (**Provisional**).

### 4.4 Frames and closures across activation

These follow the language unchanged: a running frame continues in the version
it started in and holds it; every later call enters the active version
(activation_model.md section 5); a closure resolves its owner and body in the
active version when it is applied (closures.md section 6). On the hosted
route each node runs the artifact admitted for the state of the frame that
opens it.

## 5. Compiler, admission and the instruction table

### 5.1 Compiler and descriptors

Extend the unified compiler's node mode and the descriptors for the five
kinds. The descriptor stays free of lowering decisions; validation learns the
instructions `QUOTE`, `FUNCTION`, `ACTIVATE` and `TRIAL`, including that
activation targets are link targets of the node and of its owner.

The compiler source changes, so the seed manifest is regenerated and checked
(`seed_cli --write`); the seed roots do not change. Route-A dependencies in
`shear/examples/vm.py` are updated only if the compiler's helper functions
change.

### 5.2 One instruction table

**Provisional:**

This follows the owner's direction for this task. A new module,
`shear/instructions.py`, holds `INSTRUCTIONS`: a plain dict with one entry
per instruction that lowering emits. That is the host machine's dispatch
less its internal `CATCH_OK` and `RETURN`. Each entry records at least:

| Field | Meaning |
| --- | --- |
| `operands` | the number of operands |
| `children` | positions of operands that name a code child of the node |
| `linked` | positions of operands that are link targets of the node and its owner: an entity, a tuple of entities, or none when the link did not resolve (`TRIAL`'s call target) |
| `names` | positions of operands that must be strings |
| `counted` | the role whose item count an operand gives (`CALL`, `APPLY`, `MKTUPLE`), if any |
| stack effect | values taken and left. Taken is fixed, or given by operands: a count, or the length of a tuple operand. `QUOTE` takes its count; `ACTIVATE` takes one per entry; `TRIAL` takes one per entry plus its argument count. |
| `handover`, `raises` | whether the instruction hands over control (`GOTO`, `BRANCH`, `LETBIND`), and whether it raises (`FAIL`, `RAISE`) |

The test-pinned names are `operands`, `children` and `linked`. Execute
names the rest.

- `hosted_bootstrap/validation.py` reads its instruction facts from the
  table when it validates, instead of keeping its own. A test deletes an
  entry and expects a well-formed chunk to be refused.
- `shear/examples/vm.py` reads operand positions from it where its generator
  already encodes them, and only there. Review checks this by inspection.
- Tests check the table against the machine's dispatch, against the entity
  operands of every chunk `bytecode.lower` produces for the corpus and the
  operation witnesses, and against the VM's instruction set.

The table is metadata. Execution semantics stay separate per route, so the
VM remains an independent oracle (D3). `shear/instructions.py` is not one of
the golden API modules, and no golden API module gains a public name.

### 5.3 The SHEAR-written VM

Unchanged apart from section 5.2. Its missing instructions are follow-up
issue #115: `FUNCTION`, `QUOTE`, `CATCH`, `RAISE` and `FAIL` could be
interpreted with existing language operations; `READ`, `WRITE`, `CODE`,
`LINKS`, `ACTIVATE` and `TRIAL` need their target chosen by value in
interpreted code, which needs a new language operation (vm_in_shear.md
section 8).

## 6. Test-facing interface

`HostedSession` remains the boundary. Additions are **Provisional** names that
the Plan-owned tests use:

- `run(entry, *args, may_activate=False)` handles program-driven `activate`
  and `trial` as section 3 says.
- `retained_versions()` returns the frozenset of the target runtime's
  `Version` objects that own an artifact set.
- `admitted(version)` returns a read-only mapping from `(EntityID,
  VersionID)` to the `Artifact` admitted in the set `version` owns: a loaded
  version's, or a running trial's version's while the trial runs. It raises
  `AdmissionRejected` for a version that owns none.
- `TraceEvent` gains `source_artifact_id`. Event kinds added:
  - `reuse` (route `host-admission`): `artifact_id` is the new admission,
    `source_artifact_id` the reused one, and `target_state_id` the state it
    is admitted for;
  - `release`: `target_state_id` is the released set's state, and `detail`
    is `"trial"` for a trial's set or `"retired"` for a version's set.

  `produce` and `admit` events of a candidate name the candidate's state.

`prepare`, `rebuild_through`, `compiler_artifacts`,
`invalidate_compiler_generation`, `produce`, `admit` and `stage_edit` keep
their task-30 meaning.

## 7. Measurements

Extend `python3 -m shear.hosted_bootstrap.diagnostics` with the live
workloads and record the results in `hosted_bootstrap.md`, by task 23's method:
named hardware, Python, operating system and revision; repeated untraced
observations with medians; peak memory in a separate traced pass; no
ratios between dissimilar workloads; D4's targets diagnostic only.

- **Update latency**, per phase: candidate construction (`define` and
  staging), compilation (with the counts of produced and reused nodes),
  admission, the switch, and the first call of the changed function; over at
  least 20 repeated valid updates and 20 rejected ones on the live image.
- **Retention**: loaded versions, retained artifact sets and artifact counts
  after each update, and peak memory over the sequence.
- **Scaling**: one small edit at three program sizes (for example 10, 100 and
  1000 functions).

Task 23, 29 and 30 measurements stay unchanged. No acceptance test checks
the numbers. Execute adds a smoke test that runs the live measurements once
with one repeat, and Review checks the recorded numbers against a rerun.

## 8. Plan-owned files

- This document and the D5 section and task-31 entry of `roadmap.md`.
- New test modules:
  - `tests/live_support.py`: the program, step tables and oracles (not a
    test module);
  - `tests/test_live_evolution.py` (corpus, live image, problem forms; lane
    `cross-boundary`);
  - `tests/test_live_artifacts.py` (candidate admission, reuse, lifetime;
    lane `cross-boundary`);
  - `tests/test_instruction_table.py` (lane `language-runtime`, beside
    `test_bytecode`).

  `live_support.py` is about 590 lines: one program and the oracles that
  read it, kept together. Its `no_host_lowering` forbids `bytecode.lower`,
  `bytecode.chunk_of` and `bytecode.lower_value` during admitted runs; the
  oracle calls `bytecode.lower` only afterwards. Its `observed_chunks` wraps
  the machine's chunk boundaries `machine._open`, `machine._open_closure`
  and `machine._child_chunk`, as task 30's tests wrap `machine._open`, so
  Execute keeps those three as the boundaries.
  `cross-boundary` is already the slowest lane. Execute records its time
  with the new modules. Splitting the lane would change
  verification_hardening.md section 12 (Decided), so it is a separate change
  if needed.
- `tests/test_hosted_bootstrap.py`: four task-30 tests encode the old
  coverage, because they use `quote` as the unsupported kind. Two are
  renamed to what they now check; the other two keep accurate names. All
  four now remove `quote` from `SUPPORTED_KINDS` (`descriptors` or `seed`)
  for the test, so each fail-closed path is still witnessed. Each says so in
  a comment.
  - `test_unsupported_operations_are_named_not_lowered` becomes
    `test_every_node_kind_is_lowered`.
  - `test_an_unsupported_node_is_recorded_and_never_lowered` becomes
    `test_a_kind_outside_the_supported_set_is_recorded_and_never_lowered`.
  - `test_a_program_error_and_a_refusal_both_exit_with_one` keeps its name.
  - `test_a_seed_needs_the_compiler_functions_and_only_lowerable_ops` keeps
    its name.
- `tests/golden_changes/GH-67.txt`: `programs/compiler`,
  `programs/bootstrap` and `programs/instrument`, which embed the compiler
  source. The checker requires each to change; a mismatch goes back to Plan.

`tests/test_hosted_corpus.py` is unchanged: its `DEFERRED` set records what
task 30 deferred, and the new module claims it.
`tests/test_bootstrap_boundary.py` is unchanged, because expanded mode and
the VM are.

Mutation: `compiler_source.py` and the changed `hosted_bootstrap` modules are
pinned mutation targets; their survivors are re-reviewed under the changed
sources in CI (workflow dispatch), as task 30 did. `shear/instructions.py`
becomes a target or gets a justified omission.

## 9. Claims Review must verify independently

1. Every chunk the machine opens for a target, including those of
   candidates, trials, old frames and closures, equals host lowering's chunk
   of its node, and is the very object admitted in the set its frame's
   version owns (a trial's version included).
   Separately, the trace gives every executed artifact an authentic chain of
   production and admission, directly or through reuse. No host lowering
   happens during any run.
2. A candidate is fully admitted before it becomes active or runs in a trial.
   A compilation failure, also one partway through a candidate, leaves the
   runtime unchanged, leaves no artifacts or holds behind, and is not
   catchable. A language rejection takes precedence over it.
3. The reuse rule is applied exactly. The produced and reused node sets of
   each activation follow section 4.3 from the two states, every reuse source
   is an artifact of the active version, a moved node is compiled again, and
   a reused chunk equals a fresh compilation.
4. Artifact sets follow version lifetime and belong to versions, not to
   `StateID`s. The versions owning sets equal the loaded versions at step
   boundaries, and two loaded versions of one state have separate sets.
   Trial sets are released on every path, including a trial of the active
   state itself. Released artifact records are reclaimed from the heap.
5. Observable behaviour (results, failures, cells, active `StateID`s and loaded
   versions) equals ordinary host execution step by step, for the corpus and
   the live image.
6. The instruction table is the emitted instruction set, validation reads it,
   and execution semantics are not shared with the VM through it.
7. Golden, seed-manifest and mutation-catalog changes are only those the
   compiler change explains.

## 10. Exclusions

Not part of task 31: lazy or tiered production (section 3.1, Open); evolving
the image's own compiler while it runs; program-driven cell migration
(changing, adding, merging or splitting cells, or converting their content,
from a running program), which no program needs yet: cells here are live
data whose content carries across activations unchanged; reuse after
host-API activations or from trial artifacts; new VM instructions (#115); a
setting for the two-version bound (roadmap, Later); native code and removing
Python.
