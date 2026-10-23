# Hosted Bootstrap Boundary

**Status: provisional operation inventory; D3 and D4 decided.** Roadmap
task 28, issue #64. This document records the current operation support
boundary and inventories Python host services relevant to hosted
bootstrap. Task 28 did not decide D3 or D4. D3 was subsequently
decided by task 29 (PR #91); D4 was decided by the owner on
2026-10-10 (issue #92, roadmap.md).

Baseline: `main` at `081ba0d0882e9c02906a3f6a4081f77d2907e897`.

## 1. Scope and terminology

The four routes are:

1. Host lowering: graph-form nodes lowered by `shear.bytecode.lower`.
2. Host execution: those chunks executed by `shear.machine`.
3. SHEAR lowering: input-form expressions compiled by the SHEAR
   program `lower` in `shear/examples/compiler_source.py`.
4. SHEAR-VM execution: expanded chunks interpreted by the SHEAR
   program `vm` in `shear/examples/vm.py`.

The fourth route is itself executed on the Python-hosted machine.
The execution columns identify the interpreter implementing an
instruction, not the absence of Python.

For the SHEAR-VM column, support means that the expanded instruction
sequence for the operation is implemented by the interpreter. It does
not mean that a complete valid source expression can necessarily be
compiled and executed through both SHEAR routes. In particular,
`unquote` has instruction-level support for `GOTO`, although valid
source `unquote` occurs only inside `quote`, which the VM lacks.

Status definitions:

- **S – Supported:** the relevant lowering or instruction route
  implements the operation for its valid inputs at the defined level.
- **R – Rejected:** the operation denotes invalid code and fails
  intentionally; lowering may produce an explicit failure instruction.
- **D – Deferred:** the route does not implement the intended operation.
  Its current behavior must fail explicitly instead of succeeding through
  an undeclared alternative execution route.

The matrix describes current code, not the post-task-30 target subset
or proof of an end-to-end bootstrap.

The matrix describes expanded mode (`lower(e)`), the route A compiler. Since
task 31 the node-mode compiler (`compile_node`, route B) also lowers `quote`,
`unquote`, `function`, `activate` and `trial`, so node mode covers every
kind (hosted_bootstrap.md section 2); the rows below are unchanged.

## 2. Operation support matrix

**Provisional:**

These classifications describe current implementation behavior.
Every row corresponds to exactly one operation in
`shear.operations.OPERATIONS`.

| Operation | Host lower | Host run | SHEAR lower | SHEAR VM |
| --- | --- | --- | --- | --- |
| `lit` | S | S | S | S |
| `arg` | S | S | S | S |
| `add` | S | S | S | S |
| `sub` | S | S | S | S |
| `mul` | S | S | S | S |
| `lt` | S | S | S | S |
| `eq` | S | S | S | S |
| `if` | S | S | S | S |
| `seq` | S | S | S | S |
| `call` | S | S | S | S |
| `read` | S | S | S | D |
| `write` | S | S | S | D |
| `quote` | S | S | D | D |
| `unquote` | S | S | D | S |
| `function` | S | S | D | D |
| `closure` | S | S | S | S |
| `activate` | S | S | D | D |
| `trial` | S | S | D | D |
| `tuple` | S | S | S | S |
| `inspect` | S | S | S | S |
| `record` | S | S | S | S |
| `len` | S | S | S | S |
| `item` | S | S | S | S |
| `slice` | S | S | S | S |
| `concat` | S | S | S | S |
| `let` | S | S | S | S |
| `catch` | S | S | S | D |
| `raise` | S | S | S | D |
| `ref` | S | S | S | S |
| `code` | S | S | S | D |
| `linksof` | S | S | S | D |
| `apply` | S | S | S | S |
| `applyv` | S | S | S | S |
| `invalid` | R | R | R | R |

`label` is an input form, not an operation in `OPERATIONS`.
SHEAR lowering recognizes it transparently.

### 2.1 Implementation evidence and limitations

Host lowering is implemented by `bytecode.lower`, including
`_lower_activation`. Host execution dispatches in `machine._execute`.
An `invalid` node lowers to `RAISE` and raises a language error when
executed.

SHEAR lowering's supported subset is
`self_hosting.LOWERED - {"label"}`. All other operation names,
including `invalid`, currently produce
`(("RAISE", "unknown operation"), ("END",))`.
This explicitly fails, but does not distinguish rejected from
deferred operations in its diagnostic.

The SHEAR VM recognizes instructions from `vm._ORDER`, implemented
through `vm._cases` and `vm._run_body`. Unsupported instructions
reach `vm_trap`, rather than being run by the host instruction
dispatcher.

Host lowering of `unquote` produces `GOTO`, which the SHEAR VM
implements. That instruction-level S does not imply support for
a complete quote/unquote expression.

`CALL` uses a linked function through host `applyv`. The VM's
`APPLY` and `APPLYV` cases also delegate when the VM callable is a
reference; a VM closure instead enters `vm_run`. Consequently,
instruction coverage does not prove that all reached program code
is interpreted, or that its chunks were SHEAR-compiled.
Task 29 evaluated bounded execution-route witnesses; complete
transitive provenance remains a task-30 requirement.

### 2.2 Existing invariants and bootstrap scope

The semantic graph remains canonical and bytecode remains derived.
The existing identity, continuity, activation, runtime-cell and
execution contracts are specified in `state_model.md`,
`identity_model.md`, `continuity_inference.md`,
`activation_model.md`, and `bytecode.md`. Task 28 does not
redefine or amend them.

**Provisional:**

The intended hosted-bootstrap boundary distinguishes permitted
host services, fixed interpreter machinery, seed compilation,
SHEAR compilation, and executed program code. Unsupported routes
must fail explicitly, not silently switch execution engines.

Task 28 tests the immediate lowering results and interpreter traps.
It does not establish complete producer provenance or the absence
of host compilation anywhere in the transitive execution graph.
That requirement is an explicit task-30 acceptance condition.

## 3. Host-service inventory

**Provisional inventory; D4 allowances decided in section 5.**

This is the historical Task 28 inventory and its original proposed
allowances. The table preserves the proposals and observations as
recorded; section 5 supplies the subsequent D4 authorization and
restrictions. Each row states its contract, implementation, proposed
use, reported rebuild observation, and existing verification references.

"Observed" refers to a reviewer's trace of rebuild generations
1 and 2. The trace was reported in review rather than committed
as a repository artifact. To reproduce the lowering observations,
create a fresh `Runtime(load(program(vm.bootstrap_entities())))`,
spy on `bytecode.lower_value` while forwarding to the original
function, and invoke
`run(runtime, vm.SWAP_ALL, may_activate=True)` twice.
Record the `relation_of(value).kind` supplied to each lowering call,
excluding runtime initialization from the recording window.

This observes host lowering of uncached graph nodes, not every
executed instruction or cached chunk. Other service observations
require separate instrumentation. "Yes" and "No" apply only to
the profiled rebuild; "Partial" and "Unverified" preserve uncertainty.

"Allow" is a proposed Python-hosted service. "Conditional"
requires a D4 allowance or Task 30's admitted-execution boundary,
as applicable. Host-lowered program wrappers are reported as current
behavior, not approved bootstrap fallback.

| Service | Contract | Implementation | Proposed use | Rebuild observed | Tests |
| --- | --- | --- | --- | --- | --- |
| Lexing and parsing | Convert source text to input forms; reject malformed input | `syntax/lexer.py`, `syntax/parser.py` | Allow | No | `test_syntax.py`, `test_syntax_units.py` |
| Source reconciliation | Resolve source edits into transformations | `reconcile.py` | Allow | No | `test_reconcile.py` |
| Graph construction and links | Validate forms and construct owned graph code | `lang.load`, `_Builder`, `relations.py` | Allow | Yes | `test_graph_form.py`, `test_lang.py` |
| Definition and transformations | Produce candidate states without mutating sources | `lang.define`, `transforms.py` | Allow | Yes | `test_node_edits.py`, `test_transforms.py` |
| Continuity inference | Preserve identities only where matching justifies them | `matching.py`, `lang.define` | Allow | Yes | `test_continuity_inference.py`, `test_continuity_corpus.py` |
| Immutable semantic state | Store values and derive content-based state identity | `state.py`, `values.py` | Allow | Yes | `test_state.py`, `test_state_identity_cost.py` |
| Entity and version identity | Distinguish semantic identity from value equality | `identity.py`, `values.py` | Allow | Yes | `test_identity.py` |
| Canonicalization | Normalize values and provide stable representations | `canonical.py`, `relations.py` | Allow | Yes | `test_canonical.py`, `test_relations.py` |
| Ownership | Preserve graph ownership and owned-subtree integrity | `ownership.py`, `state.py` | Allow | Yes | `test_ownership.py`, `test_ownership_lifetime.py` |
| Host lowering and chunk cache | Produce derived chunks from graph nodes | `bytecode.py` | Conditional; seed and oracle, not undeclared fallback | Yes, including wrappers | `test_bytecode.py`, `test_rebuild.py` |
| SHEAR compiler | Produce expanded chunks as data | `examples/compiler_source.py`, `machine.py` | Required; execution through admission under D3 | Yes | `test_self_hosting.py`, `test_rebuild.py` |
| SHEAR VM | Interpret its declared instruction subset | `examples/vm.py` | Reference/alternative under D3 | Yes | `test_vm.py`, `test_rebuild.py` |
| Host machine | Run derived instructions and provide runtime execution | `machine.py` | Seed and fixed machinery; authenticated artifact admission under D3, integrated by task 30 | Yes | `test_bytecode.py`, `test_vm.py` |
| Code reflection | Return code for a function in the selected state | `machine.py`, `lang.function_at` | Allow | Yes: 16 host-lowered `code` nodes; `function_at` also used | `test_self_hosting.py` |
| Link reflection | Resolve a function's link table | `machine.py`, `lang.py` | Allow | Yes: 4 host-lowered `linksof` nodes | `test_vm.py` |
| Data and callable operations | Provide primitives, tuples, comparisons and linked calls | `machine.py`, `canonical.py` | Allow | Yes | `test_data_ops.py`, `test_vm.py` |
| Cells and constraints | Read and write runtime content; enforce declared constraints | `cells.py`, `runtime.py`, `constraints.py` | Allow | Partial: `cells_of` used; constraint evaluation not observed | `test_cells.py`, `test_constraints.py` |
| Activation | Stage, check and atomically select a candidate | `Runtime.activate`, `lang.define` | Allow | Yes: two activations reported | `test_activation.py`, `test_metaprogramming.py` |
| Trials | Run a candidate in isolated runtime state | `Runtime.trial`, `machine.py` | Allow | No | `test_trial_runs.py`, `test_language_trials.py` |
| Version lifetime | Manage frames, holds and retirement | `Runtime`, `Version`, `Frame`, `Hold` | Allow | Yes | `test_lifecycle.py`, `test_activation.py` |
| Runtime errors | Surface language, program, runtime and limit errors | `machine.py`, `lang.py` | Allow | Unverified separately | `test_error_handling.py`, `test_error_values.py` |

### 3.1 Current rebuild versus required hosted pipeline

The reported rebuild profile includes `define`, matching,
activation, version holds and retirement, `cells_of`,
`function_at`, and semantic model services. The host-lowering
trace also reports 16 `code` nodes and 4 `linksof` nodes
across two successive `swap_all` runs.

The review did not observe source parsing, reconciliation,
trials, constraint evaluation, or `read`, `write`, `catch`
and `raise` execution. Absence in this profile is not
proof that these operations are unnecessary for D4.

The host also lowers the wrappers for `evals`, `lower`, `upper`,
and the `generation` function during generation 2, in addition
to the interpreter's own functions. These per-function wrappers
are program code, not automatically exempt fixed machinery under
task 30. The current rebuild therefore must not be described as
already meeting the task-30 no-host-lowering requirement.

Source parsing and reconciliation are prospective dependencies
of task 30. Trial and live-evolution services are prospective
dependencies of task 31. An absent call in the present rebuild
does not establish that a service can be removed from D4.

The reported service observations need independent verification
before being treated as complete execution-provenance evidence.
The selected-route measurements and their limits remain in
`content_baseline.md`.

Python allocation, hashing, memory management and operating-system
services remain part of this hosted model. Python-independent
execution is a separate future milestone.

## 4. Acceptance contract for task 28

**Provisional:**

The Plan-owned acceptance module is
`tests/test_bootstrap_boundary.py`, registered in `tests/lanes.py`.

1. The matrix has exactly one row for each operation in
   `OPERATIONS`, including `invalid`, and the input-only `label`
   is excluded.
2. Host lowering dispatch covers the operation set. Real graph
   witnesses yield chunks ending in `END` whose instructions
   are recognized by the host dispatcher.
3. SHEAR lowering coverage agrees with
   `self_hosting.LOWERED - {"label"}`. Supported examples
   structurally agree with expanded host chunks.
4. SHEAR-VM support is classified from the interpreter's actual
   instruction cases and order. A supported `LIT` example
   executes successfully; this is not an execution witness
   for every supported opcode.
5. Deferred SHEAR lowering produces the explicit
   `RAISE "unknown operation"` result. The test checks that
   result, not global absence of Python host fallback.
6. Unsupported SHEAR-VM instructions reach `vm_trap`.
   An observable replacement trap and the ordinary failing
   trap verify the route independently of the host opcode
   dispatcher.
7. The invalid graph-form witness lowers to `RAISE`
   and host execution reports its specific unknown-operation
   error. SHEAR lowering currently gives `invalid` the same
   generic error chunk as deferred operations.
8. Each inventory row identifies a contract, implementation,
   allowance, reported use and test reference. The automated
   check verifies structure and the existence of named test
   modules; it does not verify that each implementation
   reference is a real symbol or that every proposed service
   is exercised by those tests.

The existing `tests/test_rebuild.py` separately checks that
generations 2 and 3 do not request host `chunk_of` for the
retained compiler source twins. Its instrumentation does not
cover all host-lowered wrappers or transitive execution.

`CALL`, `APPLY` and `APPLYV` delegation is recorded in section
2.1 as a current limitation. Task 29 evaluated bounded
execution-route witnesses; complete transitive routing and
producer-provenance verification belong to Task 30.

Preserve existing compiler, VM, corpus, continuity and golden
records. No golden-record changes are intended for issue #64.

## 5. Scope and decision gates

Task 28 records the matrix, its acceptance tests and the host
inventory. It does not implement additional instructions or
change production semantics.

**D3 – Decided** (roadmap task 29, PR #91): Route B is the primary
hosted execution path. The host may execute authenticated SHEAR-compiled
per-node derived artifacts through fail-closed internal admission with
node/version binding and observed compiler provenance. The SHEAR VM is
retained as an alternative and independent correctness reference.
The detailed admission implementation belongs to Task 30. Neither
arbitrary program-supplied bytecode nor silent host-lowering fallback
is permitted on the hosted path.

**D4 – Decided** (owner, 2026-10-10; issue #92):

- **Staged workload.** Task 30 demonstrates canonical-source-preserving
  compiler generations 1–3 on admitted route B and a precisely declared
  non-evolution corpus subset. Task 31 completes the self-modification
  and error canaries and sustained live evolution. The SHEAR compiler
  and SHEAR VM may continue evolving during task 31, without mandatory
  VM feature parity.
- **Replaceable host services.** Python may provide the semantic and
  runtime services enumerated in section 3, including canonicalization,
  parsing, reconciliation, `define`, continuity inference, identity,
  ownership, reflection, cells, constraints, trial, activation, errors
  and lifetime management. Their interfaces must be explicit and
  replaceable. Minimizing the Python host kernel is an incremental
  long-term direction, not a task-30 or task-31 completion gate.
- **Compilation boundary.** Python may prepare node descriptors and
  decode compiler results generically. Only a finite, documented seed
  and its dependencies may undergo host lowering. Subsequently,
  program code executes exclusively as authenticated
  SHEAR-compiler-produced artifacts through D3 admission. No silent
  host compilation, Python-generated substitute instructions,
  executable wrapper exemptions or program-supplied bytecode
  authority. Fixed interpreter machinery and the seed are separately
  identified. Producer evidence covers transitive execution.
- **Derived IR and identities.** Reuse provisional per-node host
  bytecode as shared executable IR, with explicit child `EntityID`s,
  version-pinned compiler inputs and trusted node/version, compiler
  generation and dependency provenance. `code` keeps the current
  active-version view. Artifact reuse requires compatible node
  versions and dependencies; invalidation is established in task 30,
  while activation, holds and retirement are tested in task 31.
  Exact IR encoding, admission adapters and cache layout remain
  provisional.
- **Independent verification.** Compiler-produced chunks must agree
  with independently specified behavior. Existing host lowering is
  a differential oracle used in tests only, not an admission verifier
  or hidden execution fallback. Share actual compiler/IR and runtime
  implementation where practical without making correctness tests
  self-referential.
- **Soft budgets.** On recorded hardware, initial diagnostic targets
  are at most 10 s per compiler rebuild generation and 50 ms from a
  small edit through admitted preparation and activation; aspirational
  targets are 1 s and 10 ms respectively. Neither target gates
  acceptance. Record comparable workloads, separate phase timings,
  cold/warm conditions and repeated untraced observations. Task 23
  and Task 29 observations remain historical evidence, not proof
  that route B meets these targets.

The stage boundary requires Task 30 Plan to enumerate precisely which
corpus cases are included and deferred. Host-orchestrated compiler
rebuilding does not satisfy task 31's program-driven live evolution.
Because the staged workload differs from Task 29's originally
recommended full workload, the selected route must be validated on
the actual task-30 workload, and again for task 31's live-evolution
workload. Reconsider D3 only if comparable evidence undermines it.

The D3 and D4 decisions and their acceptance boundaries are recorded
in roadmap.md. This document does not supersede them.

Task 29 evaluated the execution-route alternatives. Task 30 owns
the integrated hosted pipeline, source-preserving rebuilding, and
complete provenance for its declared workload. Task 31 completes
live evolution and remaining corpus coverage. The operation matrix
does not authorize any undeclared fallback.

## 6. Independent review targets

Independently verify the operation classifications, especially
`invalid`, `unquote`, the deferred instructions, and the
instruction-level meaning of VM support.

Check that tests distinguish declared behavior from untested
claims, that malformed witnesses are not mistaken for operation
support, and that error paths fail explicitly.

Inspect `CALL`, `APPLY` and `APPLYV` delegation and reported
host-lowered wrappers when assessing the selected route B and
the D4 host-service boundary. The service-use observations must
not be promoted to complete producer-provenance evidence
without an independent trace.

Compare the Plan-owned specification and acceptance tests with
the revised Plan baseline before accepting subsequent changes.

The matrix and inventory remain historical inputs to D4 and
task 29, not evidence that hosted bootstrap is complete.
