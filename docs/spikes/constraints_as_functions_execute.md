# Task 24 – Execute Evidence and Mechanism Audit

**Status: Execute complete – proposed kill; independent Review pending.**

Issue: GH-56.
Branch: `task/24-constraints-as-functions`.
Evidence head: `a2d2553`.
Frozen Plan: `97e4297`.
Control baseline: `697b2d7`.

This document records the bounded experiment's negative result. It
does not change the frozen Plan, semantic requirements or acceptance
expectations.

## 1. Verification

GitHub Actions run `38974990376` passed at `a2d2553`.

Verified CI steps:

- All registered semantic test lanes passed.
- Experimental A, B and C probes passed.
- Full frozen rejection-grader tests passed.
- Golden-record comparisons passed.

The passing experimental tests establish that the observations and
expected disqualifications occurred. They do not establish that a
candidate meets the complete semantic or boundary contract.

Production constraint evaluation remains unchanged. The Plan-owned
oracle, graders, specifications and test-lane registration were not
modified during Execute.

## 2. Candidate A – callable constraint substitution

Implementation:
`tests/constraint_function_a_probe.py`.

The seven executable witnesses establish that:

- Arbitrary Python callables are not canonical semantic values.
- `Function` and `EntityID` are not accepted as cell constraints.
- Different deployment references affect state identity.
- Function bodies can differ in identity despite equal results.
- Ordinary function execution requires a loaded runtime.
- Initial runtime admission invokes constraint evaluation before
  ordinary function execution.
- An External constraint's canonical identity is independent of
  its evaluator configuration.

These observations support prediction P3 and the bootstrap concern
in P5.

They demonstrate obstacles to direct substitution. They do not prove
that every possible callable-based architecture is impossible.

Preserving canonical constraint identity would require separating
semantic constraint data from callable deployment, or introducing
another identity-preserving interface.

A complete A candidate was not implemented because direct
substitution failed the prerequisite identity and execution
discriminators within the bounded experiment.

**A verdict: kill direct callable substitution under this Plan.**

## 3. Candidate B – interpretation using ordinary functions

Implementation:
`tests/constraint_function_b_probe.py`.

The positive witness executes an ordinary SHEAR function over
tuple-form data through the existing VM.

The negative witnesses establish missing generic capabilities:

- `item` cannot inspect canonical constraint payloads.
- `item` cannot project canonical map contents.
- `len` does not implement Length for every supported semantic kind.

The implementation boundary is `shear/machine.py::_items`, which
supports ordinary tuples and canonical tuple nodes, not every
canonical node.

The rejection adapter in
`tests/constraint_function_disqualification_probe.py` attempts to
materialize genuine constraints and project them through ordinary
SHEAR execution.

It cannot implement the required canonical constraint interpreter.
Unsupported cases fail explicitly, with no incumbent fallback.

The complete semantic grader was invoked with its default 100
generated seeds per family, in addition to all fixed vectors.
The resulting candidate report is non-passing.

All 17 frozen boundary cases were submitted to the boundary grader.
Every script was explicitly rejected because no candidate-integrated
runtime admission path exists.

These are recorded failures, not successful boundary executions.

**B verdict: kill the bounded interpreter as a replacement.**

## 4. Candidate C – compilation into ordinary functions

Implementation:
`tests/constraint_function_c_probe.py`.

Candidate computation follows:

`CandidateInput` → `materialize` → canonical constraint value →
`Compiler.compile` → generated Function → `load` → Runtime → `run`.

The prototype generates executable SHEAR bodies for:

- OneOf.
- Not.
- AllOf.
- AnyOf.

The generated code executes through existing VM operations.
Canonical operand normalization and existing semantic equality
are reused.

The prototype lacks:

- IsKind, IntRange, Length and Role compilation.
- Constraint-node budget equivalence.
- Named External evaluation and its failure boundary.
- Candidate-integrated initial load, writes, activation and trial.
- Version-independent artifact ownership and pre-activation execution.
- Demonstrated effect isolation for constraint evaluation.

Unsupported requirements raise explicit errors.

The candidate was evaluated against all fixed semantic vectors and
the full default generated campaign. Its report is non-passing.

All 17 frozen boundary scripts were submitted to the grader and
explicitly rejected as unsupported. No candidate-integrated runtime
transition was executed by this boundary adapter.

The reported execution route and fallback count are adapter claims.
The probe also blocks the incumbent `Constraint.evaluate` entry point
during selected tests, but this is not complete independent
instrumentation of every possible evaluation path.

