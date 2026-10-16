# Handoff

Read `CLAUDE.md`, the Workflow section and Task 24 in
`docs/roadmap.md`, issue #56, and the two experiment documents.
Verify this checkpoint against GitHub before relying on it.

## Current state

- Task: 24 – constraints as functions.
- Issue: GH-56, https://github.com/NadOby/shear/issues/56.
- Branch: `task/24-constraints-as-functions`.
- Role: Plan – prepared for independent execution.
- Baseline main: `697b2d73b538ad38b57f12beffd7724fda64a871`.
- Plan head: `e2f87fa07d37ca3b7d3ceca8b0c8cb28a3abcaa6`.
- The next commit updates only this handoff.
- No production implementation or experimental candidate exists.
- No adopt-or-kill verdict has been reached.
- Ordinary CI and mutation results are not yet verified for this branch.
- The user has not requested Execute yet.

## Goal and decision rule

Determine whether expressing semantic constraints through ordinary
SHEAR functions strictly reduces the number of independent fixed
mechanisms while preserving observable semantics.

The null hypothesis is that no candidate achieves both requirements.

Adopt only if:

1. Independent semantic and boundary acceptance passes.
2. The complete execution path has no hidden incumbent fallback.
3. Independently verified removed mechanisms outnumber additions.
4. No more than one generic external-authority boundary and one
   generic execution budget remain.
5. No unapproved normative language changes are required.

Otherwise record kill and retain the existing constraint evaluator.

A valid negative result completes the experiment.

## Plan-owned specifications

- `docs/spikes/constraints_as_functions.md`
  - Competing designs A, B, C and incumbent S.
  - Pre-registered falsifiable predictions P1–P7.
  - Semantic invariants, acceptance matrix T1–T9.
  - Experiment procedure, kill criterion and reserved decisions.

- `docs/spikes/constraints_as_functions_mechanisms.md`
  - Independent-mechanism accounting.
  - Baseline M1–M4, retained requirements N1–N5.
  - Existing generic facilities G1–G5.
  - Required implementation-site evidence and accounting ledger.

Both are Provisional experiment specifications, not a change
to existing Decided language semantics.

## Plan-owned test infrastructure

- `tests/constraint_function_oracle.py`
  - Independently fixed primitive and budget cases.
  - Mathematical strong-Kleene oracle.
  - Deterministic generated trees and shrinking.
  - Runtime-boundary witness inventory.

- `tests/constraint_function_acceptance.py`
  - Candidate adapter and vector acceptance harness.
  - Explicit reporting of semantic mismatches, unsupported routes,
    fallback calls and reproducible generated failures.
  - A passing vector report does not establish full adoption.

## Plan-owned acceptance tests

- `tests/test_constraint_function_oracle.py`
  - Mathematical truth-table properties, fixed vectors and
    independently generated expectations against the control.

- `tests/test_constraint_function_acceptance.py`
  - Harness validation using test doubles, including failure
    propagation, fallback detection and replay reporting.

- `tests/test_constraint_function_boundaries.py`
  - Unknown during load, write, relation checking, activation
    and trial; state preservation, owned-subtree subjects,
    budget boundaries and identity independence.

- `tests/lanes.py`
  - All three test modules assigned to `core-model`.

Existing acceptance coverage also includes:
`tests/test_constraints.py`,
`tests/test_constraint_relations.py`,
`tests/test_runtime.py`, and
`tests/test_error_handling.py`.

The complete existing corpora must be run through any newly
introduced computation layer. Green incumbent tests alone do not
qualify a candidate.

## Frozen invariants

- Constraint values have canonical identity independent of
  evaluation resources, installed functions and versions.
- Three-valued results obey strong Kleene composition.
- Unknown is neither Violated nor execution failure.
- Existing primitive behaviour, canonical subject handling,
  set composition and constraint-node budgets remain unchanged.
- Missing External evaluators yield Unknown.
- Escaping evaluator exceptions remain model failures and are
  not converted into catchable program errors.
- Only Satisfied permits admission.
- Rejected writes, activation and trial preserve live state.
- Relation subjects include required endpoints and owned subtrees.
- State, version, reference and public language semantics remain
  unchanged.

No golden changes are planned or authorized.

## Competing designs

S – retain the existing constraint evaluator as control.

A – directly callable constraint values; must first resolve
canonical identity and pre-activation evaluation without
special-case machinery.

B – retain canonical constraint data and interpret it using
ordinary SHEAR functions.

C – compile canonical constraint data to ordinary functions,
accounting for translation, artifact lifetimes and admission.

Primary bounded implementation experiments are B and C.
Assess A with concrete identity and execution witnesses before
investing in a full prototype.

## Execution procedure

1. Verify the frozen Plan head and run the new acceptance tests.
2. Establish baseline control results and mechanism sites.
3. Implement isolated, bounded candidates; do not silently
   redirect the production constraint path.
4. Connect each candidate to the frozen acceptance harness.
5. Run independent vectors and adversarial boundary scenarios.
6. Test the existing corpora through any new execution layer.
7. Measure execution routes and independently establish that
   no dedicated evaluator fallback was used.
8. Record removed, retained, added and shared mechanisms.
9. Compare observations to pre-registered predictions P1–P7.
10. Record adopt or kill, including failures and counterexamples.

Do not repair candidate failures by weakening Plan-owned
expectations or changing the normative semantic contract.

If the experiment needs new language semantics, return to Plan
and the owner before implementing them.

## Decisions reserved for the owner

D24-1 – Canonical constraint values versus function identity.

Recommendation: preserve canonical constraint identity.
Do not make callable identity normative in Execute.

D24-2 – Generic execution budget and external boundary.

Recommendation: allow bounded experimental prototypes,
but require explicit owner approval before normative VM
or language additions.

D24-3 – Meaning of an experimental success.

Recommendation: success authorizes an adoption recommendation,
not an automatic production migration.

These remain Provisional recommendations. Execute cannot decide
a material normative language change alone.

## Verification status and gaps

GitHub commits and Plan file contents were checked individually
during preparation.

No Task 24 candidate implementation has been executed.
No experimental claim is verified.
No complete CI result has been established for this branch.

The Plan boundary tests pin representative incumbent behaviour.
Candidate-specific integration and adversarial effects tests,
including initial-load execution, version coupling, escaping
exceptions under catch, non-termination and isolation, must be
completed and assessed before an adoption verdict.

The candidate adapter's reported incumbent-call count is not
itself proof of independence. Review must inspect and instrument
the actual execution path.

A nonblocking test-runner cleanup remains: `tests/lanes.py`
calls `future.result()` twice for the same completed future.
It is functionally equivalent, but Review may request restoring
the single tuple unpacking.

## Independent Review obligations

Verify independently:

1. Every P1–P7 prediction is assessed against observed evidence.
2. Frozen expectations are independent of the candidate code.
3. No hidden Python evaluator or special environment substitutes
   for genuinely ordinary function execution.
4. Runtime admission, effects, budgets, host failures and
   canonical identities preserve the recorded semantics.
5. Every claimed mechanism removal is real and independently
   counted; additions include generic mechanisms and adapters.
6. No golden records or public behaviour were changed silently.
7. CI, corpora, replayable failures and relevant mutation
   evidence support the reported results.
8. The adopt-or-kill decision follows the frozen criteria.

## Next step

Plan stops here. Do not Execute without a separate instruction.

Start the later Execute role in a fresh chat from the frozen
Plan head identified above, using this handoff as a checkpoint
rather than as verification evidence.
