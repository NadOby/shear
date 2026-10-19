# Handoff

## Current state

- Issue: #119 – Task 32, restricted execution and SHEAR-defined constraints.
- Branch: `task/32-restricted-execution`.
- Role: independent Execute re-Review APPROVED; editorial Publish preparation.
- Baseline `main`: `d50297cd44db26135bc0b3f9f95e4326c832beb9`.
- Original frozen Plan: `819848a849c4a15da29232c911fa36c24b57bd40`.
- First revised Plan: `d7261cdd568ae55a85714b12f5659c7cb7a5f0d2`.
- Approved second frozen Plan content head: `1cf3f22f1767a3d3b001b86f27381b6cfb41d9e2`.
- Pre-Execute handoff: `77982141161b28cade0bb8f15b3296e37b0fbff1`.
- Independently approved implementation head: `e26430c4630655a6cb2a4aa714b00d26bf53199c`.
- Independent Execute re-Review: APPROVE, with P2/P3 editorial publication findings.
- No PR opened and no merge at this checkpoint.

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

The revised Plan was independently approved for Execute. Its frozen
technical acceptance and the Task 24 semantic/golden controls were not
changed by Execute. No golden-record changes were authorized. Plan-owned
documentation needs editorial status reconciliation before Publish.

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
7. `98648878`, `0ba555a7`, `8ee78a89` – failed evaluator
   provenance, fault-aware tracing and descriptor-authentication tests.
8. `60b8f538`, `77d1dbb9`, `2df978ba` – mutation-target
   registration and mutation-catalog validation fixes.
9. `fed24acc`, `8ebaed1a`, `0af3a5f4` – selectable mutation
   targets through campaign selection, runner and CI.
10. `d47ed1f` – removed unintended workflow modifications.
11. `04714465` – restored optional `mutation_shards` input.
12. `5170b125` – authority, provenance, lifecycle and deployment
    mutation-regression tests.
13. `efc89b0` – independent restricted-policy and boundary regressions.
14. `e26430c` – final two adversarial mutation guards.

Other Execute checkpoint commits: `0fe99f7` recorded the initial handoff.
All post-Review changes above preceded the accepted Execute re-Review.

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

**Accepted bounded result: positive integration feasibility.**
The independent Execute re-Review approved the implementation at
`e26430c`; no P0 or P1 production defects were identified.

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

## CI evidence and mutation disposition

The branch was verified at reviewed implementation head
`e26430c4630655a6cb2a4aa714b00d26bf53199c`.

- Final ordinary push CI:
  https://github.com/NadOby/shear/actions/runs/39176163229
  – passed all eight test lanes, the Task 24 probes and golden comparison.
- Final full targeted mutation campaign:
  https://github.com/NadOby/shear/actions/runs/39176488935
  – passed; `mutation_count=9999`, batch `0`, seed `1`,
  16 shards and exactly the two new restricted-execution modules.
- All 200 selected mutations were killed. Zero unclassified survivors,
  timeouts, resource kills, abnormal exits or unexecuted mutations.
- Discovery campaign:
  https://github.com/NadOby/shear/actions/runs/39166568100
  – 169 killed, 31 unclassified survivors.
- After two consolidated regression-test commits:
  https://github.com/NadOby/shear/actions/runs/39174412544
  – 198 killed, two survivors.
- Final two targeted rejection-boundary tests at `e26430c` killed
  both remaining mutations. This establishes 100% kill of this
  engine's current 200-site selected catalog, not universal correctness.
- The new restricted modules are both registered mutation targets;
  target selection and optional shard count are available in CI.
- Existing source-pinned classified-survivor rules were not relaxed.
  Issue #107's general repin-after-merge problem remains a separate
  open workflow concern; this Task 32 targeted campaign is not a claim
  that issue #107 is closed.

The independent Execute re-Review was read-only and returned **APPROVE**
for the bounded milestone; it accepted some implementation-coupled
mutation assertions as P3 without requiring further changes.

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
- The follow-up for complete constraint semantics, including
  canonical-content inspection and resource budgeting, is #123.
- Broader planning guidance for decisive experiments is #124.

The new restricted modules are mutation targets. Regression coverage
now directly challenges copied deployment authority, rehashed artifacts,
absent decoded executable nodes and malformed definition bodies.
Some tests intentionally assert structural invariants such as dataclass
immutability and `may_activate=False`; those are not independent proofs
of end-to-end isolation.

Do not silently broaden the reviewed implementation or frozen tests.
Any substantive post-Review change requires new independent Review.

## Independent Execute re-Review disposition

Reviewed branch: `task/32-restricted-execution`.
Reviewed implementation head: `e26430c4630655a6cb2a4aa714b00d26bf53199c`.
Baseline: `d50297cd44db26135bc0b3f9f95e4326c832beb9`.
Approved frozen Plan: `1cf3f22f1767a3d3b001b86f27381b6cfb41d9e2`.

**Verdict: APPROVE – Execute.** Genuine SHEAR compilation and machine
execution, independent source/chunk effect checking, authenticated
artifact authority, operation-scoped selection, negative admissions,
rollback, provenance and complete current mutation coverage passed.

No P0 or P1 production defects were identified. Outstanding
publication-only findings:

- P2 – refresh this handoff with actual review and CI evidence.
- P2 – update the obsolete Plan Review/Execute authorization status
  in `docs/restricted_execution.md`, strictly editorially.
- P3 – correct historical Task 24 and Task 31 roadmap statuses;
  mark Task 32 as implemented pending Publish until merged.
- P3 – some mutation tests are implementation-coupled; accepted
  without further work.

Keep the reviewed technical contract, tests, production behavior,
mutation-pinned evidence and Task 24 golden records unchanged.

## Next action

Publish preparation only:

1. Reconcile the obsolete workflow-status text in
   `docs/restricted_execution.md` without changing its frozen contract.
2. Reconcile historical statuses for Tasks 24 and 31 and branch status
   for Task 32 in `docs/roadmap.md`.
3. Append the bounded Task 32 outcome, evidence, retained mechanisms
   and follow-ups to `CHANGES.md`.
4. Inspect the complete publication-only diff against `e26430c`;
   verify applicable CI and open the PR. Do not merge before final checks.

Follow-up issues: #123 (full constraints semantics) and #124
(decisive experiments/planning). Both are open and separately scoped.
No additional production changes or full mutation rerun are required
by the approved review. Any substantive change requires fresh Review.

The longer-term architecture question remains open: extending ordinary
SHEAR functions to cover full constraint semantics depends on a
separately planned generic-content and resource-budget experiment
against the unchanged Task 24 oracles.
