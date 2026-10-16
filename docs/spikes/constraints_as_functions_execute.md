# Task 24 – Execute Evidence and Mechanism Audit

**Status: Provisional Execute evidence – not a final verdict.**

Issue: GH-56.
Branch: `task/24-constraints-as-functions`.
Inspected head: `57dd0c7`.
Frozen Plan: `97e4297`.
Control baseline: `697b2d7`.

This document records observations from the bounded B/C experiments.
It does not amend the frozen predictions, acceptance contracts or
mechanism-counting rules.

## 1. Verification

GitHub Actions run `38972471297` succeeded at `57dd0c7`.

The run passed:

- All registered semantic test lanes.
- Ten experimental B/C probe tests.
- Golden-record comparisons.

This establishes that the experimental tests execute successfully.
It does not establish that B or C satisfies the frozen acceptance
contract.

No production constraint implementation was replaced.

The Plan-owned specifications, oracle, semantic grader, boundary
grader and test-lane registration remain unchanged.

## 2. Candidate B – ordinary-function interpretation

Implementation:
`tests/constraint_function_b_probe.py`.

The positive witness executes an ordinary SHEAR function over
tuple-form data through:

`Function` → `State.create` → `load` → `Runtime` → `run` →
ordinary machine operations.

This demonstrates basic interpretation of tuple-form data.

The negative witnesses establish that the current `item` operation
cannot project canonical constraint nodes or canonical maps.
The current `len` operation also lacks the complete semantics of
the constraint algebra's `Length` primitive.

The relevant implementation is `shear/machine.py::_items`.
It exposes elements of ordinary tuples and canonical tuples,
not arbitrary canonical nodes.

Consequences:

- No actual canonical constraint interpreter has been implemented.
- No B adapter has been submitted to the frozen semantic grader.
- No B adapter has executed the 17 mandatory boundary scenarios.
- Constraint-node budgeting is not implemented.
- Named External dispatch and failure provenance are not implemented.
- No generic introspection or runtime operations have been added.

These are bounded negative witnesses supporting P2, not proof
that all possible interpretation-based implementations fail.

**B status: incomplete and not eligible for adoption.**

## 3. Candidate C – compilation to ordinary functions

Implementation:
`tests/constraint_function_c_probe.py`.

Observed candidate path:

`CandidateInput` → `materialize` → canonical Constraint
construction → `Compiler.compile` → generated `Function` →
`State.create` → `load` → `Runtime` → `run`.

The compiler implements a bounded subset:

- `OneOf`
- `Not`
- `AllOf`
- `AnyOf`

Generated function bodies execute using the existing language
and virtual machine.

Canonical constraint construction, operand normalization and
ordinary semantic equality are reused from existing facilities.

This is not an independent reimplementation of every primitive.

The candidate explicitly rejects unsupported functionality,
including:

- Constraint-node budgets.
- External evaluator configuration.
- Primitive operations outside the implemented subset.
- Runtime boundary integration not provided by the prototype.

The probe runs `assess` against all fixed semantic vectors and
two generated seeds per family.

The resulting report is deliberately non-passing. The test checks
that the incomplete candidate does not qualify.

The default full generated campaign and all 17 candidate-facing
boundary scenarios have not been executed through C.

The adapter's declared route and zero fallback count are not
independent execution-path instrumentation.

The ordinary test lanes passing does not establish equivalence
between the generated layer and the production admission paths.

**C status: bounded proof of concept, not a qualifying replacement.**

## 4. Existing production consumers

The migration counterfactual must preserve all existing users
of constraint evaluation, including the public
`Constraint.evaluate` interface.

Relevant implementation sites:

| Consumer | Current implementation |
| --- | --- |
| Direct constraint evaluation | `shear/constraints.py::Constraint.evaluate` |
| Initial cell validation | `shear/runtime.py::Version._load`, `_check_content` |
| Initial relation validation | `shear/runtime.py::_failed_constraint_relation` |
| Cell writes | `shear/runtime.py::Runtime.write` |
| Staged activation and trial | `shear/runtime.py::_stage_cells`, `_check_staged_relations` |
| Named evaluator invocation | `shear/constraints.py::External._check` |
| Host-failure provenance | `shear/constraints.py`, `shear/machine.py` |

The probes create separate runtimes containing experimental
functions. They do not redirect these production callers.

Any removal claim must explain how every consumer above would
operate in the migrated architecture without retaining an
independent duplicate constraint evaluator.

## 5. Isolated-path mechanism ledger

The baseline taxonomy is defined in
`docs/spikes/constraints_as_functions_mechanisms.md`.

| Mechanism | B isolated path | C isolated path |
| --- | --- | --- |
| M1 – Dedicated constraint execution | Avoided for tuple examples only; full constraint path unresolved | Avoided in implemented subset; canonical construction retained |
| M2 – Constraint-node budget | Not implemented | Explicitly unsupported |
| M3 – Named External dispatch | Not implemented | Explicitly unsupported |
| M4 – Host-failure provenance | Not exercised | Not exercised |

Avoidance in an isolated path is not production removal.

The prototypes do not establish that any M-series mechanism
could cease operating across every migrated production consumer.

## 6. Migrated-architecture removal ledger

