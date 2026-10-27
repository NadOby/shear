# GH-123 – Authenticated execution-proof authority contract

**Status: Provisional proposal for independent Review, not a Task 32 amendment.**
**Basis:** `task/123-complete-constraints` at `e03dae1b3ff3db9665f6477a9601b8438346c8d1`.
**Scope:** GH-123 proof caching only. General executable-region fusion belongs to #130.

## 1. Decision proposed

Prefer **B: authoritative immutable-snapshot semantics** to **A: strict mutation-detection parity for every superseded Python backing object**, but only if the unchanged Task 32 and GH-123 acceptance requirements can be met.

Task 32 requires an immutable admitted-artifact view for an invocation, compiler production **and** host admission, whole-reachable-graph effect preflight (including dead branches), pinned execution, failure provenance and fail-closed revocation. It does not require checking an object that has ceased to be an execution authority merely because Python code can still refer to that object.

This is a proposed interpretation, not permission to change existing tests, security behavior or the public restricted-runner interface. The current runner remains authoritative until independent Review approves a concrete implementation.

## 2. What the proof authorizes

An issued proof is a host-owned capability for exactly:

- One issuing `RestrictedExecutor` and its issued deployment identity.
- One pinned runtime **Version object**, source `StateID`, entry `EntityID` and function-definition version.
- One compiler generation and its authentic producer/admitter evidence.
- One exact `RestrictionPolicy` (including the effect allowlist), not a subset chosen later.
- The complete transitive allowed function/code-node set, with owner and `VersionID` for each node.
- An immutable executable chunk view and canonical function-definition view for those nodes.
- A revocation/lifetime state owned by the issuer, not reconstructed from a caller-provided hash.

Source and admitted bytecode are both checked before proof issuance. Structural validation, artifact integrity, genuine production/admission events and source/bytecode effect restrictions are distinct obligations. Unknown code, indirect dispatch, forged reuse ancestry and unauthorized effects reject before VM entry.

A proof's hash or cached result alone never establishes its authority. Proof caching must not be keyed only by `StateID`, normalized constraint or semantic equality: these do not identify an issuer, an active runtime version, a policy or the lifetime of an admitted deployment.

## 3. Authority transition and object identity

Issuance must define the exact transition at which the authenticated execution snapshot becomes authoritative. The VM may obtain executable chunks and definitions **only** from that snapshot, in the same pinned runtime; it may not fall back to source decoding, host lowering or the current mutable artifact mapping.

**Frozen acceptance constraint:** `tests/constraint_functions_complete_acceptance.py::candidate_execution_guard` and Task 32 witnesses require each VM-opened chunk to be the **same Python object** as `deployment.artifacts[(node, version)].chunk`. The current experiment privately copies chunks, so it does not meet this witness. Production design must make the published authenticated deployment view and the VM execution view identical at the tested boundary. Do not rewrite the witness to compare chunk equality instead.

The implementation must also prove that chunk contents, decoded definitions and nested metadata used by the VM are stable for the invocation. `MappingProxyType`, frozen dataclasses and tuple outer containers are insufficient evidence by themselves if inner objects remain writable by an untrusted actor. The source graph and any derived definition must be version-bound; `Value._definition` is a mutable memo, not a fresh authority.

**Open:** Whether to publish sealed chunk objects during `deploy()` or establish an equivalent protected authoritative view before the first invocation. Neither design is approved by this document. It must preserve the existing artifact provenance and object-identity witnesses.

## 4. Replacement, revocation and retention

| Event | Proposed rule |
| --- | --- |
| New invocation with valid matching grant | Use the pinned proof; live issuer/lifetime checks remain mandatory. |
| Normal named-evaluator registry replacement | Existing operation finishes on its pinned selection; the next operation selects the replacement. No retroactive revalidation. |
| New semantic version / successful activation | Old frames may finish on a retained old version under D5; fresh calls obey existing active-version selection. No implicit grant transfer. |
| Explicit `invalidate(deployment)` or artifact-set invalidation | Reject new invocations before VM entry; in-flight execution fails closed at its next required authority safe point. Do not redirect to a replacement. |
| Producing compiler-generation invalidation or issuer withdrawal | Revoke dependent grants and reject at the same boundaries. |
| Policy change, entry change or deployment identity change | A distinct proof is required; never silently reuse the old one. |
| Failed candidate preparation, preflight or proof issuance | Publish no grant, leave existing admitted runtime state unchanged and preserve failure provenance. |
| Replacement of a superseded, non-authoritative backing map | Cannot authorize forged execution. Continuing with independently pinned genuine code may be acceptable only after Review confirms all frozen tests. |
| Mutation of still-authoritative code or definition | Must not execute altered code. Reject or make the mutation impossible within the declared threat model. |

**Safe-point requirement:** a live grant must be checked at entry and at the existing code-node/function-opening boundaries at minimum, until a separately reviewed contract permits coarser checks. An invalidation between openings must be observed before the next opening. Do not claim immediate interruption of a Python opcode already executing.

