# Constraints as Functions – Task 24

**Status: Provisional – Plan pre-registration.**

Issue: GH-56. Baseline: main at `697b2d7`.

This document fixes the experiment's designs, predictions, discriminators and decision rule before implementation. It records no experimental result.

## 1. Question and null hypothesis

Can the current semantic constraint algebra be evaluated through ordinary SHEAR functions using fewer total mechanisms, without changing its observable semantics?

H0: Replacing the dedicated constraint evaluator does not decrease the total mechanism count while preserving semantics.

H1: At least one function-based design preserves semantics and strictly decreases the total mechanism count.

A failed experiment is a valid result. Architectural preference is not evidence for H1.

Adoption requires both semantic equivalence and a strict mechanism reduction. Code-size reduction alone is insufficient.

## 2. Existing semantic contract

The control is the current implementation in `shear/constraints.py`, `shear/runtime.py` and `shear/relations.py`, interpreted according to `docs/constraint_model.md`, `docs/relation_model.md` section 7, and `docs/error_handling.md`.

The following are invariants, not opportunities for redesign:

1. Constraints are immutable, canonically identified semantic values. Evaluation context and history do not affect identity.
2. Results are Satisfied, Violated and Unknown. Unknown is not false and is not an ordinary execution failure.
3. AND, OR and NOT follow strong Kleene logic. Empty AND is Satisfied, empty OR is Violated. Composite operands have canonical set semantics.
4. Primitives retain their behaviour: IsKind, IntRange, Length, OneOf and Role. Bool is not IntRange's integer kind.
5. Every evaluated constraint node consumes one unit of the existing constraint budget. Exhaustion yields Unknown, subject to already established short-circuit results.
6. An External constraint references a named evaluator. An absent evaluator yields Unknown. Registered evaluators receive canonical subject content. An escaping evaluator exception is a model failure, not Unknown and not a catchable program error.
7. Initial cell content and constraint relations are checked when a version loads. Relevant relations are checked on cell writes. Activation and trial check staged content. Only Satisfied admits the operation.
8. Rejected writes and activations preserve the previous live state. Relation endpoints, owned-subtree subjects, and continuity remain unchanged.
9. Existing StateID, VersionID, canonical encoding, public behaviour and golden records remain unchanged.

No language-visible effects or external authority may be introduced merely by treating a constraint as a function.

## 3. Competing designs

### S – Existing dedicated evaluator

Control design. Keep the constraint semantic records, tree evaluator, node-count budget, three-valued result and named External evaluator mechanism.

Measure the existing independent machinery without counting each primitive class as a separate mechanism.

### A – Callable constraint values

Represent a constraint directly as a callable SHEAR function or closure returning a three-valued result.

Potential benefit: avoid a separate constraint tree interpreter.

Risks: ordinary Function values are not directly callable before installation; callable references are version-dependent; closure captures and execution context may affect meaning and identity. Runtime load must also evaluate constraints before a normal active runtime exists.

This design must preserve canonical constraint identity independently of callable deployment. A special constraint-call interface counts as additional machinery.

### B – Constraint data interpreted by ordinary functions

Retain immutable constraint data and canonical identity, but implement primitive dispatch, recursion and strong-Kleene composition as ordinary SHEAR functions.

Potential benefit: eliminate the constraint-specific evaluator and recursion engine.

Risks: the existing language offers tuple operations but no equivalent generic introspection of every canonical kind or role-map projection. A second interpreter hidden in Python does not qualify.

Ordinary function definitions implementing semantic logic are permitted. A distinct runtime dispatch engine for those functions counts as machinery.

### C – Constraint data compiled to functions

Retain constraint data as the source of identity. Translate it into ordinary function code using existing language and lowering infrastructure.

Potential benefit: replace repeated interpretation with reusable compiled computation.

Risks: translation, artifact ownership, evaluation environment and admission rules may introduce more fixed mechanisms than they remove. Compiled artifacts must remain derived from semantic content and must not change its identity.

