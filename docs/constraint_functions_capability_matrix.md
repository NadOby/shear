
# GH-123 – Vision-to-Capability Matrix

Status: Plan amendment – provisional, independent Review required.
Repository: NadOby/shear
Branch: task/123-complete-constraints
Audited Execute head: 26327534a146fd261770c2b655f78c6e41b1dd02

## 1. Purpose

Determine whether SHEAR has the generic capabilities required
to implement complete constraint semantics through admitted
ordinary SHEAR computation.

Begin with architectural intent, not the current implementation.

Distinguish:

- Vision – long-term direction, not automatically normative.
- Decided – binding semantic and architectural rules.
- Implemented – capabilities supported by repository evidence.
- Required – capabilities necessary for GH-123 acceptance.

Do not treat a Python reference-model facility as a
language-level facility.

Do not treat passing existing tests as proof that all required
combinations of capabilities are implementable.

## 2. Architectural anchors

V1. The semantic graph is the canonical program.

V2. Runtime, compile-time, transformation and semantic
computation share the ordinary function model.

V3. Semantic meaning and identity are independent of physical
representation and executable deployment.

V4. A small set of general primitives should support useful
higher-level behavior without application-specific machinery.

V5. Values can be opaque. Uniform semantic treatment does not
imply unrestricted access to internal representations.

V6. Capabilities authorize behavior; effects describe it.
Execution authority must be explicit and enforceable.

V7. Programs retain their compiler and may transform their
semantic graph, validate candidates and activate them.

V8. Constraints distinguish Satisfied, Violated and Unknown.
Computation failures are not semantic Unknown results.

V9. Architecture is evaluated through falsifiable experiments.
Mechanism count, complexity and performance all matter.

V10. Nontrivial features should be implementable as ordinary
programs or libraries where the core mechanisms suffice.

Sources:
- README.md, sections 1–2, 8–17, 23, 32 and 35.
- CLAUDE.md, Vision and Workflow.
- docs/semantic_graph.md.
- docs/constraint_model.md.
- docs/testing_model.md.
- docs/roadmap.md, decisions D1–D5.

## 3. Assessment notation

E = Existing, evidenced by implementation and tests.
P = Partially available or limited to a narrower contract.
M = Missing from the examined implementation.
X = Explicitly forbidden by the applicable policy.
U = Unverified for the required end-to-end use.
N = Not applicable at this boundary.

E does not mean independently demonstrated for GH-123.
End-to-end evidence is tracked separately.

Columns:
- Model: Python semantic reference implementation.
- Language: ordinary SHEAR operations and host VM.
- Restricted: Task 32 admitted execution.
- GH-123: current sufficiency assessment.

## 4. Capability matrix

| ID | Capability | Model | Language | Restricted | GH-123 |
|---|---|---|---|---|---|
| C01 | Canonical identity and serialization | E | P | E | Existing invariant |
| C02 | Passing raw canonical subjects | E | E | E | Binding must be proven |
| C03 | Tuple construction and inspection | E | E | E | Sufficient for tuples |
| C04 | Generic semantic-kind inspection | E | M | M | Blocker |
| C05 | Length of text, bytes, lists and maps | E | M | M | Blocker |
| C06 | Structural access to lists and maps | E | M | M | Blocker |
| C07 | Inspecting text code points and bytes | E | M | M | Blocker |
| C08 | Generic canonical-record inspection | E | M | M | Blocker |
| C09 | Type-sensitive semantic equality | E | E | E | Existing mechanism |
| C10 | Generic reconstruction of semantic kinds | E | P | P | Unverified |
| C11 | Role-map and nested-subject traversal | E | M | M | Blocker |
| C12 | Strong Kleene composition | E | P | P | Unverified |
| C13 | Exact constraint-node budgeting | E | P | P | Unverified |
| C14 | Named external evaluator dispatch | E | P | P/X | Unverified |
| C15 | Semantic versus host failure provenance | E | P | P | Unverified |
| C16 | Pure computation and static calls | E | E | E | Existing mechanism |
| C17 | Effect and artifact authority enforcement | E | E | E | Existing foundation |
| C18 | Candidate-backed runtime admission | E | P | P | Unverified |
| C19 | Compiler support for proposed new operations | N | M | M | Decision required |
| C20 | CI registration of all new acceptance suites | N | N | N | Not yet registered |

The matrix distinguishes the existence of building blocks
from proof that they compose into complete constraint semantics.

Current findings are based on repository inspection and
existing tests. Candidate-dependent acceptance has not run.

## 5. Evidence anchors

C01–C03:
- shear/canonical.py
- shear/lang.py
- shear/machine.py
- tests/test_canonical.py
- tests/test_data_ops.py

C04–C11:
- shear/constraints.py
- shear/operations.py
- shear/bytecode.py
- shear/machine.py
- docs/language_data.md
- docs/spikes/constraints_as_functions_execute.md

C12–C15:
- docs/constraint_model.md
- docs/error_handling.md
- tests/constraint_function_oracle.py
- tests/constraint_functions_t2_t3_acceptance.py
- tests/constraint_functions_external_acceptance.py

C16–C19:
- docs/roadmap.md, D3–D5
- shear/examples/compiler_source.py
- shear/hosted_bootstrap/restricted.py
- shear/hosted_bootstrap/restricted_policy.py
- shear/hosted_bootstrap/validation.py
- shear/instructions.py

C20:
- tests/lanes.py
- .github/workflows/semantic-model.yml
- docs/constraint_functions_complete.md

## 6. Known blockers inherited from prior work

Task 24 candidate B established missing generic facilities:

- Canonical constraint payload inspection.
- Canonical map inspection.
- Complete Length behavior across semantic kinds.

