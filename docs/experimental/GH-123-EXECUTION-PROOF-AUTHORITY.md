# GH-123 – Authenticated execution-proof authority contract

**Status: Provisional – revised after independent CONDITIONAL review. Not approved for production integration.**  
**Basis:** `task/123-complete-constraints` at `0ca4630100de010f871cddea9acc709ef37f8a43`.  
**Scope:** GH-123 proof caching with existing expression-node artifacts. Executable-region design belongs to #130.

## 1. Decision and precedence

**Provisional:** Prefer an authenticated, immutable execution reference (Option B) over redoing unchanged production/admission proofs at every invocation. The reference does **not** replace required live authority checks. In particular, GH-123 frozen witnesses require rejection when protected backing bindings are substituted at invocation, even if authentic code survives in a snapshot.

**Decided by existing specifications and tests:** Task 32 requires genuine compiler-production and admission authority, pinned runtime execution, complete transitive source-and-instruction effect preflight (including dead branches), authentic artifact identity, failure provenance and fail-closed invalidation. GH-123 adds observable backing-binding rejection and recovery. Neither specification nor frozen tests are amended by this proposal.

A genuine detached snapshot may make some *unprotected, superseded* storage irrelevant, but a binding directly challenged by GH-123 acceptance cannot be reclassified as irrelevant simply because a proof exists. The current `RestrictedExecutor.run` remains the production authority until a reviewed replacement passes unchanged tests.

## 2. Proof scope and pinned evaluator version

A proof is owned by one issuing `RestrictedExecutor` and binds exactly:

- Issued `RestrictedDeployment` identity and its issuer's issuance record.
- The evaluator runtime's **one active `Version` object** and its exact source `StateID`; entry function `EntityID` and authenticated definition/version.
- The producing compiler generation, its live authority and genuine production/admission evidence.
- One exact `RestrictionPolicy` including the allowed-effect set.
- The fully preflighted transitive function and expression-node set, with owner, `EntityID`, `VersionID`, admitted artifact identity and emitted instructions.
- An immutable authenticated reference for executed chunks, source definitions, dependency/link metadata and provenance used by proof consumers.
- Proof lifetime, explicit revocation and required issuer/version binding checks.

A matching `StateID`, constraint normalization key, content hash or cached result is not sufficient authority. Proofs cannot cross issuers, deployments, entries, effect policies or evaluator-runtime `Version` objects.

**Bounded scope:** The evaluator runtime is stable during GH-123 restricted execution (`may_activate=False`). Activation inside the evaluator runtime, concurrent evaluator activation and transferable proofs are not introduced. Evolution of the **constrained target runtime** is a distinct D5 operation and retains its existing behavior. Named evaluator replacement is a separate operation-scoped registry change; it is not evaluator-runtime activation.

## 3. Issuance, publication, object identity and source authority

The following are a single serialized authority transition relative to managed invalidation: verify the issuer/deployment and producing generation; authenticate source and admitted artifacts; perform complete source-and-emitted-instruction preflight; construct the trusted reference; revalidate any bindings that could have changed during preparation; then publish the proof. A failed step publishes no grant. Explicit revocation cannot race with publication to leave a usable stale proof. A lock, generation token, transactional swap or equivalent mechanism may implement this; no internal state machine is prescribed.

The reference must bind all metadata consumed by preflight, VM execution, definition resolution, dependency checking and provenance/traces. Function definitions must be reconstructed or checked against canonical source; mutable `Value._definition` and relation memos cannot independently create authority. Before fresh proof issuance, an inconsistent decoded definition must reject before VM entry. After issuance, only metadata actually transferred into the authoritative reference may be treated as obsolete; no consumer may silently fall back to a changed memo or live unproved definition.

**Unchanged chunk-identity witness:** Every VM-opened chunk must satisfy:

`chunk is deployment.artifacts[(node, version)].chunk`

Equality of bytes, hashes or copied tuples does not meet the witness. The production view and VM resolver must use the **same published admitted chunk objects**, while the issuer retains an independently authenticated record of their authorized contents and identity. Private chunk copies in the live-admission and definition-snapshot experiments do not satisfy this condition. A design may publish sealed objects at admission or establish an equivalent safe authoritative view, but cannot revise the frozen witness.

An outer `tuple`, frozen dataclass or `MappingProxyType` does not by itself prove that nested execution/source data cannot change. The design must either protect the consumed data against the supported mutations or validate it against independently authenticated contents where the contract requires detection. Forged self-consistently rehashed artifacts gain no producer/admitter authority.

## 4. Mandatory invocation-time backing validation and recovery

**Frozen behavioral invariants:**