**C verdict: kill the bounded compiler as a replacement.**

## 5. Frozen acceptance results

| Requirement | A | B | C |
| --- | --- | --- | --- |
| Canonical identity prerequisite | Direct substitution fails | Preserved as separate data | Preserved as separate data |
| Complete fixed semantic matrix | No adapter | Fail | Fail |
| Full generated semantic campaign | No adapter | Fail | Fail |
| Boundary inventory submitted | No adapter | 17 of 17 | 17 of 17 |
| Boundary scripts actually executed through candidate integration | 0 | 0 | 0 |
| Complete boundary acceptance | Fail | Fail | Fail |
| Full node-budget equivalence | Not demonstrated | Missing | Missing |
| External authority and host-failure equivalence | Not demonstrated | Missing | Missing |
| Verified production replacement | None | None | None |

A passing test of an expected rejection is not a passing candidate
acceptance result.

Unsupported scenarios were not silently skipped or replaced with
incumbent results. They were classified as candidate failures.

Because no candidate passes mandatory semantic and boundary
discriminators, no candidate is eligible for adoption.

## 6. Production mechanism baseline

The frozen counting taxonomy identifies four potentially removable
mechanisms.

| ID | Baseline mechanism | Implementation |
| --- | --- | --- |
| M1 | Constraint-specific execution | `Constraint._evaluate`, `_check`, composite traversal |
| M2 | Constraint-node budget | `_Evaluation.step` |
| M3 | Named External dispatch | `External._check`, `EvaluationContext.externals` |
| M4 | Escaping host-failure provenance | `_HOST_FAILURES`, `_record_host_failure`, `_is_host_failure`, machine exception handling |

The following requirements remain mandatory rather than removable
savings: canonical constraint construction and identity (N1),
three-valued logic (N2), admission and atomicity (N3), relation
subjects and ownership (N4), and program/version identity (N5).

Existing ordinary function execution, tagged errors, call-depth
refusal, graph lowering and version facilities are G1–G5.
They are free to reuse only without introducing new fixed rules.

## 7. Production consumers and migration counterfactual

Existing consumers of the dedicated evaluator include:

| Consumer | Implementation |
| --- | --- |
| Public constraint API | `Constraint.evaluate` |
| Initial cell admission | `Version._load`, `_check_content` |
| Initial relation admission | `_failed_constraint_relation` |
| Cell writes | `Runtime.write`, `_check_content`, `_failed_constraint_relation` |
| Activation and trial | `_stage_cells`, `_check_staged_relations` |
| Named evaluator calls | `External._check` |
| Failure provenance inside program runs | `shear/constraints.py`, `shear/machine.py` |

A replacement must serve all these consumers while preserving
the frozen public interfaces, admission decisions and failure
boundaries.

The tested B/C paths create independent experimental runtimes.
They do not replace any production consumer.

The smallest concrete migration consistent with the tested
implementations therefore retains the incumbent mechanisms for
unsupported cases. That architecture is not a complete replacement
and does not qualify.

A full replacement would require further facilities, described
below. No such complete migrated architecture was implemented or
validated during the bounded experiment.

## 8. Removal accounting

| Mechanism | Isolated candidate observation | Verified migrated disposition | R |
| --- | --- | --- | --- |
| M1 | B uses ordinary tuple operations; C executes generated bodies for a subset | Retained by all current production consumers; full removal unverified | 0 |
| M2 | Neither candidate implements required node budgeting | Existing mechanism still required | 0 |
| M3 | Named External evaluation unsupported | Existing mechanism still required | 0 |
| M4 | Escaping host failures not demonstrated through candidate execution | Existing mechanism still required | 0 |

**Verified removal credit: R = 0 for B and C.**

Theoretical maximum: four mechanisms.

The maximum is not an earned score. Avoiding a mechanism in a
separate experimental path is not evidence that production can
remove it.

## 9. Addition accounting – B

| Required rule | Evidence | Status |
| --- | --- | --- |
| Canonical constraint inspection | Negative `item` witnesses | New operation or equivalent interface required |
| Map projection and complete length | Negative map/length witnesses | Additional semantics required; overlap with introspection unresolved |
| Constraint-node budget | Budget-sensitive semantics not reproduced by call-depth limit | Replacement rule required |
| External authority | No candidate External execution | Boundary required |
| Host-failure provenance | No candidate escaping-error route | Existing rule must remain or be replaced |
| Pre-activation invocation | Runtime validates content before usable active execution | Safe generic execution path required |
| Effect isolation | No complete admission-boundary tests | Generic enforcement or specialized boundary required |

