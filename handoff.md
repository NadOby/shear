# Handoff

Read `CLAUDE.md`, the Workflow section of `docs/roadmap.md`,
issue #119, `docs/restricted_execution.md`, and the Task 24
experimental evidence. Verify all claims against the repository.

This file is a checkpoint, not independent evidence.

## Current state

- Issue: #119 – Task 32, generic restricted execution and SHEAR-defined constraints.
- Branch: `task/32-restricted-execution`.
- Role: Plan Resolve complete – request independent re-Review.
- Baseline `main`: `d50297cd44db26135bc0b3f9f95e4326c832beb9`.
- Original frozen Plan: `819848a849c4a15da29232c911fa36c24b57bd40`.
- Revised frozen Plan content head: `d7261cdd568ae55a85714b12f5659c7cb7a5f0d2`.
- Substantive Execute work remains mandatory.
- No production implementation, golden-record changes or PR.
- The proposed `shear.hosted_bootstrap.restricted` module does not exist.

## Revised Plan-owned files

- `docs/restricted_execution.md`
- `docs/roadmap.md` – Task 32 entry only
- `tests/test_restricted_execution.py`
- `tests/test_restricted_execution_boundaries.py`
- `tests/test_restricted_execution_lifecycle.py`
- `tests/lanes.py` – three test registrations only

These files constitute the revised acceptance contract.
Execute must not weaken frozen expectations without an explicit
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

## Independent Review findings and Plan Resolve

Previous independent review verdict: REVISE.

Resolve changes committed after the original frozen Plan:

- `df639c1` – corrected malformed-link witnesses, added permitted
  transitive calls, stronger runtime snapshots and error assertions.
- `e61a903` – added independent artifact-provenance checks, emitted
  forbidden-bytecode tests and stronger rollback observations.
- `91d1ba5` – added lifecycle, in-flight replacement, cleanup and
  forged-producer acceptance tests.
- `e010bc5` – registered the lifecycle acceptance module.
- `ace8d58` – clarified replacement, non-retroactive admission,
  operation-level snapshots and artifact lifetime in the specification.
- `d7261cd` – removed unrelated lane-runner wording change.

These corrections are proposed resolutions, not self-certified
evidence of compliance. Independent re-Review must verify each.

## Frozen semantic boundaries

- Canonical constraint identity does not include evaluator deployment.
- Admission is not retroactive: replacement does not revalidate
  already accepted cell contents or program state.
- New writes, activations, trials and initial admissions use the
  evaluator selected for their operation.
- An operation performing multiple checks uses one pinned deployment
  snapshot even if registry replacement occurs during execution.
- In-flight deployment holds and valid artifacts remain protected
  under D5 lifecycle rules; explicit invalidation fails closed.
- Preflight checks both semantic graph operations and actual admitted
  bytecode, including static transitive dependencies.
- Unresolved indirect calls and unclassified instructions are denied.
- No Python evaluator fallback, independent execution engine or
  special constraint interpreter is authorized.

Generic content inspection, computation fuel, language-visible
effects and unrestricted evaluator self-bootstrap remain deferred.

## CI evidence

Run `39064305280` at the original frozen Plan failed because
the two original Task 32 acceptance modules imported the absent
restricted-execution implementation. Seven other lanes passed.

The revised Plan adds a third acceptance module. Run
`39138948136`, targeting `d7261cd`, was still in progress when
this checkpoint was prepared. Its final result must be checked
independently.

Import failures before Execute do not establish successful
execution of acceptance assertions. Do not represent CI as green.

## Independent Plan re-Review

Review the complete branch diff against baseline `d50297c`
and compare the original and revised frozen Plan content.

For each previous P1/P2/P3 finding, verify whether its correction
is sound, independently discriminating and feasible against
the existing SHEAR runtime and hosted machinery.

Especially inspect:

- Malformed input versus post-load graph normalization.
- Permitted and forbidden transitive calls.
- Adversarial emitted bytecode and producer authenticity.
- Actual machine execution rather than implementation trace claims.
- Artifact identity, lifetime, invalidation and cleanup.
- Operation-level replacement consistency.
- Non-retroactive admission and subsequent constraint checks.
- Atomicity of live cells, holds, references and admitted artifacts.
- Arity, result conversion and escaping host-error provenance.
- Preservation of Task 24, D3/D4/D5 and owner decisions.

Check the full diff for unrelated changes and unnecessary scope
expansion. Classify findings P0–P3, separating verified defects
from limitations and hypotheses.

Read-only. Do not modify files, Execute or open a PR.

Give an explicit APPROVE or REVISE verdict. If blocking findings
remain, Resolve them and obtain another independent Review.
If approved, proceed to Execute against this frozen contract.
