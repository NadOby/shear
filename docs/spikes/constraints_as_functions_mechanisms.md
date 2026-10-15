# Task 24 – Mechanism Accounting

**Status: Provisional – pre-registered accounting baseline.**

Issue: GH-56. Control: `main` at `697b2d7`.

Companion: `docs/spikes/constraints_as_functions.md`.

This ledger identifies accounting boundaries before experimental
implementation. It is not evidence that any mechanism was removed.

## 1. Counting rule

One mechanism is one independently enforced semantic or execution
rule requiring fixed implementation machinery.

Count a rule once even when it spans multiple files. Count it
again only when a candidate retains an independently operating
duplicate.

Renaming, wrapping, generating or moving code does not remove a
mechanism. Ordinary functions implementing constraint logic are
not themselves new fixed mechanisms.

Record mechanisms as removed, retained, added or shared.
A claimed removal requires an execution-path audit.

## 2. Existing constraint-specific mechanisms

M1 – Dedicated constraint execution.

- `shear/constraints.py`: `Constraint._evaluate`, `_check`
  implementations and composite traversal.
- Counts as one constraint-specific dispatch and control mechanism.
- Removed only if all evaluation follows ordinary SHEAR
  computation without a hidden dedicated interpreter.

M2 – Constraint-node budget.

- `shear/constraints.py`: `_Evaluation.step`.
- Counts as one independent resource-accounting mechanism.
- Removed only if a generic budget reproduces the required
  observable results, including budget-sensitive short circuits.

M3 – Named external evaluation.

- `shear/constraints.py`: `External._check` and
  `EvaluationContext.externals`.
- Counts as one external-authority dispatch mechanism.
- Removed only if the same authority boundary is available
  generically and the constraint-specific lookup disappears.

M4 – Escaping host-failure provenance.

- `shear/constraints.py`: `_HOST_FAILURES`,
  `_record_host_failure`, `_is_host_failure`.
- `shear/machine.py`: distinction between evaluator exceptions
  and catchable program failures.
- Potentially shared with generic error handling.
- Do not claim removal unless that distinction remains enforced
  by an existing generic mechanism, without duplicate tracking.

The provisional maximum removable set is M1–M4.
It is not an assertion that all four can actually be removed.

## 3. Required mechanisms that are not savings

N1 – Canonical constraint identity and construction.

- `Constraint.canonical_node`, `Constraint.from_content` and
  canonical serialization remain necessary under this Plan.

N2 – Three-valued result semantics.

- Satisfied, Violated and Unknown remain distinguishable.
- Strong-Kleene semantics remain mandatory.
- Rewriting logic as ordinary functions is not, by itself,
  removal of these semantic requirements.

N3 – Runtime admission.

- `shear/runtime.py`: `_check_content`,
  `_failed_constraint_relation`, staged admission and rejection.
- Only Satisfied permits admission.
- Atomic rejection remains mandatory.

N4 – Relation subjects and ownership.

- `shear/relations.py`: role subject formation.
- `shear/runtime.py`: endpoint and owned-subtree content.
- A candidate must preserve these semantic subjects.

N5 – Canonical content and version identity.

- StateID and VersionID cannot become dependent on evaluation,
  compilation artifacts or callable deployment.

Eliminating any N-series requirement by changing semantics does
not qualify as a successful experiment.

## 4. Existing general-purpose facilities

G1 – Ordinary function calls and closures.

- `shear/lang.py`, `shear/machine.py`.

G2 – `catch`, `raise` and tagged execution failures.

- `shear/machine.py`, `docs/error_handling.md`.

G3 – Call-depth refusal.

- `shear/bytecode.py`: `CALL_DEPTH_LIMIT`.
- Counts pending calls, not evaluated constraint nodes.
- Tail recursion does not consume this budget.

G4 – Graph-form operations and bytecode lowering.

- `shear/operations.py`, `shear/bytecode.py`.

G5 – Runtime versions and admitted executable artifacts.

- `shear/runtime.py` and the hosted bootstrap implementation.

Reusing an existing G-series facility without modifying its
fixed semantics costs zero additions. Extending it with an
independent rule counts as an addition even when generically
named.

## 5. Candidate accounting obligations

### A – Callable constraints

Record:

- canonical identity independent of function reference;
- callable validity before a version is active;
- effect isolation and authority;
- any new callable adapter or special execution boundary;
- any retained M-series mechanisms.

Replacing a semantic constraint with an ordinary function
reference is not allowed to evade the identity test.

### B – Interpretation by SHEAR functions

Record:

- semantic-content inspection and kind introspection;
- canonical map and role access;
- primitive evaluation and recursion;
- node-budget equivalence;
- external calls and host-failure handling;
- any Python fallback or constraint-only environment.

A Python dispatcher calling SHEAR functions around each
constraint node still retains M1.

### C – Compilation into SHEAR functions

Record:

- constraint-to-code translation;
- generated code identity and caching;
- compilation and admission before initial runtime load;
- execution isolation and budgets;
- derived artifact lifetime and version ownership;
- all retained mechanisms from the control design.

Compilation does not count as mechanism removal when a
constraint-specific dispatcher remains necessary.

## 6. Ledger format for Execute

For each candidate, record:

| Field | Required evidence |
| --- | --- |
| Baseline | Existing sites and rules |
| Removed | Rule absent from complete execution path |
| Retained | Existing rule still independently enforced |
| Added | New fixed rule and implementation site |
| Shared | Existing general-purpose rule, unchanged |
| R | Number of verified removed mechanisms |
| A | Number of verified added mechanisms |
| Net | R minus A |
| Semantics | Independent acceptance results |
| Result | Adopt or kill, with explanation |

Do not compute R from planned deletions or A from file counts.

Shared rules count neither as removals nor additions unless
their implementations genuinely change.

## 7. Decision rule

A candidate qualifies only when:

1. Every mandatory semantic and boundary discriminator passes.
2. No production evaluator fallback masks an unsupported case.
3. Every claimed removal is confirmed by independent inspection.
4. R is strictly greater than A.
5. There is at most one generic external-authority boundary and
   at most one generic execution budget.
6. The candidate introduces no unapproved normative language change.

An unresolved mechanism is not counted as removed.

Performance, reduced source size and fewer Python classes may be
reported separately but cannot overturn a failed mechanism test.

If no candidate qualifies, record **kill** and retain the existing
architecture. The experiment is successful as evidence even when
the proposed replacement is rejected.

## 8. Evidence status

The baseline implementation sites above have been inspected.

No candidate implementation, mechanism elimination or experimental
result is claimed by this Plan document.

Execute must populate a result ledger after implementing bounded
candidates. Review independently validates the sites, counts,
semantic evidence and adopt-or-kill conclusion.
