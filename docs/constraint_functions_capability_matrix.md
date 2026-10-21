# GH-123 – Vision-to-Capability Matrix

Status: Plan Resolve – independent Review required.
Branch: `task/123-complete-constraints`.
Original baseline: `f994a2d59b0f6f890f4800effe209d88e1c838c1`.
Provisional Execute head: `26327534a146fd261770c2b655f78c6e41b1dd02`.

## 1. Architectural basis

SHEAR's original vision establishes these principles:

- The semantic graph is canonical.
- Ordinary and semantic computation share a function model.
- Semantic identity is independent of physical representation.
- General primitives should support useful higher-level programs.
- Values may be opaque; representation exposure is not automatic.
- Effects and capabilities have distinct responsibilities.
- Constraints distinguish Satisfied, Violated and Unknown.
- Human-facing operations should be predictable.

Sources:
- README.md, sections 1–2, 8–17, 23, 32 and 35.
- CLAUDE.md.
- docs/semantic_graph.md.
- docs/constraint_model.md.
- docs/testing_model.md.
- docs/roadmap.md, decisions D1–D5.

The vision guides design but does not itself establish
an implemented or binding language operation.

## 2. Assessment layers

Assess capabilities separately at five boundaries:

- Host – Python semantic model and runtime services.
- VM – operations available to ordinary SHEAR functions.
- Compiler – SHEAR source lowered to executable instructions.
- Policy – Task 32 restricted-execution permissions.
- Evidence – actual GH-123 end-to-end demonstration.

Status:
- E: existing capability supported by repository evidence.
- P: partial or narrower capability.
- M: missing capability.
- X: explicitly forbidden.
- U: unverified or not yet designed.
- N: not applicable.

Host E does not imply VM E.
VM E does not imply Compiler E.
Compiler E does not imply Policy E.
Four E statuses do not establish GH-123 acceptance.

## 3. Capability matrix

| ID | Capability | Host | VM | Compiler | Policy | Evidence |
|---|---|---|---|---|---|---|
| C01 | Canonical serialization and identity | E | P | N | N | U |
| C02 | Pass raw canonical arguments | E | E | E | E | U |
| C03 | Construct and inspect tuples | E | E | E | E | U |
| C04 | Inspect semantic kind | E | M | M | M | U |
| C05 | Length across supported collections and text | E | M | M | M | U |
| C06 | Inspect lists and maps | E | M | M | M | U |
| C07 | Inspect text code points and bytes | E | M | M | M | U |
| C08 | Inspect semantic-record fields | E | M | M | M | U |
| C09 | Type-sensitive boolean equality | E | E | E | E | U |
| C10 | Reconstruct all semantic value kinds | E | M | U | U | U |
| C11 | Traverse maps and nested values | E | M | M | M | U |
| C12 | Compose three-valued results | E | P | E | E | U |
| C13 | Exact constraint-node budget accounting | E | P | E | E | U |
| C14 | Named external evaluator dispatch | E | P | P | X/P | U |
| C15 | Preserve host-failure provenance | E | P | P | P | U |
| C16 | Pure computation and static calls | E | E | E | E | E |
| C17 | Artifact authentication and effect preflight | E | N | N | E | E |
| C18 | Candidate-backed runtime admission | E | P | P | P | U |
| C19 | Support a new generic inspection operation | N | U | U | U | U |
| C20 | Execute all GH-123 acceptance suites in CI | N | N | N | N | M |

Interpretation:

- C01: Canonical serialization is host machinery.
  SHEAR equality does not expose a serialization API.
- C12–C13: Existing general computation provides building
  blocks, not verified constraint-equivalent implementations.
- C14: Static calls are permitted. Indirect calls are
  forbidden by current restricted policy. An authorized
  host callback boundary may still suffice.
- C17: Task 32 authority enforcement is host-managed,
  not a completed language-visible effect system.
- C19: No operation has been selected. Its missing
  implementation is not evidence against an undecided design.
- C20: The candidate acceptance suites are not yet
  registered for ordinary CI discovery.

Task 32 evidence for C16–C17 is not equivalent to
demonstrating the complete GH-123 candidate.

## 4. Inherited limitations

Task 24 documented missing:
- Canonical constraint-payload inspection.
- Canonical map inspection.
- Complete multi-kind Length behavior.
- Generic budgeting and external authority mechanisms.

Task 32 established authenticated restricted execution
but explicitly deferred complete canonical inspection,
generic resource budgets and full constraint replacement.

These limitations were known before GH-123 Execute began.
They were not sufficiently resolved at Plan entry.

Sources:
- docs/spikes/constraints_as_functions.md.
- docs/spikes/constraints_as_functions_execute.md.
- docs/restricted_execution.md.

## 5. D123-7 – Approved visibility boundary

Owner decision: ordinary SHEAR functions may inspect the
semantic structure of an immutable value supplied to them,
covering the 15 currently supported canonical kinds:

