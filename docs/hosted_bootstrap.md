# Hosted Bootstrap Implementation

**Status: implemented** (roadmap.md task 30, issue #66). The contract is
[`hosted_pipeline.md`](hosted_pipeline.md), written by Plan and not changed
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
| `seed.py`, `manifest.json` | The generation-0 seed: the compiler nodes the host lowers, derived from the source and checked in. `SeedGate` is the only door to host lowering. |
| `generations.py` | Builds generations 1 to 3, each by running `compile_node` on the machine over the previous generation's admitted artifacts. |
| `descriptors.py` | Builds the argument of `compile_node` for a node and decodes the answer. Makes no lowering decision. |
| `validation.py` | Structural admission checks on a chunk: known instructions and operand types, children and links of the node and its owner, and a single pass over the operand stack (no underflow, empty at a handover, nothing after a handover or raise, exactly one result). No host re-lowering. |
| `artifacts.py` | Admitted artifacts, content-derived ids and the per-run chunk resolver. |
| `target.py` | One target state: produce, admit, run. Opaque evidence handles bind an admission to one compiler run. |
| `session.py`, `command.py` | The public boundary (`HostedSession`) and the documented command. |
| `trace.py`, `errors.py` | Provenance events; `AdmissionRejected`, which is not a program error. |
| `diagnostics.py` | Section 10 measurements. |

`machine.run` takes an optional `resolver`, scoped to the run by a context
variable. When given, every chunk the machine opens comes from it; without
one, behaviour is unchanged. A resolver failure is not a `LanguageError`, so
a program cannot `catch` it.

## 2. Operation coverage

The SHEAR compiler lowers every input-form operation of `operations.py`
except `activate`, `function`, `quote`, `trial` and `unquote`, plus `catch`,
`raise` and the host's `invalid` node. A node of another kind is recorded as
a `reject` event when the target is prepared, and running it fails closed
with `AdmissionRejected`; nothing falls back to host lowering. The 20
included corpus programs run on the admitted route; the deferred programs
are outside this task's subset (hosted_pipeline.md section 2).

`tests/test_hosted_bootstrap.py` also runs `applyv` and `linksof`, which the
corpus subset lacks, on admitted artifacts against ordinary execution, and
compares the compiler's chunk with
`bytecode.lower` for every supported node of every corpus program.

## 3. Provisional integration choices

**Provisional:**

These were chosen to satisfy the contract and are open to Review.

- The descriptor is `(operands, (state_id, node, version, owner))`. Children
  and call targets are entity ids; link names are replaced by their targets.
- The operand of `LIT` stays in canonical form, as a node's payload does in
  host lowering. Other identities and tuples are decoded to plain values.
- Any change of the active state makes every artifact stale. A caller must
  `prepare` again; reuse across activations is Task 31.
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

## 5. Mutation decisions

`compiler_source.py` and the `hosted_bootstrap` modules are mutation
targets, except `__init__.py`, `__main__.py`, `errors.py` and
`diagnostics.py`, whose omissions are justified in
`tests/mutation_catalog.py`. The Task 29 spike and its test are removed.
Because the seed manifest pins the compiler source, any change to
`compiler_source.py` fails the manifest check at once; behavioural coverage
of the compiler is the differential test and the self-hosting suite.
