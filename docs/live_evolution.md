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

`tests/test_live_evolution.py` holds a program in text syntax version 0
(`IMAGE`) and drives it as a persistent image. It:

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
- moves nodes to another function with a program-driven activation (`move`).

The trial-rejection kind `depth_limit` is covered by `safe_install`.

### 2.3 Operation coverage

The SHEAR compiler's node mode lowers every graph-form node kind:
`descriptors.SUPPORTED_KINDS` equals `lang.NODE_KINDS`. The five kinds task
30 left out are `quote`, `unquote`, `function`, `activate` and `trial`. Their
host lowering in `bytecode.lower` is the specification of the chunk, and the
existing differential test (`CompilerAgreesWithHostLowering`) covers them
through the corpus.

**Provisional:**

Expanded mode (`lower(e)`) keeps lowering the five to the `RAISE` it
emits today. Expanded chunks feed only route A, whose VM cannot
run these instructions (section 5.3). `docs/bootstrap.md`'s matrix keeps
describing expanded mode and gains a note that node mode covers every kind.

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

A candidate that is rejected by the language before compilation keeps its
existing failure: a missing activation capability, a malformed definition,
a constraint or a two-version-bound rejection is raised as today, and no
compilation is attempted for it.

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

At every step boundary, the states with an artifact set (`retained_states()`)
are exactly the states of the runtime's loaded versions. During a run they
include at least those. A released set leaves nothing in the session that
keeps its artifact records alive; chunks shared through reuse stay alive as
long as some retained artifact uses them. The trace is intentionally retained
history and keeps identifiers only.

### 4.2 Trials

A trial's candidate gets its own artifact set, admitted before the trial runs
and released when the trial returns or fails. It is never used for the
parent runtime's states and never reused afterwards (**Provisional**: an
activation of the same candidate compiles again relative to the active
version).

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
shared, not copied.

Why this is dependency-safe: a chunk is a function of its node's content and
the compiler alone. Children, call and apply targets, cells and closure
bodies appear in it by `EntityID` and are resolved when they run, each to its
own artifact in the frame's state (continuity_corpus.md, `extract_function`:
"a chunk depends only on its node"). Admission additionally checks the
node's and its owner's links, so rule 2 recompiles a moved node, and rule 4
re-checks links in D. Nothing is inferred from a `VersionID` alone.

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

The owner's direction for this task. A new module
`shear/instructions.py` holds `INSTRUCTIONS`, one entry per instruction
that lowering emits (the host machine's dispatch less its internal
`CATCH_OK` and `RETURN`), with at least the operand count `operands`.
Execute decides the other facts it records (child operands, linked
operand, stack effect).

- `hosted_bootstrap/validation.py` reads its instruction facts from the
  table instead of keeping its own.
- `shear/examples/vm.py` reads operand positions from it where its generator
  already encodes them, and only there.
- Tests check the table against the machine's dispatch, against every chunk
  `bytecode.lower` produces for the corpus, and against the VM's instruction
  set.

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
- `retained_states()` returns the frozenset of `StateID`s that currently own
  an artifact set.
- `admitted(state_id)` returns a read-only mapping from `(EntityID,
  VersionID)` to the `Artifact` admitted for that state, and raises
  `AdmissionRejected` for a state that is not retained.
- `TraceEvent` gains `source_artifact_id`. Event kinds added: `reuse` (route
  `host-admission`; `artifact_id` is the new admission, `source_artifact_id`
  the reused one, `target_state_id` the state it is admitted for) and
  `release` (`target_state_id` the released state). `produce` and `admit`
  events of a candidate name the candidate's state.

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

Task 23, 29 and 30 measurements stay unchanged.

## 8. Plan-owned files

- This document and the D5 section and task-31 entry of `roadmap.md`.
- `tests/test_live_evolution.py`, new, lane `cross-boundary`.
- `tests/test_hosted_bootstrap.py`, two task-30 tests that encode the old
  coverage, renamed to what they now check:
  - `test_unsupported_operations_are_named_not_lowered` becomes
    `test_every_node_kind_is_lowered`.
  - `test_an_unsupported_node_is_recorded_and_never_lowered` becomes
    `test_a_kind_outside_the_supported_set_is_recorded_and_never_lowered`.
    It removes `quote` from `SUPPORTED_KINDS` for the test, so the
    fail-closed path is still witnessed.
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

1. Every executed program-code artifact, including those of candidates,
   trials, old frames and closures, has an authentic chain of production and
   admission, directly or through reuse, and no host lowering happens during
   any run.
2. A candidate is fully admitted before it becomes active or runs in a trial;
   a compilation failure leaves the runtime unchanged and is not catchable.
3. The reuse rule is applied exactly: the produced and reused node sets of
   each activation follow section 4.3 from the two states, a moved node is
   compiled again, and a reused chunk equals a fresh compilation.
4. Artifact sets follow version lifetime: retained states equal loaded
   versions at step boundaries, trial sets are released, and released
   artifact records are reclaimed.
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