Task 24 also identified unresolved generic budgeting,
external authority and initial-admission requirements.

Task 32 resolved part of the authority and admission
problem through authenticated restricted execution.

Task 32 explicitly deferred complete canonical inspection,
generic budgets and full constraint replacement.

GH-123 inherited those limitations.

The original Plan treated existing-operation sufficiency
as a falsifiable hypothesis but did not test that
prerequisite before substantial Execute work.

This is a failure of dependency verification, not a
newly discovered absence of historical evidence.

Sources:
- docs/spikes/constraints_as_functions.md
- docs/spikes/constraints_as_functions_execute.md
- docs/restricted_execution.md, sections 2–3

## 7. Minimal feasibility gates

G1. A raw canonical subject reaches an admitted SHEAR
function without subject-dependent host preparation.

G2. SHEAR computation identifies all 15 semantic kinds.

G3. SHEAR computation derives correct lengths for text,
bytes, tuples, lists and maps, including empty values.

G4. SHEAR computation selects nested canonical map and
record contents, preserving semantic type distinctions.

G5. The same generic inspection facilities work on
non-constraint data without application-specific dispatch.

G6. One admitted evaluator implements a budget-sensitive
composite constraint on multiple independently chosen subjects.

G7. Named external evaluation preserves the distinctions
between absence, Unknown, a decisive result and host failure.

G8. The evaluator executes through authenticated artifacts,
under preflight policy, without Python predicate fallback.

G9. Genuine initial admission and subsequent runtime
operations consume candidate verdicts without bypass.

G10. Required source operations are supported by the
SHEAR compiler, admitted verifier and executing machine.

Each gate requires:
- A reproducible executable witness.
- Exact source and execution boundary.
- Expected and observed outcome.
- Evidence of actual admitted computation where applicable.
- A failure classification and next action.

No unexecuted gate may be reported as passed.

## 8. Provisional architectural finding

The existing tuple operations do not supply G2–G5.

Host-side preprojection cannot substitute for the original
canonical subject required by frozen direct-result acceptance.

A generic shallow structural-view operation is a candidate
solution, not an approved language design.

Its adequacy must be tested against G1–G10, rather than
only against the first missing Length operation.

No new VM instruction, syntax or normative data operation
is authorized until the owner decides.

## 9. Process failure and prevention requirement

The missing inspection capability was known before GH-123.
It propagated because Plan approval verified acceptance
integrity without closing its inherited prerequisites.

For future implementation Plans, every critical dependency
must have one explicit disposition:

- Demonstrated – with reproducible end-to-end evidence.
- Exploratory – made the first bounded experiment, with
  a stop condition before dependent implementation work.
- Blocked – no Execute beyond the prerequisite is approved.
- Out of scope – justified without contradicting the task
  acceptance contract.

An unverified capability must never silently count as
an existing dependency.

Independent Plan Review must reconcile the capability
matrix with earlier negative evidence, open limitations
and task dependencies.

Execute must stop and return to Plan when a critical
dependency fails, rather than build workaround machinery
that silently changes the architectural contract.

The generic workflow amendment is tracked separately
from this task-specific capability matrix.

## 10. Next actions

1. Independently validate matrix classifications.
2. Run G1–G5 as the smallest generic-inspection experiment.
3. Determine whether G6–G10 expose additional blockers.
4. Compare generic mechanism alternatives.
5. Request owner approval for language-shaping changes.
6. Add the generic dependency gate to docs/roadmap.md.
7. Independently review the amended Plan before Execute.

All 15 existing GH-123 acceptance modules and Task 24
frozen oracles remain unchanged.


## 11. Human-facing naming and semantic clarity

SHEAR's language surface must be understandable and
predictable to human programmers, not merely distinguishable
by parsers, tools or language models.

Naming consistency does not require changing established
semantics or making all similarly named operations equivalent.

Audit corresponding concepts across:
- The original architectural vision.
- Decided semantic specifications.
- Ordinary SHEAR source operations.
- Constraint and contract interfaces.
- The Python reference-model API.

For each ambiguous name, record:
- The accepted kinds and input domain.
- The returned result and its semantic category.
- Failure and resource behavior.
- Effects and authority requirements.
- Identity and continuity implications.
- The likelihood of human misunderstanding.

Initial candidates:

| Names | Clarity risk | Disposition |
|---|---|---|
| len / Length | Tuple-only operation versus multi-kind constraint | Review naming and documented domains |
| eq / semantic equality | Boolean result versus aspirational three-valued reasoning | Distinguish current and future contracts |
| ref / Reference | Callable EntityID versus state/version-pinned handle | Review names for distinct reference categories |
| function / Function | Function value versus installed executable definition | Clarify construction and execution |
| Role / relation role | Canonical-map predicate versus graph endpoint role | Clarify semantic context |
| IsKind / kind inspection | Constraint predicate versus generic value introspection | Record the missing ordinary capability |

Possible solutions include:
- Keeping existing names with clearer documentation.
- Renaming an operation to describe its actual domain.
- Using a semantic namespace or prefix.
- Introducing a generic operation while preserving the
  behavior of existing specialized operations.

Prefer the option that makes ordinary source code clearest
with the least ongoing complexity.

No renaming, changed semantics, new compatibility layer,
canonical-identity change or frozen-test change is authorized
by this audit.

If a proposed rename changes public source syntax or APIs,
record its migration cost and obtain owner approval.

Independent Plan Review must assess human-facing clarity,
not only whether names and operations are mechanically
distinguishable.

A naming issue is blocking only when it materially affects
the current task's correctness, acceptance or architectural
decision. Other findings remain explicitly tracked.

The general Plan/Review workflow must require this audit
when new operations overlap existing semantic concepts.
