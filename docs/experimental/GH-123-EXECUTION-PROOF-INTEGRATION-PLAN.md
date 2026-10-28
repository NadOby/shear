# GH-123 – Minimal execution-proof production integration plan

**Status: Proposed Plan – independent Review required before Execute.**
**Branch baseline:** `task/123-complete-constraints` at `ecfecc838aefc0c3ce75bffbc0c0fd3b6f89841f`.
**Authority:** `docs/experimental/GH-123-EXECUTION-PROOF-AUTHORITY.md`, independently APPROVED after the Section 4 P2 correction.
**Task:** #123 only. The executable-region architecture in #130 is out of scope.

## 1. Decision and stopping conditions

Implement the smallest **generic** authenticated execution-proof facility in the production `RestrictedExecutor` path that preserves all Task 32 and GH-123 frozen observations. Retain the existing per-expression bytecode and original machine/runtime. No test-harness interception, alternate evaluator, new semantic operation or native backend is production authority.

This is **not** an authorization to implement immediately. An independent reviewer must accept this Plan and its unresolved regression-test handling first.

A passing implementation means unchanged frozen semantic/security tests and the existing runtime integration pass. Only then is it eligible for the statistically qualified resource battery. Failure to reach the 1,000× ceiling does not authorize weakening authority or acceptance; report the negative or inconclusive result and a measured discriminator.

## 2. Existing boundaries that must not move

- `RestrictedExecutor.deploy` authenticates compiler production **and** host admission, validating artifact identity, owner, state/version and chunk structure.
- `restricted_policy.preflight` validates source and **emitted** instructions across the entire statically reachable call graph, including dead branches, before VM entry.
- `machine.run` continues using the **same evaluator runtime** with `may_activate=False`; one proof belongs to one active evaluator-runtime `Version` object.
- Actual VM-opened chunks satisfy `chunk is deployment.artifacts[(node, version)].chunk`. Private copies from earlier experiments cannot serve as the final executable view.
- Wrong issuer, substituted `_artifacts` binding at *any* key, stale deployment/version, bad policy, invalidated artifact set or producing generation reject under existing requirements. Restoring temporarily substituted authentic bindings permits another invocation, subject to remaining checks. Explicit invalidation is irreversible.
- Named evaluator replacement pins the current constrained-target admission operation, while subsequent operations select the replacement. D5 constrained-target old-frame retention does not authorize evaluator-runtime activation.
- Definition/code openings and resumed SHEAR segments check applicable live authority; error provenance, rollback, `READ`, External callback order and budgets remain unchanged.

## 3. Proposed production components

| Component | Location / role | Contract |
| --- | --- | --- |
| Proof issuance | Generic `RestrictedExecutor` | Run genuine issuer/deployment authentication and full transitive preflight once for each distinct authorization; construct an independently authenticated reference; publish atomically relative to revocation. |
| Proof key | Issuer-owned cache | Deployment *identity*, current evaluator `Version` *identity*, entry `EntityID`, exact effect policy; no sharing by normalized constraint, `StateID`, equal artifact contents or registry name alone. |
| Immutable proof reference | Host-private authority | Authorized `(node, VersionID)` keys, owner, authenticated artifact and original chunk identities, canonical function definitions, link/metadata dependencies, provenance and generation reference. It cannot depend on untrusted mutable decoded memos. |
| Invocation validator | `RestrictedExecutor.run` | Check live issuance, deployment/target/version/generation, current complete `_artifacts` key set and artifact-object identities; check any `_chunks` bindings consumed by the implementation; reject mismatches before `machine.run`. Do not permanently revoke for temporary binding mismatches. |
| Pinned resolver | Existing `machine` resolver hooks | Open original admitted chunk objects and proof-bound definitions only; check approved owner/version, live lifetime and policy on function-definition and code-node openings; reject without host lowering. |
| Revocation and retention | Executor/Version ownership | Serialize issuance/publication with explicit invalidation; prevent stale proof reuse and release proofs with their last legitimate owner. No value in a `WeakKeyDictionary` may strongly retain its own weak deployment key indefinitely. |
| Trace/operation provenance | Executor/registry | Use proof-authenticated entry/root/artifact and operation-scoped target metadata; no fresh unauthenticated `_definition` lookup may establish a proof-backed trace. Preserve distinct host failures and semantic verdicts. |

### Binding-validation choice

**Initial conservative candidate:** compare the complete authenticated `_artifacts` mapping against the issuer's reference on every invocation, including all keys and exact `Artifact` object identities. Comparing the full `_chunks` table is allowed but **not mandatory** when unused entries are not consumed. If `_chunks` is consumed, validate the relevant binding(s). Also validate authentic `artifact.chunk` object identity and any independently mutable consumed metadata, or establish trusted sealed storage with equivalent coverage.

This is expected to require **O(number of admitted artifacts)** work per invocation without a reliable write barrier. The Plan makes no claim that this will meet the resource ceiling. Replacing the scan with a counter or epoch is **not acceptable** unless independent direct-dictionary-mutation witnesses remain covered. Do not recompute SHA-256 or transitive preflight at each warm call merely because the manifest comparison is required.

## 4. Integration order and gates

### Gate A – Generic proof issuance and positive path

1. Add proof ownership within the generic restricted executor, using the existing authenticate/preflight functions and same runtime, entry and effect policy.
2. Bind and verify all source/definition metadata consumed by the VM and traces, including nested callees; preserve canonical/source-memo disagreement rejection on first proof issuance.
3. Preserve original admitted chunk object identities, transitive effect restrictions and actual machine execution. Compare ordinary generic pure and `READ` cases and their execution/trace provenance with the existing runner.

