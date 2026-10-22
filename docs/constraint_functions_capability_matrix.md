# GH-123 – Vision-to-Capability Matrix

Status: Architecture and T5 acceptance independently approved; D123-7c and D123-8 owner-authorized. Execute evidence pending.
Branch: `task/123-complete-constraints`.
Original baseline: `f994a2d59b0f6f890f4800effe209d88e1c838c1`.
Construction approval baseline: `9c4ef2839d8b04f1a9f63d961707c3967ee1bba1`.

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

Owner approval authorizes implementation but does not
change a missing capability to an implemented capability.

The matrix records the pre-Execute implementation baseline.
Execute must update status from actual repository and test
evidence, not from design approval alone.

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
| C10 | Reconstruct semantic values, including typed records | P | M | M | M | U |
| C11 | Traverse maps and nested values | E | M | M | M | U |
| C12 | Compose three-valued results | E | P | E | E | U |
| C13 | Exact constraint-node budget accounting | E | P | E | E | U |
| C14 | Named external evaluator dispatch | E | P | P | X/P | U |
| C15 | Preserve host-failure provenance | E | P | P | P | U |
| C16 | Pure computation and static calls | E | E | E | E | E |
| C17 | Artifact authentication and effect preflight | E | N | N | E | E |
| C18 | Candidate-backed runtime admission | E | P | P | P | U |
| C19 | Approved generic inspect operation | N | M | M | M | U |
| C20 | Execute all GH-123 acceptance suites in CI | N | N | N | N | M |

Interpretation:

- C01: Canonical serialization is host machinery.
  SHEAR equality does not expose a serialization API.
- C04–C08 and C11: The generic inspection/access
  design is approved but not yet implemented.
- C10: The original capability question was broader
  than construction of constraint records. D123-8
  authorizes a generic pure `record(kind, fields)`
  operation for Cell, Constraint and Relation.
  It does not authorize closure construction,
  forging opaque identifiers or independently
  manufacturing every semantic kind.
  Existing host constructors cover only part of the
  broader reconstruction capability.
  Full C10 closure requires applicable frozen evidence,
  not merely a working record constructor.
- C12–C13: Existing general computation provides building
  blocks, not verified constraint-equivalent implementations.
- C14: Static calls are permitted. Indirect calls are
  forbidden by current restricted policy. An authorized
  host callback boundary may still suffice.
- C17: Task 32 authority enforcement is host-managed,
  not a completed language-visible effect system.
- C19: D123-7b authorizes generic `inspect(value)`.
  D123-7c authorizes generalized `len`, `item`, `slice`,
  named record lookup and public field schemas.
  The operations are not yet implemented across the
  required compiler, VM and restricted-policy boundaries.
- C20: All 18 candidate-dependent modules and 78 test
  methods are approved and mandatory but not yet
  registered and executed as a completed candidate lane.

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

D123-7c resolves the inspection-interface design gap.
D123-8 resolves the semantic-record construction-design gap.

Neither decision constitutes implementation or proves
end-to-end semantic equivalence.

Sources:
- docs/spikes/constraints_as_functions.md.
- docs/spikes/constraints_as_functions_execute.md.
- docs/restricted_execution.md.
- docs/semantic_inspection.md.
- docs/semantic_record_construction.md.

## 5. D123-7 and D123-8 – Approved generic capabilities

### D123-7a and D123-7b

D123-7a approves inspection of the semantic structure
of supplied immutable values across all 15 canonical kinds:

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

D123-7b approves `inspect(value)` as the generic pure
inspection operation, with input form:

    ("inspect", expression)

Its result is:

    (semantic_kind, original_value)

The earlier eager `(semantic_kind, members_tuple)`
result contract is superseded.

### D123-7c

The independently reviewed public inspection interface
was explicitly authorized by the owner.

It includes generalized:

    len(value)
    item(value, index)
    slice(value, start, stop)

across the approved semantic kinds.

String-named field lookup through `item` is authorized.

The public Cell, Constraint and Relation schemas are
approved, while Closure remains opaque.

Required properties:

- No eager proportional-size materialization.
- Demand-driven element and field access.
- Unicode code-point semantics without normalization.
- Deterministic canonical-key map ordering.
- Preservation of semantic types and identities.
- No disclosure of private CanonicalNode representation.
- Inspection costs distinct from semantic budgets.
- No new runtime, graph or external authority.

For semantic records, inspection distinguishes immutable
declaration content from live runtime state.

The normative specification is:

    docs/semantic_inspection.md

The interface-design Review gate is closed.

### D123-8

The owner approved one generic pure constructor:

    record(kind, fields)

Supported immutable semantic-record kinds:

