# Handoff

## Current state

- Issue: #119 – Task 32, restricted execution and SHEAR-defined constraints.
- Branch: `task/32-restricted-execution`.
- Role: Execute implementation complete; independent Execute Review required.
- Baseline `main`: `d50297cd44db26135bc0b3f9f95e4326c832beb9`.
- Original frozen Plan: `819848a849c4a15da29232c911fa36c24b57bd40`.
- First revised Plan: `d7261cdd568ae55a85714b12f5659c7cb7a5f0d2`.
- Approved second frozen Plan content head: `1cf3f22f1767a3d3b001b86f27381b6cfb41d9e2`.
- Pre-Execute handoff: `77982141161b28cade0bb8f15b3296e37b0fbff1`.
- Last verified implementation head: `7b59e76e35c9a84086c4fa33c275eefc9725cac5`.
- No PR opened, no independent Execute approval, no merge.

Read `CLAUDE.md`, the Workflow section of `docs/roadmap.md`,
issue #119, `docs/restricted_execution.md`, and the Task 24
evidence. Verify this checkpoint against the repository.

## Frozen Plan and earlier reviews

Plan-owned files:

- `docs/restricted_execution.md`.
- `docs/roadmap.md` – Task 32 entry.
- `tests/test_restricted_execution.py`.
- `tests/test_restricted_execution_boundaries.py`.
- `tests/test_restricted_execution_lifecycle.py`.
- `tests/lanes.py` – Task 32 registrations.

The initial Plan and first Resolve were rejected by independent
review. The second Resolve addressed three P1 findings:

1. Forbidden emitted-effect fixtures lacked structural validity.
2. Forgery tests confused artifact hash integrity with compiler authority.
3. Real machine observations and anti-fallback fault injection were
   missing at multiple admission boundaries.

Additional corrections addressed immutable rollback observations,
error provenance, runtime-operation trace identity, malformed links,
replacement atomicity and lifecycle evidence.

The revised Plan was independently approved for Execute.
Its acceptance, specification and Task 24 golden controls were not
modified by Execute. No golden-record changes were authorized.

## Execute changes

Commits after the pre-Execute handoff:

1. `914a7f7` – generic source and admitted-instruction policy preflight
   in `shear/hosted_bootstrap/restricted_policy.py`.
2. `128eb75` – hosted restricted deployment, authenticated artifact
   binding, pinned resolver and named evaluator adapter in
   `shear/hosted_bootstrap/restricted.py`.
3. `76042af` – operation-local registry selection and target-operation
   provenance in the restricted runner.
4. `8e77bb9` – optional operation scope for initial load, write,
   activation and trial in `shear/runtime.py`.
5. `886ed99` – executor-issued deployment identity and authority
   in the restricted runner.
6. `7b59e76` – reviewed `runtime.py` mutation-survivor source repin
   in `tests/mutation_catalog_data/shear/runtime.toml`.

All production execution remains on the existing SHEAR compiler and
host machine. No separate interpreter, Python predicate fallback,
constraint-specific bytecode VM, language-visible effect type or
new canonical constraint representation was introduced.

The generic restricted runner supports non-constraint function calls,
pure computation, static transitive calls and an explicit read policy.
Pure and read policies reject write, activation, trial, unresolved
indirect execution and unclassified instructions before execution.

Source and emitted instructions are checked separately. Authentic
compiler production, structural validity, hash integrity, correct
node/version ownership, artifact-set identity and invocation policy
remain distinct trust requirements.

Named `External` still uses its existing semantic identity. The
host deployment is separate metadata. Its evaluator result adapter
accepts only the exact strings `satisfied`, `violated` and `unknown`.

The runtime scopes all checks belonging to one admission operation
to the same evaluator selection. An in-flight replacement does not
change that selection. Explicit invalidation fails closed.

## Bounded Execute outcome

**Provisional classification: positive integration feasibility,
pending independent Review.**

The frozen acceptance suite now executes successfully, including:

- Pure non-constraint functions and permitted static transitive calls.
- Genuine SHEAR-defined evaluators at initial cell and relation admission.
- Accepting and rejecting writes, including relation-sensitive writes.
- Activation and trial checks over staged target content.
- Independent machine-opening and admitted-chunk observations.
- Fault injection against hidden evaluator fallback.
- Structurally valid but policy-forbidden emitted `WRITE`.
- Rehashed unauthorized artifacts at their authentic lookup keys.
- Incorrect provenance, malformed links and indirect-call rejection.
- Operation provenance, runtime rollback and failure atomicity.
- Host-error origin, exact arity and result-conversion semantics.
- Deployment replacement, in-flight holds, cleanup and invalidation.

Passing these checks demonstrates the bounded milestone, not complete
replacement of the incumbent constraint evaluator or superiority of
the new architecture.

## CI evidence

Successful push run:

- https://github.com/NadOby/shear/actions/runs/39153659410
- Tested commit: `7b59e76e35c9a84086c4fa33c275eefc9725cac5`.
- Eight ordinary test lanes passed: core-model, language-runtime,
  transform-continuity, syntax-reconcile, compiler-self-hosting,
  vm-bootstrap, cross-boundary and mutation.
- Task 24 experimental probes and golden comparison also passed.
- Earlier failures at `76042af` involved replacement and trace
  semantics; they were corrected by `8e77bb9`.