**Gate:** No change in source/verdict, bytecode identity, provenance or authorized effects. No private copied chunk is executed. Stop if immutable authority cannot coexist with the published admitted objects.

### Gate B – Live binding guard, rejection and recovery

4. Implement invocation-time binding validation for **all** protected `_artifacts` keys, including one unrelated to the current execution; protect `_chunks` where consumed. Reject before VM entry.
5. Verify wrong issuer and `object.__setattr__` issuer-binding substitution. Verify authentic restoration succeeds without forcing redeployment; distinguish temporary missing compiler-generation mapping from its permanent invalidation.
6. Preserve `invalidate(deployment)`, artifact-set invalidation and producing-generation invalidation as irreversible. Serialize proof issuance and explicit withdrawal; do not revoke on a temporarily substituted binding.

**Gate:** Original GH-123 authority/cache mutation witnesses pass unchanged, together with Task 32 lifecycle forgeries. No forged or different chunk is ever executed.

### Gate C – Resolver, continuation, lifecycle, integration

7. Check live proof authority at entry, each function-definition opening, each code-node opening and each SHEAR continuation resumption. No stronger immediate commit/READ cancellation requirement is added.
8. Preserve named evaluator operation-scoped replacement, exact External ordering/budgets, read authority, language errors versus host failure, trace association and target-write/activation/trial rollback.
9. Ensure stale evaluator-runtime `Version` is rejected and proof references are reclaimed under D5 lifetime, without a cache retaining retired versions indefinitely. No evaluator-runtime activation or concurrency expansion.

**Gate:** Full unchanged Task 32 and GH-123 frozen acceptance, semantic/boundary suite, negative mutation witnesses and applicable normal CI are green. Independent code Review then evaluates security and authority equivalence.

### Gate D – Resource qualification (only after Gate C)

10. Run the existing Plan-owned comparison (`docs/constraint_functions_complete_benchmarks.md`): matched prepared/cold paths; at least three processes, warm paired blocks, stratified bootstrap intervals, median/p95 ratios, memory, preparation, 8/64/256 scaling and mechanism ledger.
11. Report the cost of required invocation-time binding validation separately. If the 1,000× median or p95 ceiling is exceeded, do **not** bypass a frozen guard: classify the failure and return a narrowly scoped optimization/design choice for owner review.

**Gate:** Resource-qualified positive, qualified negative or explicit inconclusive outcome. The 107-workload, eight-sample experiment remains exploratory evidence only.

## 5. Pre-existing non-frozen regression conflict – explicit Plan decision

`tests/test_constraint_functions_preparation_cache.py::test_authenticated_runner_and_preflight_on_cache_hits` explicitly asserts that `restricted.preflight` is **called once on every cached evaluation**. This is a non-frozen observation of the old algorithm, not a requirement stated by the approved execution-proof contract; the approved design instead requires proof at issuance and current live authorization at invocation/openings.

An implementation that skips repeated preflight will fail that existing test even when it preserves frozen behavior. **Do not silently change or work around the assertion just to get CI green.** Before Execute, independently review and authorize one of:

- **Recommended:** update this *non-frozen* regression together with implementation to assert full first-issuance preflight, genuine authenticated VM openings and live fail-closed checks on every cache hit, with direct-mutation and recovery witnesses unchanged. Record the change and its rationale; do not touch frozen tests.
- Keep the existing per-invocation preflight call and accept its cost; separately determine whether that meets the resource objective.

No test modification is authorized by this proposed Plan until the owner accepts the regression contract decision. The reviewer should explicitly assess the recommendation before implementation.

## 6. Implementation constraints

- Keep the public `RestrictedExecutor.deploy/run/invalidate/registry` contracts and the existing compiler/artifact/VM boundaries.
- No new per-constraint semantic dispatch, no Python incumbent fallback, no interpreter written in the host to replace the SHEAR evaluator.
- No weakening or changes to `tests/constraint_functions_*acceptance.py`, Task 32 frozen tests, Task 24 oracles or 17 boundary cases.
- Do not treat valid artifact hashes as production/admission authority, or a historical set of good bindings as license to ignore current ones.
- Preserve root causes of `AdmissionRejected` and other host failures rather than coercing failures into semantic `Unknown`.
- No function/basic-block fusion, JIT/native backend, general security redesign or modification of issue #130 in this work.

## 7. Required independent Plan review

Return **APPROVE / CONDITIONAL / REJECT**, with exact conflicting source/test citations. Specifically verify:

1. The proof, manifest and same-object resolution can coexist under the actual `ArtifactSet` and `machine` APIs.
2. Backing validation covers unrelated-key substitutions without imposing independent checking of every unused `_chunks` entry.
3. Temporary substitution recovery and permanent invalidation remain distinct.
4. Every proof consumer, including registry trace and continuation resumption, uses authenticated source/provenance metadata.
5. Version ownership, publication/revocation ordering and cache retention are feasible without unapproved evaluator-runtime evolution.
6. The **non-frozen preflight-on-cache-hit test conflict** is resolved by an explicit acceptable decision, not hidden by a semantic change or test gaming.
7. Acceptance and performance gates follow the approved contract and existing Plan; no frozen test or resource ceiling is redefined.

After independent approval and the owner decision on the non-frozen regression, Execute may make a bounded generic implementation change. No benchmark result or production correctness is claimed by this planning document.