Ordinary replacement is *not* revocation. Explicit invalidation *is* revocation. In-flight retention does not grant immunity from explicit invalidation.

## 5. Threat model and limits

Untrusted SHEAR code and caller-supplied constraint data must not be able to obtain or modify the issuer's proof, its executable storage, runtime-version binding, effect policy or revocation state.

Arbitrary privileged Python reflection (`object.__setattr__`, rewriting private dictionaries, monkeypatching trusted methods) can defeat ordinary Python immutability. Two possible host threat models must not be conflated:

- **Trusted-host model:** privileged reflective mutation of the *authoritative* issuer/proof is outside the adversary model. Public and SHEAR-visible operations still fail closed, and test instrumentation may mutate obsolete storage without gaining code authority.
- **Host-private-mutation adversary:** even privileged reflective writes to authoritative objects must be detected or isolated. An O(1) Python guard is not a general write barrier; use stronger isolation or retain verification scans.

**Open owner/Review decision:** which model the project actually commits to, and whether current frozen mutation witnesses permit the chosen implementation. No performance optimization may quietly narrow an already required threat boundary.

## 6. Worked execution and adversarial cases

**Authentic invocation:** producer and admission events establish artifact authority; full source/bytecode preflight includes transitive dead branches; proof binds issuer/version/entry/policy and a stable execution view; the real VM opens the published authenticated chunk objects; its execution trace identifies the actual code node and source version.

**Self-consistently rehashed forgery:** an attacker replaces a retired backing `ArtifactSet` entry with a validly rehashed but unauthorized chunk. It never becomes part of the proof. A runner may reject or execute the original pinned chunk if its view is demonstrably independent and the unchanged acceptance witnesses permit it. Substituting an authoritative chunk must reject.

**Poisoned decoded definition:** before issuance, a mismatching cached `_definition` must not silently pass as a valid proof; compare with the canonical definition and refuse. After issuance, corruption of an *obsolete* memo must not change execution. Corruption of the *authoritative* definition cannot be allowed. The same rule applies transitively to callees.

**Replacement during an operation:** evaluator name `policy` changes from deployment A to B between two constraint checks. Both checks in the existing operation execute A; a subsequent operation executes B. Canonical constraint and target-state identities do not change.

**Explicit invalidation during execution:** an invalidated proof does not begin a new machine run. If invalidation happens between code-node openings, the next opening rejects as a host failure, without Python fallback or admission of partial target changes.

**Forbidden effect in dead branch:** a valid `WRITE` emitted under a read-only policy rejects in preflight before any target VM instruction. A pinned snapshot does not relax source or emitted-effect validation.

**Multi-External and budgets:** the exact canonical callback subject, callback count/order, Unknown/exception behavior, remaining node budget and operation-scoped selection must agree with the incumbent. A successful semantic verdict alone is insufficient evidence.

## 7. Required production gates

1. Independent Review accepts the chosen threat model, authority transition, revocation safe points and old-version behavior, with explicit Task 32 citations. No Plan amendment is implicit.
2. Issued proof and resolver are owned by the production restricted-execution module, not the test harness. No additional constraint-specific verifier or interpreter is added.
3. Opened chunk *identity*, owner, version, producing compiler generation, artifact ID, source-node and failure provenance pass the **unchanged** independent witnesses.
4. Wrong issuer, stale version, forbidden transitive/dead effect, forged/rehashed code, invalidated artifact set/generation, tampered definition and failed preparation all fail closed under the approved threat model.
5. The unchanged Task 32 and GH-123 acceptance suites pass, including read authority, write/activation/trial rollback, error provenance, callbacks and budget continuation. Any behavioral divergence is reported, not concealed.
6. Only after security equivalence is established, run the Plan-owned full performance protocol: three processes, paired blocks, bootstrap intervals, cold/warm cost, memory and scaling. The exploratory 107-workload result is **not** resource acceptance.

**Stop rule:** If a stable published execution view cannot satisfy the frozen object-identity and security witnesses, or if the required threat model includes untracked hostile mutation of authoritative Python objects without isolation, do **not** install a constant-time proof cache. Keep the current restricted runner and investigate less aggressive verification optimizations. Do not edit the frozen tests to make the experiment pass.

## 8. Separation from issue #130

This proposal changes no execution granularity. GH-123 only concerns authenticating ordinary existing per-expression artifacts efficiently. Function/basic-block fusion, specialization, native/JIT execution, and source-to-region provenance are explicitly delegated to #130.

## 9. Next action

Submit this provisional contract to a **fresh independent adversarial Review**. The reviewer must return APPROVE / REJECT / CONDITIONAL with concrete conflicts against `docs/restricted_execution.md`, frozen tests and D5 lifetime rules. Only then prepare a minimal production integration plan. No implementation or benchmark was authorized by this document.