The tuple interpreter itself introduces no new fixed VM rule.
However, it does not perform the required constraint evaluation.

The missing operations and boundaries cannot be credited as free
merely because their implementations have not been written.

Some obligations might share generic implementation machinery.
Their exact independent count is unresolved.

**B: R = 0; complete migrated A unresolved; no qualifying net reduction.**

## 10. Addition accounting – C

| Required rule | Evidence | Status |
| --- | --- | --- |
| Constraint-to-code translation | `materialize`, `Compiler.compile` | One independently operating translation mechanism demonstrated |
| Generated code identity and reuse | New generated function graph for each probe runtime | Cache and ownership design unresolved |
| Initial admission execution | Existing load validates before ordinary program execution | Additional integration required |
| Resource accounting | Candidate rejects node budgets | Equivalent generic or specialized mechanism required |
| Named external evaluation | Candidate rejects external configuration | Authority mechanism required |
| Failure provenance | No external-failure candidate witness | Generic reuse or replacement unresolved |
| Purity and effects | Normal VM execution is not a constraint sandbox | Isolation mechanism or proven reuse required |
| Compatibility with all callers | Incumbent production sites remain unchanged | Migration integration required |

Generated function bodies are not charged individually as new
fixed mechanisms. The constraint-specific translation rule is
charged because it introduces an independent dispatch and
code-generation policy.

**C: at least one candidate-specific added mechanism is demonstrated.**

Further additions cannot be counted precisely without a complete
migrated architecture and evidence of which generic facilities
can be reused unchanged.

Any claim to remove M1 while continuing to depend on a separate
constraint dispatcher must account for that dispatcher.

**C: R = 0; migrated A is at least one for the demonstrated
compiler design, with further additions unresolved.**

## 11. Decision accounting

| Candidate | Mandatory semantics | Mandatory boundaries | Verified R | Migrated A | Verdict |
| --- | --- | --- | --- | --- | --- |
| A | Direct identity prerequisite fails | No qualifying implementation | 0 | Unresolved | Kill |
| B | Fail | Fail | 0 | Unresolved | Kill |
| C | Fail | Fail | 0 | At least 1; incomplete | Kill |
| S – control | Existing contract preserved | Existing contract preserved | Not applicable | Not applicable | Retain |

A complete numerical net score is deliberately withheld.

The result does not depend on claiming that every future
migration would have non-positive net mechanism savings.
Each bounded candidate already fails mandatory semantic or
boundary acceptance, independently of the mechanism score.

Under the frozen conjunctive adoption rule, failure of any
mandatory condition is sufficient to reject a candidate.

## 12. Predictions P1–P7

| Prediction | Evidence status |
| --- | --- |
| P1 – Existing call-depth limit cannot substitute for node budgeting | Consistent with baseline mechanics; not falsified by B/C |
| P2 – B needs additional content operations or an adapter | Supported by direct capability witnesses |
| P3 – Direct callable substitution breaks identity independence | Supported by A witnesses |
| P4 – Generic catch does not replace External boundary | Not falsified; no successful replacement boundary |
| P5 – Pre-activation safe execution is necessary | Supported by observed ordering; candidate integration absent |
| P6 – At least one additional rule is needed | Supported by missing B facilities and C translator |
| P7 – No strict mechanism reduction will be established | Not falsified |

This evidence supports the null hypothesis for the bounded
experiment. It does not establish a universal impossibility theorem.

## 13. Final Execute recommendation

**Kill A, B and C as replacements within the frozen Task 24 scope.**

Retain the dedicated constraint architecture and existing public
semantics. Do not weaken the frozen acceptance contract or enlarge
the prototypes into an unrestricted language/VM implementation.

Remaining limitations for independent Review:

- No successful candidate-integrated boundary execution.
- No complete replacement implementation for resource accounting,
  external authority, failure provenance or effect isolation.
- No fully validated migrated-production architecture with exact
  numerical additions.
- No proof that every possible future design lacks strict savings.

These limitations prevent adoption. They do not invalidate the
negative bounded experimental result.

Any subsequent attempt to introduce generic content inspection,
a generic fuel budget, new authority capabilities or pre-activation
execution should be separately planned and authorized.

Next workflow checkpoint: update `handoff.md`, then independent
read-only Review. Do not enter Publish before Review.
