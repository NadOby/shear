# Handoff

Read `CLAUDE.md`, the Workflow section of `docs/roadmap.md`,
issue #119, `docs/restricted_execution.md`, and the Task 24
experimental evidence. Verify all claims against the repository.

This file is a checkpoint, not independent evidence.

## Current state

- Issue: #119 – Task 32, generic restricted execution and SHEAR-defined constraints.
- Branch: `task/32-restricted-execution`.
- Role: second Plan Resolve complete – request independent re-Review.
- Baseline `main`: `d50297cd44db26135bc0b3f9f95e4326c832beb9`.
- Original frozen Plan: `819848a849c4a15da29232c911fa36c24b57bd40`.
- First revised Plan: `d7261cdd568ae55a85714b12f5659c7cb7a5f0d2`.
- Second revised frozen Plan content head: `1cf3f22f1767a3d3b001b86f27381b6cfb41d9e2`.
- Substantive Execute work remains mandatory.
- No production implementation, golden-record changes or PR.
- The proposed `shear.hosted_bootstrap.restricted` module does not exist.

## Plan-owned files

- `docs/restricted_execution.md`
- `docs/roadmap.md` – Task 32 entry only
- `tests/test_restricted_execution.py`
- `tests/test_restricted_execution_boundaries.py`
- `tests/test_restricted_execution_lifecycle.py`
- `tests/lanes.py` – three test registrations only

These files constitute the proposed frozen acceptance contract.
Execute must not weaken reviewed expectations without an explicit
reviewed Plan revision.

## Architectural objective

Establish whether ordinary SHEAR functions can perform restricted
computation during genuine runtime admission using the existing
hosted compiler, admitted artifacts and machine.

Use named `External` constraint evaluation as the first integration
without adding an independent interpreter or claiming architectural
superiority over conventional implementations.

Demonstrate reusable non-constraint execution, restricted static
calls, fail-closed effect enforcement, authenticated execution,
correct admission semantics and safe runtime evolution.

Functional sufficiency and manageable architectural risk are
the success criteria. Mechanism savings are not required.

Retain Task 24's negative evidence, independent semantic oracles
and incumbent evaluator. Preserve D3/D4/D5 contracts.

## Review history

The original Plan received REVISE.

The first Resolve added permitted transitive execution, strengthened
admission observations, malformed-link witnesses, provenance tests,
lifecycle checks and explicit replacement semantics.

First Resolve commits:

- `df639c1` – main acceptance corrections.
- `e61a903` – independent boundary tests.
- `91d1ba5` – lifecycle tests.
- `e010bc5` – third acceptance module registration.
- `ace8d58` – replacement and lifetime semantics.
- `d7261cd` – unrelated lane-runner message cleanup.
- `8bc71af` – first revised Plan handoff.

The independent re-Review of `d7261cd` returned REVISE.

Its three blocking P1 findings were:

1. Emitted forbidden-effect fixtures failed ordinary chunk validation
   and therefore did not establish effect-policy enforcement.
2. Most artifact provenance fixtures failed checksum verification,
   without challenging authenticated execution authority.
3. Independent machine observations and anti-fallback fault injection
   did not cover every required admission boundary.

Additional P2 concerns addressed runtime operation provenance,
immutable rollback snapshots, error-origin evidence, deployment
lifetime and the initial effect-policy classification.

## Second Plan Resolve

Changes after the first revised handoff:

- `0839f44` – rehashed artifact-forgery and lifecycle witnesses.
- `f110d66` – structurally valid forbidden emitted effect,
  independent admission-path machine observations and operation
  provenance assertions.
- `eae1ca8` – immutable runtime snapshots, exact arity/error
  provenance and result-conversion checks.
- `00a73d5` – explicit initial instruction/effect matrix and
  separation of structure, integrity and compiler authority.
- `1cf3f22` – authenticated-forgery test at the original artifact
  lookup key, including a real but unauthorized reuse parent.

The second Resolve modifies only:

- `docs/restricted_execution.md`
- `tests/test_restricted_execution.py`
- `tests/test_restricted_execution_boundaries.py`
- `tests/test_restricted_execution_lifecycle.py`

The architecture, roadmap, lane registrations, production code,
Task 24 controls and golden records were not changed in this round.

These are proposed corrections, not self-certified proof.
Independent re-Review must verify their feasibility and rigor.

## Frozen execution and authority boundaries

