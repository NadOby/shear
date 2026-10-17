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
A claimed removal requires an execution-path audit and the
migration counterfactual in section 6.

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

## 6. Two accounting boundaries and the migration counterfactual

### 6.1 Isolated candidate path – evidence, not the score

Execute initially develops candidates alongside the production
constraint evaluator. Therefore the current repository will
still contain M1–M4 during the experiment.

For each candidate, identify its complete isolated execution
path, including translation, construction, evaluation, runtime
admission and failure handling.

Classify each baseline mechanism on that path as:

- **Used:** the candidate invokes the incumbent rule.
- **Duplicated:** an independently operating equivalent exists.
- **Avoided:** the candidate path demonstrably does not use it.
- **Unresolved:** its use or absence cannot be established.

Avoiding M1–M4 in an isolated prototype is necessary evidence,
but does not itself constitute a production mechanism removal.

Do not award R for a mechanism merely because a test adapter
does not call it, or because an experimental code path bypasses
it while the production architecture still requires it.

### 6.2 Hypothetical migrated production architecture – scored

The adoption score compares two architectures serving the
same complete obligations:

- **Control:** production architecture at baseline `697b2d7`,
  with M1–M4 and the N/G requirements.
- **Migration:** the fully specified architecture that would
  replace the incumbent evaluator with the tested candidate,
  while preserving the existing public interfaces, semantics,
  admission paths, identity and other users of these facilities.

The migration need not be implemented in production during
this experiment. It must, however, be specified concretely
enough for an independent reviewer to establish which fixed
mechanisms would remain, disappear or be added.

For every proposed removal:

1. Identify the original implementation sites and all known
   production call sites and consumers.
2. Explain how each consumer would be served after migration.
3. Identify the exact old rules that can cease operating,
   including any dispatch, budget, lookup or provenance state.
4. Identify all replacements, bridges and initialization paths.
5. Verify the corresponding behaviour using candidate-facing
   semantic and boundary acceptance evidence.
6. Confirm that no other supported production path still needs
   the allegedly removed independent mechanism.
7. Record whether this is verified, disproved or unresolved.

A counterfactual removal receives credit only when the complete
migration argument is auditable and supported by passing
candidate evidence. An illustrative deletion plan, a diagram
alone, or absence from the isolated path is insufficient.

If other production consumers would still require the original
mechanism, classify it as retained. If a migration-specific
replacement enforces an equivalent rule independently, count
that replacement under additions; do not silently treat it as
an unchanged generic facility.

If the counterfactual cannot be verified, give the mechanism
zero removal credit. Do not assume an optimistic migration.

### 6.3 Additions and shared mechanisms

Count additions in the same migrated architecture, not just
inside the candidate's evaluator function.

Include all new fixed rules needed for:

- existing public runtime and language interfaces;
- canonical data-to-function translation and caching;
- evaluation before a runtime or version becomes active;
- invocation, authorization and external callbacks;
- generic or specialized fuel accounting;
- host-failure separation from catchable program failures;
- effect isolation and state preservation;
- version dependence and artifact lifetime;
- canonical content inspection and reconstruction;
- compatibility adapters for remaining production consumers.

An adapter is not automatically one independent mechanism.
Count the fixed rule it introduces, not each wrapper or class.
Equally, a small adapter is not free if it enforces a new rule.

An existing G-series facility is shared at zero added cost
only if the migration reuses its present fixed rules unchanged.
A general-purpose extension introducing independent fixed
semantics must be counted under additions.

A baseline rule relocated into an independently operating
replacement cannot be claimed as a free removal.

The same migration counterfactual must be used for R and A.
Do not score removals assuming a fully migrated architecture
while scoring additions from an isolated prototype.

### 6.4 Required accounting evidence

For each M-series mechanism, provide:

| Field | Required evidence |
| --- | --- |
| Baseline | Rule and current implementation/call sites |
| Candidate path | Used, duplicated, avoided or unresolved |
| Migrated consumers | Where every incumbent caller would go |
| Migration disposition | Removed, retained, shared or unresolved |
| Replacement | Exact fixed rules and implementation sites |
| Confidence | Verified, disproved or unresolved |
| Removal credit | One only when verified; otherwise zero |

For each added mechanism, provide its migrated consumers,
fixed rule, planned implementation sites, evidence that it
is genuinely new, and whether it is generic or specialized.

The migration analysis is falsifiable: one surviving production
consumer of the old rule, or one uncounted replacement rule,
invalidates the corresponding accounting claim.

## 7. Result ledger for Execute

For each candidate, record:

| Field | Required evidence |
| --- | --- |
| Baseline | Existing sites and rules |
| Candidate path | Complete call path and incumbent use |
| Migrated architecture | Proposed full replacement and call sites |
| Removed | Verified counterfactual removal, not mere bypass |
| Retained | Rules still independently enforced after migration |
| Added | All new fixed rules needed by the migration |
| Shared | Existing generic rules reused without extension |
| R | Number of verified migrated-architecture removals |
| A | Number of migrated-architecture additions |
| Net | R minus A |
| Semantics | Independent candidate acceptance results |
| Result | Adopt or kill, with explanation |

Do not compute R from planned deletions or A from file counts.

Shared rules count neither as removals nor additions unless
their implementations genuinely change.

Report unresolved entries explicitly. They receive no removal
credit; missing evidence must not produce a favorable net score.

## 8. Decision rule

A candidate qualifies only when:

1. Every mandatory semantic and boundary discriminator passes.
2. No incumbent evaluator fallback masks an unsupported case.
3. Every claimed removal is verified in the migrated-production
   counterfactual, not merely absent from the isolated prototype.
4. All additions required by that same counterfactual are counted.
5. R is strictly greater than A.
6. There is at most one generic external-authority boundary and
   at most one generic execution budget.
7. The candidate introduces no unapproved normative language change.

An unresolved mechanism is not counted as removed.

Performance, reduced source size and fewer Python classes may be
reported separately but cannot overturn a failed mechanism test.

If no candidate qualifies, record **kill** and retain the existing
architecture. The experiment is successful as evidence even when
the proposed replacement is rejected.

## 9. Evidence status

The baseline implementation sites above have been inspected.

No candidate implementation, mechanism elimination or experimental
result is claimed by this Plan document.

Execute must populate the candidate-path and migrated-architecture
ledgers after implementing bounded candidates. Review independently
validates the sites, counts, semantic evidence and adopt-or-kill
conclusion.