- none, bool, int, str, bytes;
- entity_id, version_id, state_id;
- tuple, list, map;
- cell, constraint, relation, closure.

Inspection is:
- Read-only and deterministic.
- Type-preserving.
- Independent of semantic identity.
- Generic rather than constraint-specific.
- Based on semantic content, not serialization internals.

Text exposes code points, not UTF-8 encoding bytes.
Bytes expose byte content, not an incidental hex encoding.
Maps expose semantic entries, not Python dictionary internals.
Semantic records expose defined semantic fields, not
arbitrary implementation attributes.

Inspection of a supplied value does not authorize:
- Traversal of unrelated program graph entities.
- Reading live cells or runtime frames.
- Access to external resources.
- Expansion of opaque representations.
- Bypassing capabilities or restricted execution.
- Mutation of the original value.

An opaque value remains opaque unless a separately
authorized expansion mechanism is available.

For semantic records, inspection must distinguish their
immutable content from live runtime state.

The public semantic-field interface is not required to
match the existing CanonicalNode tuple layout.

This decision approves visibility semantics only.
The operation name, result shape, instruction encoding,
compiler changes and implementation remain undecided.

## 6. Decisive feasibility experiment

The first implementation witness must exercise:

Raw canonical subject
→ authenticated admitted SHEAR function
→ generic semantic inspection
→ composite constraint evaluation
→ exact budget accounting
→ returned three-valued verdict.

Use the same compiled evaluator on independently selected
subjects covering strings, bytes, maps and nested data.

Verify together:
- G1: Raw subject without subject-dependent host projection.
- G2: Correct semantic-kind inspection.
- G3: Correct multi-kind lengths.
- G4: Nested semantic-field and map access.
- G5: Genericity outside constraint-specific inputs.
- G6: Exact composite and short-circuit budgets.
- G8: Authenticated execution without Python predicate fallback.
- G10: Compiler, verifier and VM agreement.

Do not accept an isolated inspection demonstration as
proof that the architecture supports ordinary constraints.

After the integrated witness, extend the same candidate:

- G7: Named external evaluator dispatch, Unknown and
  host-failure provenance.
- G9: Genuine initial admission, writes, activation
  and trials using candidate-produced verdicts.

G7 and G9 are mandatory, not optional follow-ups.

## 7. External dispatch discriminator

Test two alternatives:

A. Existing static calls and authorized host dispatch
   implement every frozen External case.

B. A new generic capability-controlled invocation boundary
   is required.

The frozen external acceptance permits host-boundary
callback dispatch after authenticated SHEAR execution.
It does not require arbitrary Python callbacks inside the VM.

Prove:
- Correct evaluator selection and pinning.
- Exact canonical subject and budget behavior.
- No callback when admitted execution fails.
- Missing evaluators produce Unknown as specified.
- Escaping host exceptions preserve type and identity.
- Forbidden invocation never gains authority.

If A fails, document the smallest counterexample and
request owner approval for B's authority, effect and
failure semantics before implementing it.

## 8. Human-facing naming audit

Names must communicate semantics to human programmers.

| Names | Actual distinction | Disposition |
|---|---|---|
| len / Length | Tuple-length operation versus multi-kind length constraint | Review generalization or clearer naming |
| eq / semantic equality | Current boolean operation versus possible future three-valued reasoning | Keep the contracts explicitly distinct |
| ref / Reference | Callable EntityID versus version-pinned state reference | Consider distinct names |
| function / Function | Constructed function value is not directly installed and callable | Clarify construction semantics |
| Role / relation role | Predicate over semantic role content versus a graph endpoint role | Clarify context |
| IsKind / kind inspection | Existing constraint test versus missing ordinary introspection | Resolve the capability gap |

Naming options include documentation, full renaming,
prefixes or namespaces.

Prefer the smallest change that makes source code clear.
Do not change settled semantics for naming consistency.

Public renames require migration analysis and owner approval.
Unrelated renames are not GH-123 blockers.

## 9. Process gate

Before implementation, every critical dependency must be:

- Demonstrated with relevant executable evidence.
- Explicitly experimental, with a falsifier and stop condition.
- Blocked until a required capability or decision exists.
- Justifiably out of scope under frozen acceptance.

Independent Plan Review must reconcile prior negative
evidence and check for unexamined dependencies.

Execute must return material contradictions to Plan rather
than silently changing the contract.

The repository-wide workflow rule is subject to independent
review of its amended text.

## 10. Preserved requirements

Unchanged:
- All 15 original candidate acceptance modules.
- All 56 original candidate-dependent test methods.
- Task 24 semantic oracles and 17 boundary cases.
- Task 32 authentication and security guarantees.
- Canonical identity and golden records.
- The agreed 1000x performance ceilings.

No new instruction or public API is authorized here.
No candidate acceptance result has been demonstrated.
Independent Plan Review remains required.
