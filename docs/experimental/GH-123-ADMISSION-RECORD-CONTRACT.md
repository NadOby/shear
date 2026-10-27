# GH-123 – Revocable admission record and Task 32 threat-boundary decision

Pinned review basis: branch `task/123-complete-constraints`, `9afd0ca9c3dd0b4fd64ba6b72b7fe44b60af8123` (the latest reviewed commit for this design). This document is **an experimental hypothesis and scope ledger**, not a Plan amendment or permission to weaken frozen acceptance.

## 1. What Task 32 actually requires

The normative text in `docs/restricted_execution.md` §5 requires a valid pinned executable deployment, an immutable admitted-artifact view **for the invocation**, proof of source and emitted effects including transitive dead branches, genuine producer/admitter evidence, fail-closed pinned resolution, and no execution of unproven code or forbidden effects. §D–E requires rejection of unauthenticated self-consistently rehashed artifacts and invalidated/stale deployments. It does not explicitly require the executor to detect arbitrary reflective Python mutations to obsolete objects that are no longer part of the authoritative admitted view.

Importantly, `tests/test_restricted_execution_lifecycle.py` (`test_rehashed_forgery_cannot_gain_restricted_execution_authority`) explicitly recognizes a **detached immutable deployment snapshot** as an acceptable outcome: after a forged replacement in the original `ArtifactSet`, either execution refuses **or** execution proceeds with the **original authenticated chunk**, as independently observed. When the deployment's actual authenticated artifact is the forged object, it must refuse. The distinction is *what is authorized and actually opened*, not necessarily the mutability of every old private backing collection.

However, the current `RestrictedExecutor.run` checks `_issued`, all authenticated artifact identities and hashes, then performs full preflight and resolver checks. Therefore its current observable behavior **does** reject certain private mutations. Frozen tests also exercise direct mutation of decoded `Value._definition` as a preflight discriminator. A new optimized public execution path must pass the unchanged acceptance suite and independent negative tests; we cannot simply assume that a behavioral difference is permissible.

## 2. Threat boundary and two possible contracts

**A – strict live-object rejection parity.** Every attempted change to any admitted artifact, memoized definition or backing map must be discovered before VM entry, even when only an old non-authoritative object changed. An O(1) guard over mutable, independently writable Python objects cannot generally achieve this absent a complete write barrier, trusted native isolation, or per-run reinspection. An `epoch` checked at run time detects only mutations that increment it. Retaining per-run scans remains a viable baseline.

**B – authoritative immutable-snapshot semantics.** The authentic compiler-produced and admitted program is copied/frozen at an explicit authority transition; VM resolution exclusively opens those pinned bytes and source identities. Mutations of a superseded collection cannot alter the authoritative admitted snapshot and cannot authorize forged code. Explicit issuer withdrawal, generation invalidation, version retirement, deployment invalidation, policy changes and switching the selected evaluator revoke or invalidate the grant. This reading has support in the existing lifecycle test, but still needs independent Task 32 contract review. In particular, replacing a currently authoritative binding must not silently leave a still-usable credential for the old binding.

**Do not silently substitute A for B or B for A.** Before production integration, specify the authoritative object, its lifetime, permitted host mutation surface, and exact behavior when old backing state is altered. The tests' allowance for a detached snapshot does **not** itself establish that the present experimental `_SealedSnapshot` meets Task 32.

## 3. Experimental admission record

`tests/constraint_functions_admission_record_experiment.py` wraps the existing experimental detached `_SealedSnapshot`. Issuance happens only after the previous prototype performs the real `RestrictedExecutor._check_deployment`, full `preflight` on original source and admitted chunks, and preflight again on a detached canonical copy. This experiment adds a grant identity, monotonic issuer epoch, explicit revocation, managed artifact/definition replacement, and existing constant-time lifetime checks.

**Managed adversaries:** a foreign grant, explicit revocation, registered artifact replacement, registered function-definition replacement, native artifact-set invalidation, compiler generation invalidation, issuer rebinding, and unrelated-replacement isolation. Each must refuse before the detached VM wrapper is invoked. Authentic unmodified execution must match the original evaluator.

**Untracked adversaries (full suite):** raw `_artifacts` replacement with valid rehash, `object.__setattr__` alteration of an admitted artifact's chunk, and `object.__setattr__` poisoning of decoded `_definition`. The current executor refuses; the detached prototype can continue to execute authentic copied code. The script records this as **strict current-runner rejection-parity divergence**, with genuine authorization of forged code **not** observed. Classification under contract B remains explicitly unqualified.

The prototype's epoch is not a general Python write barrier, its objects are not physically immutable against reflective mutation, it uses a separate runtime and lacks Task 32 trace/admission integration, and it is currently pure-only without live External callbacks. It does not establish production acceptance or resource performance.

## 4. Required evidence for production design B

1. Demonstrate producer **and** admission authority for each exact admitted chunk, including nested owner/version identity; no issuer can forge an executable replacement by rehashing.
2. Demonstrate detached executable **and source graph** cannot share mutably writable storage with any untrusted caller. Avoid mutable cached decoded definitions; copying `Value.content` once is not enough if a privileged host can then mutate the new private snapshot.
3. Bind grant to `(issuer, target active Version identity, compiler generation, entry, exact effect policy, authenticated snapshot)`. Selection changes must retire the previous grant at the defined operation boundary, with correct in-flight retention.
4. Prove revocation for failure, retirement, generation invalidation, invalidated artifact set and replacement. No execution or observable target-state mutation after refusal; no host-lowering fallback.
5. Preserve transitive effect preflight and per-node defense in depth, precise Error/External propagation, execution trace/provenance, continuation budgets, and existing legitimate `read` authority.
6. Run unchanged Task 32/GH-123 security and frozen acceptance, then targeted mutation adversaries. Run the complete mutation campaign and full resource battery only after architecture freeze.

**Decision rule:** If a genuinely immutable authoritative snapshot and revocation interface cannot be enforced under the supported host threat model, do **not** accept an O(1) proof cache. Optimize non-cached verification instead. Even if design B becomes formally acceptable, the 1,000× resource ceiling needs separate end-to-end measurements.