| Mechanism | Potential migration disposition | Verification | R credit |
| --- | --- | --- | --- |
| M1 | Replace dedicated execution with ordinary functions | Incomplete semantics and integration | 0 |
| M2 | Replace node accounting with an equivalent generic execution budget | No equivalent candidate budget demonstrated | 0 |
| M3 | Replace named evaluator dispatch with a generic authority boundary | No candidate External execution demonstrated | 0 |
| M4 | Reuse or replace host-failure provenance without duplicate enforcement | No candidate failure-boundary evidence | 0 |

The possible removal ceiling is four mechanisms.

**Verified removals: R = 0 for B and C.**

This is an evidence score, not an assertion that migration
could never remove these mechanisms.

## 7. Candidate B – addition obligations

A complete B migration requires analysis of the following
independent fixed rules:

| Obligation | Evidence | Accounting status |
| --- | --- | --- |
| Canonical content projection and kind inspection | Current tuple projection rejects canonical constraint nodes | Missing facility; count unresolved |
| Canonical map access and full Length support | Negative B probes | Missing operations; overlap with projection unresolved |
| Per-constraint-node evaluation budget | M2 semantics differ from existing call-depth refusal | Replacement not implemented |
| External authority boundary | Missing evaluator and escaping exception semantics remain mandatory | Replacement not implemented |
| Safe evaluation before activation | Initial admission currently calls the dedicated evaluator | Generic reuse or new boundary unresolved |
| Failure provenance and effect isolation | Existing generic catch behaviour alone does not demonstrate equivalence | Reuse or new enforcement unresolved |

These obligations must not be counted by file or wrapper count.

The number of genuinely independent new mechanisms is not yet
established. Some may share an existing generic facility;
others may require an additional rule.

**B: complete migrated-architecture addition count unresolved.**

## 8. Candidate C – addition obligations

| Obligation | Evidence | Accounting status |
| --- | --- | --- |
| Constraint-to-function translation | `Compiler.compile`, `materialize` | New fixed translation rule present in prototype |
| Generated code identity and reuse | New compiled function graph per probe evaluation | Migration design unresolved |
| Artifact lifetime and ownership | Existing VM facilities exist; candidate-version integration absent | Generic reuse unresolved |
| Constraint-node budget equivalence | Candidate rejects budgets | Replacement not implemented |
| Named external authority | Candidate rejects external configuration | Replacement not implemented |
| Host-failure provenance | No candidate External execution | Replacement not implemented |
| Pre-activation code execution | Production initial admission precedes usable active runtime | Execution boundary unresolved |
| Effect isolation | Ordinary VM execution alone does not establish the constraint sandbox | Enforcement unresolved |
| Public-interface compatibility | Production consumers still call `Constraint.evaluate` | Migration bridge unresolved |

The constraint-to-code compiler is new fixed machinery even
though the resulting programs execute with ordinary language
operations.

Existing lowering and execution facilities G1 and G4 can be
counted as shared only when reused without altering their
fixed semantics.

Do not award free removal credit for M1 while omitting the
translation mechanism from additions.

**C: at least one demonstrated new fixed mechanism; the complete
migrated-architecture addition count remains unresolved.**

## 9. Accounting checkpoint

| Candidate | Full semantics | Full boundary contract | Verified R | Complete A | Adoption |
| --- | --- | --- | --- | --- | --- |
| B | Not tested through a candidate adapter | 0 of 17 | 0 | Unresolved | Not qualified |
| C | Fails frozen semantic grading | 0 of 17 | 0 | Unresolved | Not qualified |

No strict mechanism reduction has been established.

A numerical net score is withheld because additions have not
been completely accounted for in a specified migrated
architecture.

Reporting `A = 0` for absent implementation work would be
incorrect.

## 10. Predictions and remaining evidence

- P1 – Existing call-depth refusal is not demonstrated to
  reproduce constraint-node budgets. No complete candidate
  discriminator result.
- P2 – Supported by the observed B capability gaps.
- P3 – Callable identity and pre-activation execution witnesses
  have not yet been executed.
- P4 – External authority and host-failure equivalence
  have not been demonstrated.
- P5 – Candidate execution through initial and staged admission
  has not been demonstrated.
- P6 – Additional facilities appear necessary, but the full
  mechanism inventory is not established.
- P7 – The null prediction is not falsified by the current probes.

Still missing:

1. A bounded A identity and bootstrap assessment.
2. Either genuine candidate-facing semantic and boundary adapters
   or explicit evidence justifying termination of the bounded
   designs before expanding their scope.
3. Independent instrumentation of incumbent calls, authorization
   and effects for every claimed successful candidate route.
4. Complete, falsifiable migration counterfactuals for B and C,
   with all additions counted against the same architecture.
5. Final comparison against P1–P7 and an independently
   reviewable adopt-or-kill verdict.
6. An updated `handoff.md` before the Review checkpoint.

The frozen acceptance expectations must not be weakened.

## 11. Current recommendation

Do not expand B or C into unrestricted production implementations.

First determine whether the missing facilities can fit inside
the frozen experiment boundary and whether a credible complete
migration has any prospect of satisfying `R > A`.

If not, document the blocking costs and reject the candidates.

A negative result is valid completion of Task 24, provided the
mechanism argument and remaining required witnesses are recorded
and independently reviewed.

Do not enter Publish or claim an adopted migration at this stage.
