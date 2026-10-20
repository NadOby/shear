# Complete Constraint Semantics with Ordinary SHEAR Functions

Status: Proposed frozen Plan – pending independent Review.
Issue: GH-123.
Baseline: f994a2d59b0f6f890f4800effe209d88e1c838c1.
Dependencies: Task 24 (#56), Task 32 (#119).

## 1. Question

Can ordinary SHEAR functions, running through the existing
restricted execution system, reproduce the complete constraint
contract without a dedicated constraint interpreter or Python
fallback, at acceptable mechanism complexity and execution cost?

Test sufficiency, not superiority or net mechanism savings.

H1: Complete equivalence is possible using generic facilities.
H0: The tested approach fails an explicit semantic, mechanism,
or resource discriminator.

Task 24's bounded negative evidence remains valid.
Task 32 established genuine restricted admission integration
but did not establish complete constraint equivalence.

## 2. Strategy

Implement one complete end-to-end candidate.

Keep canonical constraint values and identity unchanged.
Represent constraint logic using ordinary SHEAR functions.
Use existing compiler, VM, hosted artifacts and Task 32
restricted execution.

Use the existing runtime admission paths for initial load,
write, activation and trial.

Do not stage incomplete A/B/C prototypes as separate milestones.
Do not build a second constraint interpreter.
Do not introduce a Python truth-evaluation fallback.

Keep the incumbent evaluator as a control implementation,
isolated from candidate execution.

## 3. Initial implementation hypothesis

H-1: No new syntax is needed.
H-2: No new VM instruction is needed.
H-3: Existing canonical content can be projected into ordinary,
inspectable immutable SHEAR data.
H-4: Existing arithmetic, tuples, control flow, equality, calls
and recursion suffice to implement all constraint operations.
H-5: An ordinary explicit budget parameter suffices to reproduce
constraint-node accounting.
H-6: Task 32's generic restricted execution and named evaluator
authority suffice for safe runtime integration.

These are hypotheses, not unconditional acceptance restrictions.

Falsify each hypothesis with a minimal executable witness.
A necessary language-shaping change requires owner approval.
Do not silently invent constraint-specific facilities.

## 4. Canonical-content access

Use the existing canonical representation as the source.

Provide a generic, deterministic, immutable projection into
ordinary inspectable values where existing VM data operations
cannot inspect canonical nodes directly.

Preserve semantic kinds, including distinctions between:
- bool and int;
- string code points and encoded bytes;
- tuple, list and map;
- entity, state and version identities;
- canonical records and their tagged payloads.

Preserve canonical map entries, nested data, and owned-subtree
structures without changing canonical identity.

This projection is a generic data facility, not a constraint
parser or interpreter.

Test equivalent structural inspection outside constraints.

No alternative canonical identity format is authorized.

## 5. Ordinary SHEAR evaluator

Implement the complete existing constraint contract:

- IsKind
- IntRange
- Length
- OneOf
- AllOf
- AnyOf
- Not
- Role
- External

Preserve:
- all 15 canonical semantic kinds;
- strong Kleene logic;
- empty composition results;
- canonical repetition and deduplication;
- order independence;
- existing short-circuit semantics;
- type-sensitive equality;
- exact existing primitive boundaries;
- missing-role semantics;
- canonical subjects for relations and owned subtrees.

The evaluator performs dispatch, composition and recursion
through ordinary SHEAR computation.

Python may prepare canonical inputs, manage authenticated
execution authority and convert result transport types.
It may not compute candidate constraint truth.

## 6. Budgets and errors

Preserve the existing constraint-node budget.

Every visited constraint node consumes one unit.
Exhaustion yields Unknown, not Violated.
Existing short-circuit results retain their precedence.

Pass budget state through ordinary SHEAR computation.
Do not mistake VM call-depth limits for node budgets.

A separate generic machine-fuel budget may be considered if
termination or execution safety requires it. It must not
silently replace existing semantic budget accounting.

Preserve the distinction between:
- Satisfied;
- Violated;
- Unknown;
- absent External evaluator;
- escaping host failure;
- language execution limit;
- restricted-admission rejection.

A host failure cannot become catchable merely because the
evaluator uses SHEAR functions.

Do not assume the incumbent constraint-node budget bounds
non-terminating external computations. Preserve and test this
documented limitation separately from any new generic fuel cap.

## 7. Named evaluators and admission

Reuse Task 32's authenticated deployments, pinned versions,
compiler generations and restricted execution.

Prefer generic static dispatch over added dynamic authority.
If insufficient, test the smallest generic authenticated
indirect-call facility and return language-shaping decisions
to the owner.

Use genuine runtime operations:
- initial cell and relation admission;
- successful and rejected writes;
- successful and rejected activation;
- isolated trials.

Preserve semantic identity independently of evaluator deployment.
Preserve operation-scoped evaluator selection and replacement rules.

No retroactive revalidation is introduced.

Only Satisfied admits mandatory operations.
Rejected operations preserve all prior live state and artifact
bindings.

## 8. Frozen semantic acceptance

Reuse the unchanged Task 24 oracle and grading contract:

tests/constraint_function_oracle.py
tests/constraint_function_acceptance.py
tests/constraint_function_boundary_acceptance.py

Require:
- every frozen fixed semantic vector;
- at least 100 deterministic seeds from each existing generated
  family;
- all existing primitive, logical and budget witnesses;
- the exact frozen inventory of 17 boundary cases;
- all original expected observations, unchanged and in order;
- full T1–T9 obligations from the Task 24 Plan.

An unsupported case is a failure, not a successful rejection.

No fixture names, oracle expectations or replay seeds may be
provided to the candidate evaluator.

No weakening of Task 24 acceptance or golden records is permitted.

## 9. Execution authenticity

Independent instrumentation must demonstrate:
- compiled ordinary SHEAR evaluator code;
- authenticated admitted artifacts;
- actual machine entry and executed node identities;
- zero incumbent constraint-evaluator calls;
- zero Python predicate fallback;
- exact operation and constrained target identities;
- actual runtime transitions and their outcomes.

Poison incumbent evaluation during candidate acceptance.
Disable host lowering after preparation.
Corrupt or remove required artifacts and demand fail-closed
behavior rather than alternate execution.

Test malformed source and emitted instructions, forbidden
transitive effects, unknown operations and unauthorized
artifact substitutions.

Inspect immutable before/after snapshots for rejected operations.

A claimed execution route is not independent evidence.

## 10. Performance and mechanism evidence

Compare against the unchanged incumbent on matched workloads.

Measure:
- compilation and initial preparation;
- cold and warm execution;
- median and p95 latency;
- executed instruction count;
- peak memory;
- artifact size;
- behavior at 8, 64 and 256 constraint nodes.

Use repeatable inputs, environment details and raw observations.

The owner-approved initial sufficiency ceiling is 1000x
the incumbent for both warm median and p95 latency.
Record measurement uncertainty and distinguish preparation
from execution. Exceeding this ceiling triggers investigation,
not automatic termination. A resource-based negative verdict
requires reproducible evidence and owner confirmation that
the observed cost is unacceptable.

There is no fixed limit on the number of new generic mechanisms.
Count and justify every mechanism independently. A necessary
language-shaping change still requires owner approval.

Count retained, reused, extended, added, shared and genuinely
removable mechanisms using Task 24's M1–M4 and N1–N5 taxonomy.

No hypothetical removal receives actual removal credit.
Function bodies implementing constraint logic are ordinary
programs, but special host dispatch or interpreter rules count
as independent machinery.

## 11. Frozen terminal criteria

Positive:
- All semantic vectors and 17 boundary cases pass.
- All required T1–T9 obligations are exercised.
- Actual runtime admission executes ordinary SHEAR functions.
- No separate constraint interpreter or Python fallback exists
  on the candidate path.
- Isolation, provenance and atomicity are independently proven.
- Genericity and agreed complexity/resource bounds hold.
- Full applicable CI and existing corpora pass.

Negative:
- A reproducible smallest counterexample demonstrates a
  semantic invariant conflict, necessary prohibited mechanism,
  or exceeded agreed complexity/resource bound.
- The exact assumptions and tested implementation are stated.
- Missing implementation alone does not prove impossibility.

Inconclusive:
- A required case is unexecuted;
- authenticity or fallback isolation cannot be verified;
- a defect prevents meaningful evaluation; or
- costs or required generic mechanisms remain unmeasured.

Every negative or inconclusive outcome requires a precise
missing discriminator and an immediate actionable successor.

A negative or inconclusive experiment does not by itself satisfy
the positive implementation acceptance or authorize closing
the issue.

## 12. Execution and Review

Plan freezes the specification and executable acceptance
contract before implementation.

Execute performs one complete implementation attempt and
records positive, negative or inconclusive observations.

The existing Task 24 graders are mandatory, not optional
comparative evidence.

Independent Review must verify:
- Plan-owned acceptance integrity;
- absence of hidden fallback;
- real machine and runtime execution;
- unchanged canonical/golden behavior;
- exact semantic and failure outcomes;
- reproducible cost measurements;
- complete mechanism accounting;
- supported outcome classification.

No architectural redesign, new normative language operation or
removal of incumbent functionality is authorized by Execute
without the owner's decision.

## 13. Owner decisions

D123-1: Generic canonical projection preferred.
D123-2: No new syntax or VM instructions initially.
D123-3: Existing restricted execution preferred.
D123-4: Exact semantic budgeting through ordinary computation.
D123-5: Production removal deferred until equivalence is proven.
D123-6: Owner approves 1000x warm median and p95 latency
as initial sufficiency ceilings, subject to evidence-based review.
No hard count limit applies to new generic mechanisms.
Every mechanism must be identified, justified and measured.

These preferences may be falsified by the experiment.
Any replacement language decision returns to the owner.

## 14. Plan-owned verification contracts

The following documents jointly define the Plan-owned acceptance
obligations for this experiment:

- `docs/constraint_functions_complete_coverage.md`
  maps every Task 24 T1–T9 obligation to executable checks.
- `docs/constraint_functions_complete_benchmarks.md`
  defines measurement, uncertainty and mechanism accounting.

The existing primary acceptance suites remain mandatory:

- `tests/constraint_functions_complete_acceptance.py`
- `tests/constraint_functions_complete_projection.py`
- `tests/constraint_functions_projection_adversarial.py`
- `tests/constraint_functions_semantic_adversarial.py`

The additional Plan-owned acceptance suites are:

- `tests/constraint_functions_import_acceptance.py`
  – fresh-process import under incumbent poisoning.
- `tests/constraint_functions_direct_result_acceptance.py`
  – direct results from subject-independent admitted preparation.
- `tests/constraint_functions_binding_acceptance.py`
  – exact operation, subject and actual machine-result binding.
- `tests/constraint_functions_t2_t3_acceptance.py`
  – malformed inputs and exact semantic budget witnesses.
- `tests/constraint_functions_external_acceptance.py`
  – external dispatch, canonical subjects, failures and timeout.
- `tests/constraint_functions_identity_acceptance.py`
  – semantic constraint reconstruction and canonical identity.
- `tests/constraint_functions_runtime_acceptance.py`
  – relation admission, explicit rename and staged operations.
- `tests/constraint_functions_failure_acceptance.py`
  – actual runtime exception and failure provenance.
- `tests/constraint_functions_corpus_acceptance.py`
  – complete existing corpus replay through candidate integration.
- `tests/constraint_functions_authority_acceptance.py`
  – authenticated artifacts, effects and replacement isolation.

These modules remain outside ordinary test discovery during Plan.
Execute must supply the real candidate, register the complete
acceptance inventory and run all applicable existing CI lanes.

The acceptance tests specify observations, not a required
internal evaluator architecture. Their candidate-facing adapters
may not substitute Python truth evaluation for SHEAR execution.

Task 24's frozen semantic oracles, all 17 boundary cases,
expected results and golden records remain authoritative.

The new suites are not demonstrated merely by being committed.
Before Execute, independent Review must check their consistency,
feasibility, completeness and ability to reject incorrect
candidate implementations.

During Execute, qualification additionally requires independent
source-path and fallback audit, genuine runtime transitions,
authenticated execution evidence, complete applicable corpora,
performance measurements and mechanism accounting.

No Plan acceptance requirement may be weakened during Execute
without an explicit owner decision and renewed independent Review.