- Earlier failures at `8e77bb9` and `886ed99` were the stale runtime
  mutation-source pin; the corrected pin passed at `7b59e76`.

**Outstanding CI evidence:** the push run skipped the heavyweight
mutation campaign. Because the survivor catalog changed, issue #107
requires a branch-head campaign that actually revalidates the reviewed
survivors before Publish. Do not infer that evidence from ordinary
mutation catalog tests.

Use the `Semantic model` workflow on this branch with
`mutation_count=1` and `mutation_revalidate=true`. Inspect the
mutation-plan revalidation message, campaign outcome and evidence
artifacts. Resolve any classified-survivor failures before Publish.

## Mechanism accounting

The counting unit is one independently enforced semantic or
execution rule, not one class, wrapper or source file.

| Mechanism | Disposition | Evidence and interpretation |
| --- | --- | --- |
| M1 – dedicated constraint dispatch | Retained | `constraints.py` still evaluates canonical constraint nodes; ordinary SHEAR handles only deployed `External` function bodies |
| M2 – constraint-node budget | Retained | Existing `constraints.py` evaluation budget remains operative; no generic instruction fuel was introduced |
| M3 – named external authority | Retained and extended | Existing `External._check` and `EvaluationContext.externals` dispatch remain; restricted registry adds deployment selection |
| M4 – escaping host failure | Reused unchanged | Existing host-failure separation in `constraints.py` and `machine.py` remains responsible for uncatchable evaluator failures |
| N1 – canonical identity | Reused unchanged | Canonical constraints exclude deployment metadata |
| N2 – three-valued semantics | Retained | Existing strong-Kleene evaluation remains; the new adapter converts only exact result strings |
| N3 – runtime admission | Extended | Existing atomic checks and staging remain; `runtime.py` adds an optional generic operation scope |
| N4 – relation subjects | Reused unchanged | Existing role-map and owned-subtree subject construction remains authoritative |
| N5 – state and version identity | Reused unchanged | `StateID` and `VersionID` remain independent of evaluator deployment and execution |

Existing generic functions, bytecode, compiler generations, admitted
artifact sets, machine frames and version holds are reused.

New fixed rules requiring separate accounting:

1. Generic source-and-instruction effect classification with
   transitive call preflight – `restricted_policy.py`.
2. Authenticated restricted deployment issuance, artifact binding,
   invocation resolution and invalidation – `restricted.py`.
3. Operation-local evaluator-selection consistency – `restricted.py`
   and the optional generic boundary in `runtime.py`.
4. Exact constraint-result transport conversion – `restricted.py`.

Runtime provenance tracing observes these mechanisms; a trace label
is not itself execution authority or independent evidence of execution.

No M-series mechanism is claimed removed. No net mechanism savings
are claimed or required by Task 32.

## Known limitations and review questions

These are limitations or unresolved questions, not established
implementation defects:

- The full Task 24 B/C replacement and its 17 boundary cases have
  not been implemented through ordinary SHEAR functions.
- Generic canonical-content introspection and generic computation
  budgeting remain deferred.
- Dynamic dispatch and executable reflection remain conservatively
  disallowed.
- Evaluator deployments are prepared in independent source states.
  Evaluator self-bootstrap within an unadmitted target state remains
  unresolved.
- No performance acceptance or sustained throughput measurement
  was established for repeated policy preflight.
- The new restricted modules are not mutation campaign targets in
  the current `tests/mutation_catalog.py` target inventory.
- The issued-descriptor guard added at `886ed99` is not directly
  challenged by the frozen acceptance suite using copied deployment
  dataclasses. A targeted regression test would strengthen coverage.

Do not broaden the frozen tests silently. The owner is open to
late-stage tightening for a demonstrated gap; any substantive
acceptance revision needs explicit review and a newly frozen contract.

## Independent Execute Review

Review the repository at the actual branch head, against
`d50297c` and frozen Plan head `1cf3f22`. Do not trust this handoff
as independent evidence.

Prioritize:

1. Full implementation diff and unchanged Plan-owned acceptance.
2. Genuine SHEAR compilation and machine execution without fallback.
3. Both source and admitted-bytecode effect proof, including
   unclassified and transitive operations.
4. Artifact production authority versus content-hash integrity,
   authentic lookup keys, rehashed substitution and invalidation.
5. Executor-issued deployment descriptor identity and replacement.
6. Target versus evaluator source provenance and operation tracing.
7. Admission-operation atomicity, evaluator selection and D5 ordering.
8. Holds, artifact lifetimes, failed preparation and cleanup.
9. Exact error/result boundaries and Task 24 oracle preservation.
10. Mechanism accounting, architectural limits and untested assumptions.
11. Mutation survivor revalidation under issue #107.

Classify findings P0–P3 with exact locations and counterexamples.
Give an explicit APPROVE or REVISE verdict. Independent Review is
read-only. Any substantive fix requires another independent Review.

## Next action

Complete issue #107's branch-head mutation revalidation, then request
fresh independent Task 32 Execute Review. If approved, Publish may
prepare the PR and update roadmap/change metadata, preserving the
reviewed implementation and acceptance contract.

The longer-term architecture question remains open: extending ordinary
SHEAR functions to cover full constraint semantics depends on a
separately planned generic-content and resource-budget experiment
against the unchanged Task 24 oracles.