A function-based implementation cannot win merely by relocating the existing evaluator into a compiler adapter.

## 4. Pre-registered predictions

P1 – `catch` and the existing depth limit alone cannot reproduce arbitrary constraint-node budgets. The depth limit counts pending calls, excludes tail calls and has no equivalent per-evaluation node budget. Discriminator: budget 0, 1, 2 and sufficient budgets over nested, short-circuited and tail-recursive evaluations. Falsification: exact equivalence using only existing generic mechanisms.

P2 – Design B requires either additional generic semantic-content operations or a special adapter for some existing primitives. Discriminator: IsKind across canonical kinds, Length across its supported kinds, and Role over canonical maps. Falsification: all run as ordinary functions with no new dedicated interface.

P3 – Design A cannot preserve the current canonical identity and evaluation independence merely by substituting a function reference for a constraint value. Discriminator: equal constraints under independently created functions, callable replacement, version changes and closure capture. Falsification: identity and results remain unchanged without an additional constraint-specific reference scheme.

P4 – Catching a generic execution limit does not by itself reproduce the external evaluator boundary. Discriminator: absent evaluator, evaluator returning Unknown, evaluator raising a host exception, and a surrounding language catch. Falsification: all cases preserve their existing distinctions with no duplicate external boundary.

P5 – Function-based checking needs a safe method of evaluation during initial version loading and candidate admission. Discriminator: a constraint that attempts a write, activation, recursion or effectful external call. Falsification: the current admission semantics hold using generic existing facilities, without a new constraint-only sandbox.

P6 – At least one candidate will need an additional generic operation, evaluation boundary or budget. This is a prediction to test, not permission to add it. Falsification: a candidate passes the complete corpus without those additions.

P7 – The experiment will not establish a strict mechanism reduction. This is the primary null prediction. Falsification: a candidate passes the independent oracle and the mechanism ledger shows a strict reduction.

Predictions cannot be silently rewritten after seeing results. A material correction requires an explicit Plan revision with its reason before a rerun, as required by the roadmap.

## 5. Mechanism accounting

Count independent fixed semantic or execution mechanisms, not classes, methods, lines of code, wrappers or duplicated source text.

An independent mechanism owns a distinct rule for interpreting, dispatching, budgeting, authorizing or transitioning computation. Moving such a rule between files does not remove it.

Baseline candidates for removal:

- M1: constraint-specific evaluation dispatch and recursive control.
- M2: constraint-specific node-budget accounting.
- M3: constraint-specific named External evaluation dispatch.
- M4: evaluator-specific host-failure provenance handling.

Baseline capabilities that must remain in some form and are not counted as savings merely because they move:

- canonical constraint content, construction and identity;
- strong-Kleene result semantics;
- runtime admission checks and rejection behaviour;
- relation subject construction and ownership semantics.

Count every new fixed mechanism, including:

- a generic execution-step budget;
- a generic external-authority boundary;
- new VM instructions or generic content operations;
- new execution isolation or purity enforcement;
- function compilation or translation adapters;
- constraint-only environments or dispatch;
- additional version, lifetime or artifact management;
- any retained duplicate of M1–M4.

A generic mechanism counts as one only if it genuinely serves ordinary computation with the same rules, rather than being a constraint-specific mechanism under a generic name.

The accounting has two distinct boundaries, specified in `docs/spikes/constraints_as_functions_mechanisms.md` section 6:

1. **Isolated candidate execution path.** Determine which incumbent mechanisms are used, duplicated, avoided or unresolved. Avoidance demonstrates possible removal but earns no removal credit by itself.
2. **Hypothetical migrated production architecture.** Account for all existing production consumers, retained mechanisms, replacements, compatibility adapters and newly required generic facilities. This is the scored counterfactual.

The migration must be specified concretely enough for independent verification, even though Execute must not replace the production implementation during the experiment.