1. If protected artifact or chunk bindings are substituted when an invocation checks them, raise `AdmissionRejected` **before VM entry**. An authentic immutable snapshot does not authorize execution through a currently substituted protected binding.
2. After authentic bindings are restored, execution must be permitted again **subject to every other admission check**. This does not guarantee any particular semantic verdict.
3. Explicit deployment invalidation permanently withdraws authority from that deployment. Restoring backing bindings cannot revive it.
4. Explicit invalidation of a producing compiler generation permanently withdraws authority dependent on that invalidated generation. Reintroducing a mapping entry cannot revive the invalidated generation.

These are observable requirements, **not** a prescribed three-state machine. A substitution reversed entirely between invocations need not be detected historically. Rejection caused solely by a temporary binding substitution is not irreversible revocation. Recovery may compare restored bindings to an existing immutable authenticated reference; it need not recompile, redeploy or repeat proof obligations already proven unchanged. An implementation may retain/revalidate a proof or discard and reissue one.

**Protected binding set, as exercised by existing frozen tests:**

- The issuing executor's record for the exact deployment; deployment `_owner`, `_session`, `_target`, `_artifact_set`, `artifacts`, `source_state_id` and `compiler_generation`, and the associated target/session/active-version bindings.
- The admitted artifact set's current `_artifacts` and `_chunks` mappings, **including bindings not opened by this particular evaluation**; their key sets, authenticated artifact object identities and corresponding exact chunk identities.
- The published `deployment.artifacts[(entity, version)]` bindings and each artifact's bound owner, node/version, source identity, producing generation, authenticated ID and genuine chunk contents.
- The selected evaluator-runtime `Version` identity, artifact-set validity, producing generation object and its validity, plus the canonical source/definition bindings actually relied on for executing or reporting the proof.

This list specifies required observables, not a demand to detect every arbitrary privileged Python write. In particular, the frozen GH-123 cache witness substitutes an **arbitrary** `store._artifacts` entry, not necessarily a reachable execution node. Checking only the entry chunk or proof-reachable chunks is insufficient. The authority witness also substitutes both `_artifacts[key]` and `_chunks[key]`; checking only one table is insufficient as a general contract.

**Concrete conservative mechanism proposed for initial implementation:** retain a private authenticated reference manifest at issuance. Before each invocation, verify the issuer and live lifecycle bindings and compare the entire protected `_artifacts`/`_chunks` key sets and per-key object identities with that reference, including `artifact.chunk is expected_chunk` and authenticated metadata needed to prevent in-place changes of an admitted record from escaping. Recheck any independently mutable consumed source metadata at its required boundary or protect it in the published authoritative representation. A mismatch refuses before VM entry; a restored exact binding permits fresh validation against the same reference. The mechanism does **not** have to repeat full compilation, SHA-256 verification of unchanged artifacts or transitive preflight on every invocation.

Without a reliable write barrier or protected storage, direct Python dictionary mutations cannot generally be detected by an O(1) epoch check. The conservative comparison is O(number of protected bindings) per invocation. Its performance is **unmeasured** and may fail the GH-123 resource limit. A faster design may replace it only by proving equivalent coverage of the actual frozen mutations, not by assuming all writers use cooperative APIs. The existing runner remains the fallback if equivalence or performance cannot be established.

## 5. Invocation, opening and continuation boundaries

A proof and its issuer/lifetime checks must be valid at each invocation entry. Current protected-binding substitution must reject there, before `machine.run` or any other VM entry. Live authority and pinned-version checks also apply at **function-definition openings**, **code-node openings** and **External continuation resumption** before resumed SHEAR execution. Reusing a proof does not exempt a new invocation or resumed continuation from required live checks.

If explicit invalidation occurs between relevant openings, the next required opening rejects before executing further unproved code; a fresh invocation rejects before VM entry. The contract does **not** add mandatory checks before every `READ`, immediately before target commit, after the last opening or between every Python opcode. It does not promise rollback of a callback's independently performed external side effects; existing target-runtime failure/rollback semantics remain binding.

All restrictions remain in force on code executed from an already issued proof: no unproved static/dynamic dispatch, forbidden effects, alternate lowering, incumbent Python constraint fallback, or exception-to-verdict coercion. Trace/error provenance must identify the actual admitted node/version, evaluator entry, producing generation, artifact ID, constrained target operation and relevant failure source.

## 6. Replacement, evolution, irreversible invalidation and reclamation