- Canonical constraint identity excludes evaluator deployment.
- Admission is not retroactive.
- New admission operations use their selected evaluator deployment.
- Each operation retains one coherent evaluator snapshot.
- In-flight valid deployment artifacts remain pinned under D5 rules.
- Explicit invalidation fails closed without fallback.
- Both semantic operations and actually admitted bytecode are checked.
- Pure deterministic operations and proven static calls are permitted.
- `read` requires explicit read authority.
- Writes, activation, trials, indirect calls and unclassified
  instructions are denied under the tested pure/read policies.
- Ordinary language `raise` and `catch` retain error semantics.
- A structurally valid emitted `WRITE` must be refused by effect
  policy rather than by ordinary structural validation.
- Content-derived artifact integrity is not compiler authority.
- Rehashed unauthorized artifacts must not acquire execution rights.
- Malformed graph links must fail closed without normalization
  concealing the malformed representation.
- No Python evaluator fallback, independent execution engine or
  constraint-specific interpreter is authorized.

Generic content inspection, computation fuel, language-visible
effects and unrestricted evaluator self-bootstrap remain deferred.

## Runtime integration evidence required

For each positive and negative initial admission, cell write,
relation write, activation and trial witness, inspect:

- The selected evaluator entry.
- The actual node and admitted chunk opened by the machine.
- The evaluator source StateID and producing compiler generation.
- The canonical subject actually supplied.
- The constrained target state and admission operation.
- The independently expected verdict and runtime result.

Fault injection must demonstrate that intercepting the actual
evaluator machine prevents admission rather than triggering
a hidden fallback.

Negative operations must preserve independently captured cell,
version, retirement, hold, reference and artifact observations.

Host-evaluator failures must be distinguished from ordinary
target-language failures and from compilation or admission errors.

## Artifact authority evidence required

Check separately:

1. Structural validity of an emitted chunk.
2. Content-derived artifact integrity.
3. Authentic compiler-production/admission evidence.
4. Correct node/version/owner/source/generation bindings.
5. Genuine reuse-dependency authority.
6. Permission under the restricted policy.
7. Lifetime and invalidation.

The forged-artifact tests must not pass merely because a checksum
is wrong or a lookup key is missing.

The structurally valid emitted-write fixture must not pass merely
because an instruction is malformed.

Normal artifact retention and eventual release must remain
consistent with D5 ownership rules.

## CI evidence

Original frozen Plan run `39064305280` failed because the
restricted-execution implementation was absent. Seven other
lanes passed.

First revised Plan run `39138948136` completed with seven
passing lanes and three missing-module import errors in the
cross-boundary lane.

Second Resolve run `39145424370` likewise failed with three
`ModuleNotFoundError` errors for the absent
`shear.hosted_bootstrap.restricted` module.

Run `39146766203` targets the second frozen content head
`1cf3f22` and was in progress when this checkpoint was
prepared. Independently verify its final result.

No new Task 32 acceptance assertions have executed.
Import failures are expected before Execute but do not
establish behavioral correctness or successful integration.

Do not represent CI as green.

## Independent Plan re-Review

Review the complete branch diff against baseline `d50297c`.

Compare:

- Original frozen Plan `819848a8`.
- First revised Plan `d7261cdd`.
- Second revised Plan `1cf3f22`.

Reassess every previous P1–P3 finding, prioritizing:

- Structural validity of the emitted forbidden-write fixture.
- Separation of artifact integrity and compiler authority.
- Self-consistent forgery injection at the correct lookup key.
- Actual machine observations at all admission boundaries.
- Anti-fallback fault injection and admitted chunk identity.
- Target-state and operation provenance.
- Immutable runtime rollback and reference observations.
- Error-provenance and exact result-conversion assertions.
- Deployment replacement, invalidation, retention and release.
- Completeness and feasibility of the initial effect-policy matrix.
- Task 24, D3/D4/D5 and owner-decision preservation.
- Unnecessary complexity or expansion of architectural search space.

Critically assess the tests themselves. In particular, distinguish
a fixture that fails for the intended invariant from one that
fails incidentally because of malformed inputs, incorrect runtime
assumptions, a missing artifact or an unrelated exception.

Check for duplicate mechanisms, unsupported assertions, hidden
fallback, unrelated changes and accidental language redesign.

Read-only. Do not modify files, Execute or open a PR.

Classify findings P0–P3 and give an explicit APPROVE or REVISE
verdict with actionable corrections.

If approved, proceed to Execute against the frozen contract.
If blocking findings remain, Resolve them and obtain another
independent re-Review.