A removal is credited only when that rule would genuinely cease to operate in the complete migrated architecture. Any surviving consumer or equivalent separately enforced replacement must be accounted for.

All additions necessary for the same migration are counted, even if they are not part of an isolated prototype.

The ledger must identify implementation and call sites for both removals and additions. An unresolved removal receives zero credit. Ordinary existing generic facilities reused without new fixed rules receive zero added cost.

Let R be verified removed independent mechanisms and A be added independent mechanisms, both in the same migrated architecture. Adoption requires R > A, with no surviving duplicate evaluator. At most one generic external-authority boundary and one generic execution budget are allowed by the roadmap. This allowance is not automatic evidence of reduction.

Record secondary costs separately: new instruction count, production branches, adapters, source size, execution time, memory, compilation and integration costs. Performance cannot substitute for the mechanism criterion.

## 6. Independent semantic oracle

The primary acceptance oracle must not compute expected answers by importing or calling the incumbent constraint evaluator.

Plan-owned files:

- `tests/constraint_function_oracle.py` – expected results, fixed vectors, independent strong-Kleene mathematics, generated cases and symbolic semantic-kind descriptors.
- `tests/constraint_function_acceptance.py` – candidate-facing input isolation and semantic grading.
- `tests/test_constraint_function_oracle.py` – control comparison and fixture validation.
- `tests/test_constraint_function_acceptance.py` – grader regression tests.

The fixed candidate-facing fixtures contain:

- All 15 currently canonical semantic kinds, including record kinds represented independently by `KindSample`.
- Existing primitives, boundary values and type-sensitive cases.
- Every binary AND and OR truth-table combination, all three NOT cases and empty compositions.
- Canonical repetition, operand-order and deduplication witnesses.
- Node-budget exhaustion, short-circuit precedence and sufficient-budget cases.

`KindSample` is descriptive input. Each execution adapter must materialize a genuine semantic value of the specified kind. The expected answer must not be derived from that materialization.

For strong Kleene logic, independently represent each result as a set of possible Boolean outcomes:

- Satisfied = {true}
- Violated = {false}
- Unknown = {true, false}

Apply Boolean operators pointwise to those sets. This provides an oracle independent of the evaluator's branching implementation.

For each generated seed, candidate acceptance includes both:

1. An unbudgeted, deterministically generated logical tree.
2. A budget-sensitive combination of primitives and composite constraints.

Generated cases retain reproducible seeds. The unbudgeted tree family has a deterministic shrinker. Generated budget fixtures are pinned by independently specified complete evaluation costs and outcomes.

The candidate callback receives only `CandidateInput`:

- expression;
- subject;
- budget;
- external configuration.

It does not receive the oracle expectation, fixture name or replay seed. The grader retains those independently.

A passing `Report.vector_passed` establishes only that the adapter returned acceptable semantic observations and declared an approved execution route. Reported execution-route and incumbent-call fields are not independent proof of those claims.

A candidate must execute real computation, not inspect test fixtures, call the control oracle or return known answers. Independent instrumentation and path inspection remain mandatory.

Comparison with the existing `Constraint.evaluate` implementation is secondary differential evidence, not the primary oracle.

A shared helper that invokes the same production predicate implementation for both expected and actual results is prohibited.

## 7. Acceptance matrix

Each candidate must be evaluated against the same frozen cases:

T1. All three truth values, every AND/OR/NOT combination, empty composition, nested composition, canonical deduplication and order independence.

T2. All existing primitives, canonical subject kinds, boundary values, malformed inputs, missing roles and type-sensitive equality.

T3. Budget 0, 1, 2, sufficient and unbounded; short-circuit precedence; deterministic consumption; no unsupported decisive result.

T4. External evaluator absent, decisive, Unknown, exception-raising and non-terminating. A non-terminating external is a documented limitation of the incumbent budget, not evidence of general termination control.

T5. Canonical identity, round-trip encoding, reconstruction, constraint-as-data, program and version identity across evaluations and ordinary edits.