| Event | Required behavior |
| --- | --- |
| Named evaluator registry replacement | Current target admission operation retains its originally selected deployment; next operation selects the replacement. No retroactive revalidation. Replacement alone is not proof revocation. |
| Constrained target runtime activation | Preserve existing D5 target version/hold/old-frame rules. Do not transfer evaluator proofs or change evaluator selection mid-operation. |
| Evaluator runtime active-Version change | Existing restricted invocation rejects stale-version use; no old-evaluator-version continuation extension is authorized. One proof binds one stable evaluator `Version`. |
| Temporary issuer/deployment/backing binding substitution | Refuse if observed at required check; restoring authentic bindings allows revalidation and resumed eligibility, absent another failure. |
| Explicit deployment or artifact-set invalidation | Permanently withdraw the deployment's execution authority; no recovery through restored bindings or replacement registry entries. |
| Producing compiler-generation invalidation | Permanently withdraw dependent authority; a temporarily missing but valid chain mapping is not equivalent to irreversible `invalidate()`. |
| New entry, policy or issuer | Require distinct authorization; do not reinterpret an existing proof. |
| Failed issuance/preparation | Publish nothing; preserve existing admitted state and failure provenance. |
| Retired evaluator Version / no remaining legitimate owner | Release associated proofs/artifacts with existing D5 retention and hold semantics; cache keys must not indefinitely retain retired versions or obsolete deployments. |

Proof publication, explicit withdrawal and reclamation must have defined ordering so a revoked or reclaimed reference cannot be newly used. No new concurrency semantics, stronger mid-instruction cancellation or generalized concurrent evaluator activation is implied.

## 7. Worked behavioral witnesses

**Authentic execution:** Genuine produce/admit events and full transitive source/bytecode preflight establish proof authority. The invoked runner checks current protected mappings; the real VM opens the same published admitted chunk objects and uses authenticated definitions and provenance.

**Forged binding, then recovery:** A validly rehashed replacement is placed under an original `_artifacts` key, with the corresponding `_chunks` substitution. An invocation raises `AdmissionRejected` before VM entry even though the private proof still holds authentic code. Restoring both bindings permits another invocation, subject to remaining checks. A substitution removed between invocations need not create a historical taint.

**Cached unrelated-key substitution:** An arbitrary current `_artifacts` key is replaced by `object()` on a cache hit. The current invocation rejects before VM entry. Restoring the original entry permits evaluation again. Proof-reachable-only validation does not satisfy this witness.

**Issuer-binding substitution:** `object.__setattr__(deployment, '_session', other)` rejects before VM entry; restoring the authentic session permits execution again subject to other checks. Reflection resistance is required for this named binding, not asserted for all privileged Python mutations.

**Irreversible invalidation:** Explicit deployment `invalidate()` or producing-generation `invalidate()` permanently withdraws the dependent authority, independently of backing-store restoration. A different valid deployment remains usable.

**Source definition poisoning:** Before fresh preflight, a decoded definition inconsistent with canonical source rejects. A previously issued proof may use authenticated definition data only where all execution/provenance consumers are bound to it; a poisoned current authoritative dependency cannot be ignored.

**Operation-scoped replacement:** The named evaluator switches from A to B during a target admission operation. That operation keeps A; the next operation uses B. Neither canonical constraint identity nor target state identity changes solely because of registry replacement.

**Stale evaluator Version:** A proof issued for evaluator `Version` V cannot be reused after that evaluator runtime's active version becomes V2. D5 old-frame continuation for the *constrained target* does not authorize this extension.

**Dead-branch forbidden effect:** An authenticated, structurally valid `WRITE` concealed in a dead branch under the read policy rejects before VM entry. No execution proof or snapshot bypasses transitive effect preflight.

**External continuation:** On each resumed SHEAR segment, applicable authority is revalidated. No callback is replayed, reordered or silently converted to `Unknown`; existing exact budget, subject and failure behavior is preserved.

## 8. Production gates and stop rule

1. Fresh independent Review accepts the explicit rejection/restoration/permanent-invalidation contract, protected-binding coverage, stable evaluator Version, publication/revocation ordering, chunk identity and provenance obligations.
2. Production proof ownership remains in the generic `RestrictedExecutor` path. No constraint-specific second interpreter or test-only monkeypatch becomes production authority.
3. Unchanged Task 32/GH-123 frozen witnesses pass: wrong issuer, validly rehashed substitution, arbitrary cache-hit binding replacement, restored authentic bindings, compiler generation/deployment invalidation, actual chunk object identity, decoded-definition preflight, forbidden dead effects and read authority.
4. Existing semantic/boundary/admission/continuation/rollback/failure-provenance acceptance remains unchanged and passes.
5. Only after correctness/security acceptance, use the Plan-owned statistically qualified cold/warm/resource benchmark. The 107-workload exploratory result cannot establish resource acceptance, especially if invocation-time binding validation adds O(number of artifacts) work.

**Stop rule:** If direct backing-map mutation cannot be detected without prohibitive cost under the applicable frozen contract, do not substitute an O(1) guard for the required comparison. Do not weaken tests or claim production approval. Retain the current runner or return to a separately approved architecture decision.

## 9. Separation and next action

This contract changes no execution granularity; authenticated function/basic-block regions, specialization and native/JIT work remain in #130. The representation of internal proof states and the means of reissuing/retaining proofs are intentionally open.

**Next:** Submit this revision alone for independent adversarial re-review. No production integration, new benchmark, frozen-test edit or Task 32 Plan amendment is authorized by this document.