- cell
- constraint
- relation

The constructor uses existing canonical validation,
normalization and identity rules.

SHEAR functions compute the kind and fields.
An authenticated VM instruction performs construction
and returns the typed semantic value.

Pure Python canonical constructors may be reused inside
that VM instruction.

Adapter-side construction after admitted execution
is prohibited.

No constraint-specific interpreter, arbitrary host
callback, dynamic host-class construction, graph
mutation or additional execution authority is authorized.

Closures remain opaque and are not constructible.

The normative specification is:

    docs/semantic_record_construction.md

The construction-design Review gate is closed.

### Preserved authority boundaries

The approved operations do not authorize:

- Traversal of unrelated program graph entities.
- Reading live cells or runtime frames.
- Access to undeclared external resources.
- Expansion of opaque representations.
- Forging entity or version identifiers.
- Bypassing restricted execution.
- Mutation of canonical semantic contents.

Compiler, verifier, VM, artifact and restricted-policy
implementation remains Execute work.

New normative language operations or authority changes
require another explicit owner decision.

## 6. Decisive feasibility experiment

The first integrated implementation witness must exercise:

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

The approved D123-8 constructor must additionally
reconstruct all nine constraint forms through genuine
admitted SHEAR execution while retaining canonical identity.

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
- Nested External composition through AllOf, AnyOf,
  Not and Role.
- Correct continuation without replay of completed work.
- Correct short-circuit behavior and exact node budgets.
- Fresh semantic budget for each top-level evaluation.
- No callback when admitted execution fails.
- Missing evaluators produce Unknown as specified.
- Escaping host exceptions preserve type and identity.
- Forbidden invocation never gains authority.

If A fails, document the smallest counterexample and
request owner approval for B's authority, effect and
failure semantics before implementing it.

This is an early integrated Execute discriminator,
not a reason to reopen the approved interface design.

## 8. Human-facing naming audit

Names must communicate semantics to human programmers.

| Names | Actual distinction | Disposition |
|---|---|---|
| len / Length | Approved general data-length operation versus semantic Length constraint | Preserve distinction in documentation |
| eq / semantic equality | Boolean equality versus possible future three-valued reasoning | Keep contracts distinct |
| ref / Reference | Callable EntityID versus version-pinned state reference | Consider distinct names |
| function / Function | Constructed function value is not directly installed and callable | Clarify construction semantics |
| Role / relation role | Predicate over semantic role content versus a graph endpoint role | Clarify context |
| IsKind / inspect | Semantic constraint test versus generic type inspection | Preserve distinct operations |
| tuple / record | Ordinary sequence construction versus typed semantic-record construction | Preserve kind and identity distinctions |

Naming options include documentation, full renaming,
prefixes or namespaces.

Prefer the smallest change that makes source code clear.
Do not change settled semantics for naming consistency.

Public renames require migration analysis and owner approval.
Unrelated renames are not GH-123 blockers.

## 9. Execute gate

The architectural Plan, T5 acceptance contract,
D123-7c inspection design and D123-8 construction
design have been independently approved.

Both normative interface decisions are owner-authorized.

Before claiming complete feasibility, demonstrate:
- Genuine authenticated execution of generic operations.
- Complete constraint semantics through ordinary functions.
- Nested external evaluation and continuation.
- Exact semantic budgets.
- Typed semantic-record reconstruction.
- Candidate-backed real runtime admission.
- No subject-dependent Python semantic fallback.
- Complete frozen acceptance and applicable regressions.
- Reproducible resource and mechanism measurements.

The bounded Plan Resolve permits only narrowly
declared compiler-induced golden identity changes,
as specified in `docs/constraint_functions_complete.md`.

Create `tests/golden_changes/GH-123.txt` during Execute
with only records actually changed by compiler evolution.
Never use a wildcard or declare unchanged records.

Regenerate and verify the hosted seed manifest.

Execute must return material architectural contradictions
to the owner rather than silently changing the contract.

## 10. Preserved requirements

Unchanged:
- All 18 candidate-dependent acceptance modules.
- All 78 candidate-dependent test methods.
- Task 24 semantic oracles and 17 boundary cases.
- Task 32 authentication and security guarantees.
- All existing behavioral golden expectations.
- Canonical identity rules and unrelated golden records.
- The agreed 1000x performance ceilings.

The original 15 modules and 56 test methods remain
mandatory within the expanded inventory.

D123-7c and D123-8 authorize specified generic language
operations but no additional execution authority.

The narrowly declared compiler-code golden exception
does not permit unrelated identity or behavioral changes.

No candidate acceptance result has yet been demonstrated.

The remaining work is implementation and experimental
validation, not another foundational design cycle.
