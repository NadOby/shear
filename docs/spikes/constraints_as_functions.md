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

The ledger must identify each proposed removal by its old implementation site and each addition by its new implementation site. It must show that removed mechanisms are actually absent, not hidden behind wrappers.

Let R be removed independent mechanisms and A be added independent mechanisms. Adoption requires R > A, with no surviving duplicate evaluator. At most one generic external-authority boundary and one generic execution budget are allowed by the roadmap. This allowance is not automatic evidence of reduction.

Record secondary costs separately: new instruction count, production branches, adapters, source size, execution time, memory, compilation and integration costs. Performance cannot substitute for the mechanism criterion.

## 6. Independent semantic oracle

The primary acceptance oracle must not compute expected answers by importing or calling the incumbent constraint evaluator.

Use fixed, independently reasoned fixtures for primitives, evaluation order, budgets and admission transitions.

For strong Kleene logic, independently represent each result as a set of possible Boolean outcomes:

- Satisfied = {true}
- Violated = {false}
- Unknown = {true, false}

Apply Boolean operators pointwise to those sets. This provides an oracle independent of the evaluator's branching implementation.

Include deterministic generated trees, fixed seeds and reproducible shrinking or minimal counterexamples.

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

The candidate must distinguish unsupported functionality from incorrect results. A fallback to the existing dedicated evaluator cannot count as candidate success.

A newly introduced general computation layer must run the existing corpora through that layer; the incumbent remaining green is not sufficient.

## 8. Experiment procedure

1. Freeze this contract, fixtures, oracle and mechanism-count taxonomy in the Plan head.
2. Obtain a control run on the current baseline using the existing tests and a documented mechanism ledger.
3. Implement bounded isolated versions of B and C, without changing the production constraint path. Evaluate A with explicit identity and execution witnesses; implement it only if those obstacles are resolved within the declared boundary.
4. Run all applicable fixtures for each design, preserving failures and counterexamples rather than modifying expectations.
5. Independently audit every claimed removed or added mechanism. Inspect the full execution path for Python fallback, duplicated dispatch, special-case handling and forbidden effects.
6. Compare results with the frozen predictions and classify every mismatch by semantics, missing capability, implementation defect or resource limit.
7. Record adopt or kill with the evidence and exact mechanism ledger. If none qualifies, retain the existing architecture.

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

Plan owns this pre-registration, the independent fixtures and acceptance tests, test-lane registration and any explicitly necessary golden declarations.

The intended golden-change set is empty. No `tests/golden_changes/GH-56.txt` is required unless the owner explicitly authorizes an identified semantic change through Plan.

Execute owns experimental candidate implementations, reproducible observations and the actual mechanism ledger. It must not change Plan-owned expectations or specifications. It must record whether a failure is an implementation defect or evidence against a design.

Review independently reproduces the key semantic counterexamples, verifies oracle independence, checks that removed mechanisms really disappeared, audits the mechanism count, and checks the final verdict against the frozen criteria.

The outcome is not assumed. Preserve the existing implementation if the experiment is killed. Document discovered architectural questions as separate follow-ups instead of enlarging Task 24.

After the Plan files are committed, the final Plan commit is pinned in `handoff.md`. Execute starts from that exact commit, not from this provisional document alone.