T6. Initial cell and relation checks, successful and rejected writes, staged activation, trial, rename continuity, owned-subtree evaluation and atomic rejection.

T7. Failure provenance and catch boundaries, including the distinction among limit status, Unknown, runtime rejection and host failure.

T8. All existing semantic and language corpora through the affected boundary; unchanged golden records and public APIs.

T9. Adversarial candidate functions attempting effects, accessing mutable state or depending on their deployment version.

### 7.1 Candidate-facing integration contract

The Plan-owned executable boundary contract is:

`tests/constraint_function_boundary_acceptance.py`

Its grader regression tests are:

`tests/test_constraint_function_boundary_acceptance.py`

The contract contains **17 mandatory candidate-facing scenarios**:

- The original 14 frozen boundary witnesses, retaining their names, scripts and expected behaviours.
- Three additional successful admission cases: `write_satisfied`, `activation_satisfied` and `trial_satisfied`.

The original boundary witnesses cover:

- escaping host exceptions and the language `catch` boundary;
- missing External evaluators;
- rejected initial content, writes and relation checks;
- rejected activation and trial with unchanged live state;
- owned-subtree canonical subjects;
- canonical identity independent of evaluation context;
- call-depth and tail-recursion behaviour;
- unauthorized effects during constraint evaluation;
- constraint identity across version changes.

The `owned_subtree` expectation is the exact tagged canonical representation of a relation subject containing an owned child. Comparison preserves the tags, nesting, map-entry ordering and primitive types. Only the reference model's `CanonicalNode` tuple-subclass distinction is ignored. The expected representation is specified independently rather than computed from the incumbent canonicalizer during grading.

The three successful admission scenarios additionally require:

1. **`write_satisfied`** – A cell initially containing `0` and constrained to the integer range 0–10 accepts a write of `7`. The operation completes with Satisfied, live content becomes `7`, the active version does not change, and the live runtime state changes through cell content.

2. **`activation_satisfied`** – A cell constrained to the integer range 0–10 is written with `4`. A one-to-one activation widens its constraint to 0–100 while preserving content. The activation completes with Satisfied, the active version changes, and live content remains `4`.

3. **`trial_satisfied`** – The same initial cell and content are used with an isolated trial of the widened constraint. The trial completes with Satisfied, the main runtime remains unchanged by the trial, its active version does not change, and the trial's new runtime contains `4` under the staged destination state.

Each `BoundaryCase` specifies input operations and an independently frozen `BoundaryExpected`.

For successful admissions, the expected observations additionally pin `live_cells`, `trial_cells`, `active_version_changed` and `trial_version_matches_staged`, as applicable.

`state_unchanged` compares the live runtime state immediately before and after the final requested operation, including live cell content and active version. Therefore a successful write changes live state without changing the active version, whereas a successful trial leaves the main runtime unchanged.

Execute supplies a `BoundaryCandidate` adapter accepting only `BoundaryInput`, containing the operation script. It must execute the candidate through the corresponding runtime or language boundary and return a `BoundaryObservation`.

The adapter may not inspect expected observations, redefine the script's meaning, replace runtime transitions with direct predicate calls or use the incumbent evaluator as fallback.

`assess_boundaries` compares every frozen expected observation field, including status, semantic outcomes, state preservation, live and trial contents, version transitions, catch behaviour, side effects, canonical subjects and identity.

Unsupported scripts, exceptions, wrong execution routes, incumbent fallback and any observation mismatch fail grading.

**Full acceptance requires the complete frozen inventory**, including all 17 original case names, scripts, expected observations and their order. A subset, duplicated cases, reordered cases or altered expectations cannot produce a full acceptance pass even if their individual observations match.

The grader's declared route and fallback count remain subject to independent instrumentation, just as in the semantic-vector harness. A passing report is not, by itself, evidence of genuine candidate execution.

### 7.2 Additional required evidence

The two candidate-facing graders are necessary but not sufficient.

Execute must also demonstrate every remaining T1–T9 obligation not completely exercised by the frozen cases, including malformed-input handling, round-trip encoding, rename continuity, non-terminating externals, further successful transitions beyond the three pinned cases and existing full corpora.

Such evidence must be checked against the existing normative specifications and Plan-owned expected behaviour. Execute may add implementation tests and instrumentation, but cannot weaken or replace Plan-owned expectations.

A newly introduced general computation layer must run the existing corpora through that layer; the incumbent remaining green is not sufficient.

The candidate must distinguish unsupported functionality from incorrect results. A fallback to the existing dedicated evaluator cannot count as candidate success.

## 8. Experiment procedure

1. Freeze this contract, fixtures, candidate-facing acceptance infrastructure and mechanism-count taxonomy in the revised Plan head.
2. Obtain a control run on the current baseline using the existing tests and a documented mechanism ledger.
3. Implement bounded isolated versions of B and C, without changing the production constraint path. Evaluate A with explicit identity and execution witnesses; implement it only if those obstacles are resolved within the declared boundary.
4. Connect each candidate to the frozen semantic-vector and boundary graders. Run every mandatory case without weakening, replacing or silently skipping expectations.
5. Run remaining T1–T9 checks and all applicable corpora through the candidate computation layer. Record failures, unsupported operations and counterexamples.
6. Independently instrument evaluator fallbacks, authorization boundaries and effect isolation. Inspect full execution paths, not just adapter-reported metadata.
7. Record the isolated-path ledger and the complete migrated-production counterfactual. Audit each proposed removed, retained, added or shared mechanism.
8. Compare observations with the frozen predictions and classify every mismatch by semantics, missing capability, implementation defect or resource limit.
9. Record adopt or kill with the evidence and exact mechanism ledger. If none qualifies, retain the existing architecture.

The bounded experiment must not grow into an unrestricted implementation project. If a candidate needs undeclared language semantics, change the Plan before continuing it.

A prototype that fails a semantic discriminator is rejected as a replacement. Do not weaken that discriminator or change the canonical contract to make it pass.

## 9. Owner decisions reserved

D24-1 – Preserve constraint values as independent canonical semantic data, or allow callable identity to become normative.

Recommendation: preserve the existing identity contract for this experiment. Treat direct callable substitution as a competing hypothesis, not an approved redesign.

D24-2 – Permit a genuinely generic fuel budget and external-function invocation boundary if existing operations prove insufficient.

Recommendation: permit bounded prototypes for measurement, but require explicit owner approval before adding either mechanism to the language or VM.

D24-3 – Adoption scope.

Recommendation: a successful experiment establishes a migration recommendation. It does not authorize Execute to silently replace public semantics or discard canonical constraints. Any material language change returns to Plan.

All other implementation choices are Provisional within these boundaries.

## 10. Plan and Review responsibilities

Plan owns this pre-registration, the independent fixtures, semantic and boundary acceptance contracts, their regression tests, test-lane registration and any explicitly necessary golden declarations.

The intended golden-change set is empty. No `tests/golden_changes/GH-56.txt` is required unless the owner explicitly authorizes an identified semantic change through Plan.

Execute owns experimental candidate implementations, candidate-specific integration adapters, reproducible observations and the actual mechanism ledger. It must not change Plan-owned expectations or specifications. It must record whether a failure is an implementation defect or evidence against a design.

Review independently reproduces key semantic and integration counterexamples, verifies oracle independence, checks execution routes and side effects, audits the complete migration mechanism count and checks the final verdict against frozen criteria.

The outcome is not assumed. Preserve the existing implementation if the experiment is killed. Document discovered architectural questions as separate follow-ups instead of enlarging Task 24.

After the Plan corrections are committed and reviewed, the revised final Plan commit is pinned in `handoff.md`. Execute must start from that revised Plan head, not the obsolete `e2f87fa` checkpoint.
