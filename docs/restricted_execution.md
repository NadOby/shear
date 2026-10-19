# Restricted Execution – Task 32

**Status: Implemented (PR #125, merged 2026-10-19); frozen Plan preserved.**

Issue: GH-119. Baseline: `main` at `d50297cd44db26135bc0b3f9f95e4326c832beb9`.

This document records the frozen Plan for generic restricted execution
of ordinary SHEAR functions, with named `External` constraint evaluation
as its first integration use. Independent Plan Review subsequently
authorized Execute; the approval does not alter Decided semantics or
the frozen acceptance contract.

## 1. Question and objective

Can an ordinary SHEAR function, compiled and admitted through the
D3/D4/D5 hosted route, evaluate a named semantic constraint during
genuine runtime admission under a reusable generic restriction policy?

A positive answer requires executed positive and negative paths, not
a prototype which merely rejects unsupported boundary scenarios.

The milestone establishes integration feasibility. It does not claim
mechanism savings or full replacement of the incumbent evaluator.

## 2. Evidence and architectural findings

Relevant sources:

- `docs/constraint_model.md`
- `docs/relation_model.md` section 7
- `docs/error_handling.md`
- `docs/activation_model.md`
- `docs/hosted_pipeline.md`
- `docs/live_evolution.md`
- `docs/spikes/constraints_as_functions.md`
- `docs/spikes/constraints_as_functions_execute.md`
- `docs/spikes/constraints_as_functions_mechanisms.md`
- `shear/constraints.py`
- `shear/runtime.py`
- `shear/machine.py`
- `shear/operations.py`
- `shear/hosted_bootstrap/`
- Task 24 frozen acceptance and boundary oracles
- Task 31 hosted-runtime acceptance and lifecycle tests

Task 24 rejected its bounded A/B/C replacement implementations.
Candidate A did not preserve direct callable identity independence.
B lacked generic canonical-content inspection. C lacked complete
semantic translation and admission integration. All 17 boundary
scenarios were rejected as unsupported by B/C, not successfully
executed through candidate-integrated admission.

These results do not establish general impossibility.

The existing `External` constraint already separates canonical name
and identity from an executable evaluator.

`Version._load` checks initial constraints before a target `Runtime`
exists. `HostedSession` currently requires an already constructed
target runtime. Directly obtaining an evaluator from that unadmitted
target runtime would therefore be circular.

D3/D4 provide independent compiler and target source states,
authenticated chunks and version-bound artifact sets. Task 31 adds
candidate compilation, reuse and retirement.

The host machine's `may_activate=False` is not a sufficient
read-only execution boundary. Writes remain possible, and the
operation inventory does not currently provide a complete
transitive capability/effect proof.

## 3. Alternatives

### A. Callable constraints

Replace canonical constraint values with callable function objects.

Rejected for this milestone. This repeats Task 24 A's identity and
pre-load problems, requiring additional semantics with no evidence
of an advantage.

### B. SHEAR interpreter of canonical constraint trees

Interpret `IsKind`, `IntRange`, `Length`, compositions and role maps
inside ordinary SHEAR functions.

Deferred. Task 24 B demonstrated missing generic content operations.
Adding these now would expand the milestone into full constraint
replacement.

### C. Constraint-to-SHEAR compiler

Translate canonical constraint trees into derived ordinary functions.

Deferred. Task 24 C demonstrated translation but not equivalent
semantics, budgets or runtime admission. It would add another
independent constraint-specific mechanism.

### D. Generic restricted runner and named evaluator deployment

**Provisional preferred architecture.**

Keep canonical `External(name)` unchanged. Deploy an ordinary SHEAR
function under that name through a generic restricted-execution
facility, using existing hosted compiler and artifact admission.

The deployment is executable authority, not canonical constraint
content. Its implementation and replacement do not enter the
constraint's StateID or VersionID.

The runner must also execute non-constraint functions under the
same policy without depending on constraint classes.

This alternative is a hypothesis to be tested, not an approved
language redesign.

## 4. Trust boundaries and identities

Four independent objects must remain distinguishable:

1. Canonical constraint: immutable semantic content, including the
   evaluator's name but not its deployment or execution history.
2. Subject snapshot: canonical content drawn from the target state
   and its staged or live cells under existing relation semantics.
3. Evaluator deployment: a specific SHEAR function entry, source
   StateID, function and code-node EntityIDs/VersionIDs, admitted
   artifacts and compiler generation.
4. Invocation: one restricted execution using a pinned deployment,
   subject snapshot, immutable policy and operation-local context.

Deployment records are host runtime metadata, never user-supplied
authority to install or relabel chunks.

Do not confuse target StateID with evaluator source StateID or
compiler source StateID.

No evaluator call may execute a chunk unless its admitted provenance,
owner, node VersionID, compiler generation and dependency bindings
remain valid.

Artifact reuse follows D4/D5 verification. No reuse by matching
function names, StateIDs alone or structural chunk equality.

### Integrity and authority are independent

An artifact's content-derived `artifact_id` establishes consistency
between the recorded identity fields and chunk. It does not, by
itself, establish that an authorized compiler produced that chunk.

Restricted execution must preserve the D4/D5 distinction between:

- Structural validity under `validate_chunk()`.
- Internal integrity under `Artifact.verify()`.
- Authentic compiler-production and admission evidence.
- Authority to execute the artifact in a particular pinned
  deployment and restricted invocation.

Passing any one of these checks does not replace the others.

An attacker who constructs a self-consistent artifact record and
recomputes its hash must not thereby gain execution authority.

For a target artifact, `produced_by` identifies the compiler
generation which produced it. The `generation` field describes
a compiler artifact's own generation and is normally `None`
for a target artifact.

Reuse requires authentic source-artifact identity and valid
dependency bindings, not an arbitrary `reused_from` string.

### Deployment lifetime

An evaluator deployment remains held throughout an invocation.
Replacement must not alter a running invocation. Retired or
invalidated artifacts cannot be revived by an older registry entry.

Replacement does not immediately destroy artifacts still held by
an in-flight invocation. Such artifacts remain pinned until that
invocation ends, subject to explicit invalidation and existing
artifact-integrity checks. Retirement follows D5 ownership rules.

A failed preparation must not publish a deployment or leave
executable candidate artifacts reachable. Previously admitted
deployments and their artifact sets remain unaffected.

Normal replacement and eventual release must not leave an
unowned executable artifact set. No separate canonical lifecycle
or artifact identity scheme is introduced.

### Execution provenance

Every evaluation records enough evidence to identify:

- The constrained target StateID.
- The admission operation being performed.
- The selected evaluator name and function entry.
- The evaluator source StateID.
- The admitted code node and VersionID.
- The producing compiler generation and artifact identity.

The target StateID is distinct from the evaluator source StateID.
An evaluator-source execution event alone does not prove which
target admission operation requested the evaluation.

The implementation may extend host-side trace or operation
context metadata to carry this association. It must not change
canonical constraint content or derive the target identity from
the evaluator deployment.

Trace metadata must not become canonical constraint content.

## 5. Generic restricted-execution contract

Proposed host-facing conceptual interface:

    restricted_run(
        admitted_deployment,
        entry,
        canonical_arguments,
        policy,
    ) -> canonical_result

This is an architectural interface, not prescribed Python syntax.

The implementation reuses the ordinary hosted machine, compiler,
artifact validation and call machinery. It must not implement
constraint-specific bytecode dispatch or a second interpreter.

A restricted invocation requires:

- A valid pinned executable deployment.
- A fixed capability/effect policy supplied by the host.
- A complete pre-execution proof for reachable executable code.
- An immutable admitted-artifact view for the invocation.
- Fail-closed resolution of static and transitive calls.
- Rejection of unproven dynamic dispatch.
- Runtime enforcement of the same restrictions as defense in depth.
- No observable mutation before any failure or rejection.

The initial policy permits ordinary deterministic computation
and statically proven calls to equally permitted functions.

Writes, activation, trials, undeclared external calls and any
unclassified operation are denied. Canonical-state reflection,
closures and indirect calls are not automatically authorized.

### 5.1 Initial operation and instruction policy

The following is the bounded Task 32 classification. It is host
restriction metadata, not a language-visible effect system.

The pure policy has an empty effect allowlist. The read policy
adds only the existing `read` effect.

| Category | Source operations | Emitted instructions | Initial rule |
| --- | --- | --- | --- |
| Pure values and arithmetic | `lit`, `arg`, `add`, `sub`, `mul`, `lt`, `eq`, tuple and sequence operations | `LIT`, `ARG`, `ADD`, `SUB`, `MUL`, `LT`, `EQ`, `INT`, `TUPLE`, `MKTUPLE`, `LEN`, `ITEM`, `SLICE`, `CONCAT`, `POP` | Allowed |
| Pure control and local binding | `if`, `seq`, `let`, `unquote` | `EVAL`, `BRANCH`, `GOTO`, `LETCHECK`, `LETBIND`, `END` | Allowed where structurally valid |
| Static function calls | Statically resolved `call` | `CALL` | Allowed only when the entire transitive reachable call graph is proven permitted |
| Local language error handling | `catch`, ordinary `raise` | `CATCH`, `FAIL` | Allowed, subject to existing error semantics |
| Invalid-code failure | Malformed or invalid source | `RAISE` | May fail with the existing language error; never treated as a successful evaluator result |
| Cell reading | `read` | `READ` | Allowed only when `read` is explicitly present in the policy |
| Cell writing | `write` | `WRITE` | Denied by the pure and read policies |
| State evolution | `activate`, `trial` | `ACTIVATE`, `TRIAL` | Denied by the pure and read policies |
| Indirect execution | `apply`, `applyv` | `APPLY`, `APPLYV` | Denied unless separately proven; no such proof is in scope |
| Reflection and executable references | `ref`, `code`, `linksof`, closures and executable quotation or function construction | `REF`, `CODE`, `LINKS`, `REFCHECK`, `CLOSURE`, `QUOTE`, `FUNCTION` | Not authorized in this milestone |
| Unknown or unclassified | Any other operation | Any other instruction | Denied |

The classification intentionally addresses both graph operations
and admitted executable instructions. A known instruction is not
automatically safe merely because its shape is valid.

The allowed category for `FAIL` is necessary to exercise existing
ordinary SHEAR error semantics. A program `raise` is not a write,
activation, trial or external side effect.

When an evaluator raises, that ordinary language error crosses
the named `External` adapter as a host evaluation failure.
The enclosing target SHEAR `catch` must not consume it.

The `RAISE` instruction generated for invalid code is distinct
from ordinary program `raise` lowering to `FAIL`. Allowing the
existing invalid-code failure path does not authorize an
unclassified instruction or convert the failure into a verdict.

This matrix is the initial bounded policy. It does not imply
support for all possible combinations of host-granted effects.
The Task 32 positive witnesses require pure computation and
explicit read authority, not generalized write-capable execution.

### 5.2 Source and emitted instruction enforcement

Both canonical graph operations and actual admitted executable
instructions require checking. Checking only the semantic source
would trust the compiler's output to preserve its effects.
Checking only declared bytecode metadata without call-resolution
proof would leave transitive execution unprotected.

Preflight must inspect the actual admitted chunks, not merely
the compiler's declarations or source-node classifications.

A permitted static transitive call must actually execute. A
forbidden transitive effect must be rejected before the first
target instruction executes, including when hidden in a dead
branch. Unresolved indirect dispatch remains denied.

A structurally valid emitted `WRITE` is still forbidden under
the read policy. A malformed instruction rejected by
`validate_chunk()` does not demonstrate restricted effect-policy
enforcement.

The decisive emitted-effect acceptance witness must:

1. Begin with a semantically permitted source node.
2. Use an already valid, authorized cell link.
3. Inject a structurally valid executable chunk containing
   a forbidden `WRITE`.
4. Independently establish structural validity.
5. Ensure the chunk follows the observed compiler-production
   and admission route rather than merely corrupting its hash.
6. Require policy rejection before evaluator-machine execution.

Unknown emitted opcodes are tested separately as structural
admission failures. They do not substitute for the valid
forbidden-effect witness.

A conservative preflight may reject an otherwise harmless function.
Such rejection is a limitation, not permission to execute unproven
effects.

A guard encountered during execution must also prevent the effect
before its instruction executes, but cannot substitute for the
required preflight.

Restriction failures are host-side failures, not `Violated`,
`Unknown` or ordinary catchable program errors.

No unrestricted fallback is permitted following rejection.

### 5.3 Capability boundary

Task 32 may implement generic host-managed restriction metadata
and an execution policy over existing operations.

It does not silently introduce a new language-visible effect
type, capability syntax, purity annotation or authority token.

Any such language-shaping addition requires an owner decision
before implementation.

## 6. Bootstrap and initial admission

The preferred non-circular sequence is:

1. Rebuild or select an existing authenticated compiler generation
   under the finite D4 bootstrap contract.
2. Construct an independent evaluator source state containing
   ordinary SHEAR functions. Its own load must not depend on the
   unresolved target constraint or a circular evaluator deployment.
3. Compile and admit the evaluator program through route B.
4. Verify restricted-execution eligibility and pin its deployment.
5. Register the name through the existing external-evaluation
   boundary, using a narrow adapter to the generic runner.
6. Construct the target runtime normally. Initial cell and relation
   admission invokes the already available SHEAR evaluator.

The evaluator source and target source need not be the same state.
No evaluator code is inserted into the target canonical state.

A missing named deployment follows existing `External` semantics:
the result is `Unknown`, and mandatory admission rejects it.

An invalid, expired or unauthorized registered deployment must
fail closed. It must not silently become missing, retry through
host lowering or use an incumbent Python predicate.

Evaluator programs which themselves require unresolved external
evaluation are not implicitly bootstrapped by this proposal.

Self-contained evaluators defined only inside an unadmitted target
state require a separately reviewed non-circular preparation path.
That capability is not assumed in Task 32.

This sequence preserves D5's existing ordering: target candidate
constraints are checked before candidate code is compiled. The
already admitted evaluator deployment performs the checking.

Changing that ordering would require explicit owner approval.

## 7. Constraint semantic contract

All existing constraint forms, canonical identities and strong
Kleene composition rules remain unchanged.

`External` receives precisely the canonical subject supplied by
the incumbent evaluation path. Cell content, relation role maps,
owned subtrees, staged values and continuity are not reconstructed
with new constraint-specific rules.

For this bounded milestone, the ordinary SHEAR predicate returns
one of three canonical strings:

    "satisfied"
    "violated"
    "unknown"

A narrow interface adapter converts those exact values to the
existing `ConstraintResult`. This is transport conversion, not
constraint evaluation.

Unexpected values, malformed results and escaping execution errors
are failures, never coerced to `Unknown` or `Violated`.

Existing `EvaluationContext` constraint-node budgets remain in
force. Generic computation/fuel budgeting is explicitly deferred.

An External call still consumes its existing one constraint-node
step. This does not imply the function's internal computation is
bounded.

Evaluator exceptions retain host-failure provenance, including
when their exception class resembles a catchable language error.
An outer SHEAR `catch` must not consume such a host failure.

The acceptance test must independently observe the selected
admitted evaluator function and its actual machine execution,
then identify the precise language error it raised. Merely
asserting an exception class is insufficient.

Only `Satisfied` permits mandatory admission. `Violated` and
`Unknown` remain distinct rejected outcomes.

No partial write, activation or trial result may escape rejection.
The previous active state, cells, holds and admitted artifact sets
remain valid and unchanged.

Rollback evidence must capture immutable observations of loaded
version identities, per-version cell content, retirement flags,
hold membership, retained references and relevant admitted
artifact bindings. Comparing only mutable version objects is
insufficient.

Existing runtime admission is not retroactive. A successful
initial admission or write is not automatically repeated when
a named evaluator's deployment changes. Already accepted cell
contents and canonical program states remain unchanged.

A subsequent write, activation, trial or newly constructed
runtime performs its normal constraint checks using the
evaluator selected for that new operation.

In particular, a write of the same canonical value is still
a write operation and must satisfy the then-current constraint.
Replacement does not grandfather future writes.

No general mechanism for retroactively discovering and
revalidating all live users of an evaluator is introduced.

## 8. Evaluator replacement

The evaluator name is stable semantic content. Implementations are
identified by their separately pinned deployment descriptors.

Replacement must be explicit and atomic between admission
operations. An operation observes one coherent deployment snapshot,
including when it performs multiple constraint checks.

This snapshot rule concerns the new host deployment registry,
not a change to the semantics of canonical `External(name)`.
It guarantees that a single admission operation cannot mix
evaluator generations merely because a registry entry changed.

A new operation acquires its own deployment snapshot. The
registry may select a different implementation for that
operation without changing the previously admitted state's
identity or cell contents.

The frozen tests must compare the same target canonical state and
constraint identity under two distinct SHEAR implementations and
verify that the selected implementation changes observable admission
outcomes without changing canonical IDs.

For a persistent runtime, deployment replacement must not alter
an in-flight operation. If current evaluation-context ownership
cannot support this, Execute must introduce an explicit generic
operation-boundary snapshot mechanism or return to Plan.

The old deployment's admitted artifacts must remain valid
through the completion of operations that already pinned it.
When no invocation or other legitimate owner retains it, its
resources can be released under existing lifecycle rules.
Explicit invalidation must fail closed and must never silently
redirect execution to the replacement.

An operation rejected by a replacement evaluator must preserve
its previous target state, cells, holds, references and unrelated
admitted artifacts. Failed candidate preparation must also leave
previously admitted deployments intact.

No mutation of canonical constraint values, anonymous replacement
fallback or silent artifact relabelling is permitted.

## 9. Implementation stages

### Stage 0 – Baseline and dependency verification

Reproduce the relevant Task 24 and Task 31 controls, verify
current admission order, and inventory every existing evaluator,
host-lowering and artifact execution entry.

Resolve the dependency classification of #107 and #110.
No unrelated correctness fix is authorized by this Plan.

### Stage 1 – Generic restricted execution

Add a restricted invocation path over the admitted hosted machine.
Define conservative effect classification, transitive preflight,
dynamic-dispatch refusal and fail-closed runtime guards.

Prove non-constraint invocation first.

### Stage 2 – Evaluator deployment

Add immutable deployment descriptors, pinned provenance and
lifetime handling. Reuse the Task 30/31 compiler-generation and
artifact facilities.

No new independent artifact identity scheme.

### Stage 3 – Named constraint bridge

Bind an existing `External` name to a restricted SHEAR function.
Add exact result conversion and preserve exception provenance.

Do not replace primitive or composite constraint evaluation.

### Stage 4 – Runtime integration

Exercise genuine initial admission, writes, activation and trials,
including cell constraints and constraint relations.

Use the existing staging and rollback semantics. Do not create a
separate constraint-specific admission path.

### Stage 5 – Replacement and negative verification

Exercise explicit replacement, compiler-generation invalidation,
stale artifacts, tampered chunks, denied effects and malformed
execution inputs.

### Stage 6 – Evidence and mechanism audit

Produce a reproducible execution report, independent test
observations and mechanism ledger. Compare with Task 24's
negative baseline without changing its results.

## 10. Frozen acceptance design

The Plan must add executable acceptance modules and register
them in `tests/lanes.py` before Execute. Tests must fail on the
unimplemented production interface, not skip required integration.

Required fixture families:

### A. Genuine computation

A SHEAR predicate performs an actual comparison of its supplied
canonical scalar subject with a fixed threshold, returning
`satisfied` or `violated` through ordinary admitted execution.

A second predicate returns `unknown` on a defined input.

A non-constraint caller executes ordinary pure SHEAR functions
through the same restricted runner and obtains raw canonical
results, without using `External` or constraint conversion.

A permitted static transitive call must execute using the same
machine and actual admitted chunks.

### B. Genuine admission

For each boundary below, provide an accepting and rejecting
case using the real SHEAR evaluator:

- Initial cell admission.
- Initial constraint-relation admission.
- Cell write.
- Write affecting a relation through its endpoint.
- Activation with staged content.
- Trial with staged content.

At least one relation fixture must inspect the exact existing
role-map subject. Existing owned-subtree semantics must be
preserved, without introducing generic-content inspection.

Positive witnesses must prove execution, not merely admission
or a reported route label.

Each admission boundary requires an independent observation of
the selected evaluator entry and actual admitted machine chunk,
together with a resulting target-state assertion.

Fault injection at the actual evaluator-machine entry must
demonstrate that a hidden Python fallback cannot satisfy
initial cell admission, activation or trial when the evaluator
machine is intercepted.

Negative witnesses must prove the previous state and appropriate
cell, hold, reference and artifact state remain unchanged.

### C. Semantic and error boundaries

Test missing evaluator, explicit `unknown`, malformed result,
arity failure, canonical input conversion, escaping evaluator
exception, strong-Kleene composition and budget exhaustion.

Check that evaluator failures do not become catchable program
errors and do not turn into constraint verdicts.

Wrong-arity failure must preserve the existing language-error
kind and expected-versus-observed argument counts.

Malformed constraint results must be distinguished from ordinary
generic runner results. The generic runner may return a canonical
value which the constraint-result adapter properly rejects.

The error-provenance witness must establish the selected
evaluator entry, the actual admitted chunk, the emitted error
kind and detail, and its originating function and node.

### D. Restriction boundaries

Reject a direct `write`, `activate` or `trial` operation before
any evaluator instruction executes.

Reject a forbidden operation hidden behind a direct callee,
including an unreachable branch.

Reject unresolved dynamic calls and any unclassified instruction.

Reject an emitted forbidden instruction even when its semantic
source appears harmless. No hidden host execution or fallback.

A self-consistently rehashed artifact is still untrusted without
authentic compiler-production evidence. Tests must distinguish
hash integrity from admission authority.

The structurally valid emitted-effect fixture described in
section 5.2 is mandatory. A malformed chunk which fails
ordinary structural validation is not an equivalent witness.

Demonstrate that denied attempts leave live state unchanged.

### E. Provenance and lifecycle

Reject wrong target state, node, VersionID, compiler generation,
dependency, producer evidence and tampered admitted chunks.

Challenge the actual restricted deployment trust boundary with
rehashed, self-consistent artifact records. An arbitrary
`ArtifactSet` fixture with a broken content hash establishes
integrity checks, not authenticated restricted execution.

For target artifacts, forge `produced_by` rather than treating
`generation` as the producing compiler generation.

Where a candidate reuses an artifact, verify the authenticated
source dependency and refuse an invented reuse parent.

Reject stale and invalidated artifacts.

Prove that an in-flight invocation retains its valid deployment
across a permitted replacement, without silently switching code.

Prove correct artifact retention and eventual release under
existing ownership rules. Explicit invalidation must not
invalidate an unrelated replacement deployment.

Prove no survivor of failed candidate preparation and no
change to previously admitted artifact sets after rejection.

The independent test oracle must distinguish an artifact's
content-derived ID from its authority to execute. It must
also observe existing hold ownership and post-failure cleanup.

### F. Replacement

Run the same canonical `External` constraint with different
admitted SHEAR implementations. Verify unchanged canonical
identity, explicit deployment selection and different expected
outcomes.

No replacement may affect a partially evaluated transaction.
Already accepted state must not be retroactively revalidated.
The next admission operation uses the newly selected evaluator.

### G. Malformed data and isolation

Reject malformed evaluator descriptors, results, links and
function references before they can authorize execution.

A malformed tuple link target or `function` role (#110) must
not be accepted or silently flattened at this boundary.

Tests must preserve the malformed witness through any ordinary
input-format normalization. A post-load malformed definition or
role relation must reach restricted admission unchanged.

Check evaluator/source/target separation and failure cleanup.
No evaluator may mutate a caller's cells or activate its state.

## 11. Independent oracles and anti-gaming

The tests must not take expected answers from the implementation
under test.

Use simple independently computed expected comparisons, existing
canonical identity oracles and pre-existing admission semantics.

The Task 24 frozen semantic vectors and 17 boundary cases remain
unchanged. Task 32 does not claim to pass them as a complete B/C
replacement.

For each positive integration witness, require independent
observations of:

- The compiler-produced artifact and its admission evidence.
- The actual node/version/generation opened by the machine.
- The subject supplied at the runtime boundary.
- The constrained target StateID and admission operation.
- The expected result and resulting runtime state.

Disable host lowering after explicit preparation and verify no
fallback during evaluation.

Independently instrument actual machine execution and mutation
boundaries; implementation trace labels alone are insufficient.

A hard-coded Python predicate, fixture-name dispatch, false
reporting of an executed route or a candidate that rejects every
case cannot pass.

Fault injection must prove that removing or corrupting the
relevant admitted artifact stops execution rather than selecting
an alternate evaluator.

Independent tests must also challenge admitted bytecode that
does not agree with the apparent source graph, including an
emitted forbidden effect or an unknown future instruction.

The forbidden-effect fixture must first pass the existing
structural validator. Structural rejection cannot be counted
as effect-policy enforcement.

Self-consistent but unauthenticated artifact substitutions must
be independently distinguished from broken hashes.

For operations with staged changes, rollback observations must
capture immutable copies of mutable runtime state and the
corresponding admitted-artifact bindings.

Tests must distinguish failed integration from genuinely executed
negative results.

## 12. Mechanism accounting

Reuse Task 24's definition: one mechanism is one independently
enforced semantic or execution rule requiring fixed machinery.

At minimum audit:

- M1 – dedicated constraint dispatch and recursion.
- M2 – constraint-node budget.
- M3 – named external-evaluator authority.
- M4 – escaping host-failure provenance.
- N1–N5 – mandatory canonical, result, admission, subject and
  identity requirements.
- Existing generic machine, compiler and artifact facilities.
- New generic restricted-execution authority and enforcement.
- New transitive-call/effect proof obligations.
- New deployment snapshot and replacement/lifetime rules.
- Any new result adapter or host execution bridge.

For each rule report `retained`, `reused unchanged`, `extended`,
`added`, `shared` or `genuinely removed`, with code locations
and an independently checked execution-path witness.

Do not count a wrapper, a renamed function, moved code or unused
legacy path as a removal.

The incumbent M1–M4 are not presumed removed. A shared new
facility counts once only if there is genuinely one enforcing
mechanism, even when several call sites use it.

No net-savings threshold applies to Task 32.

## 13. Correctness dependencies

Issue #110 describes malformed tuple link and function-role
inconsistency between consumers. Restricted admission must fail
closed on this shape. If a general correction is necessary to
make that guarantee, stop and request a separately scoped fix;
do not silently expand Task 32.

Issue #107 concerns mutation-survivor repin revalidation. It
becomes a publish dependency if Task 32 changes the mutation
engine or catalog and the relevant campaign evidence is missing.
No such modification is planned.

Task 24's frozen Plan, results and acceptance oracles remain
immutable. Task 31's D5 provenance and artifact-lifetime contract
remains binding.

No golden-record changes are authorized in this Plan.

## 14. Outcome classification

**Positive:** Every required genuine admission boundary executes a
SHEAR-produced admitted predicate and yields the independently
expected accepting and rejecting behavior. Generic reuse,
pre-execution isolation, lifecycle, replacement and anti-fallback
tests also pass.

**Negative:** An exact acceptance discriminator fails and a
reproducible witness identifies the smallest missing generic
capability, architectural contradiction or implementation defect.

**Inconclusive:** A required witness is not executed, the oracle
cannot distinguish real integration from fallback, provenance
cannot be established, or isolation remains unproved.

Only the positive outcome satisfies Task 32's proposed
implementation terminal acceptance.

A negative or inconclusive implementation outcome must produce
an actionable successor or return to Plan. It cannot be called
successful integration or published as completed implementation
solely because the failure was informative.

The report must separate the bounded result from the still-open
architectural question.

## 15. Required blocked-outcome evidence

If blocked, record:

1. Exact command, fixture and failing assertion.
2. Required and observed result, including runtime effects.
3. Pinned source, node, compiler generation and artifact provenance.
4. The smallest absent generic capability or violated invariant.
5. Whether the obstacle is a missing capability, implementation
   defect, architectural obstacle or untested hypothesis.
6. At least one bounded alternative and its distinguishing test.
7. A concrete successor action, dependency and owner decision
   when required.

Do not replace this evidence with a general claim that SHEAR
constraints cannot be ordinary functions.

## 16. Deferred scope and owner decisions

Deferred:

- Generic canonical-content and role-map inspection.
- A generic computation/fuel budget.
- Full Task 24 B/C semantic replacement.
- Removing the incumbent evaluator.
- General dynamic-dispatch effect inference.
- Language-visible effects, capability types or purity syntax.
- Unrestricted self-referential target-state evaluator bootstrap.
- Native-code backends and unrelated VM parity work.

Owner approval is required before changing:

- D5 candidate compilation and constraint-check ordering.
- The language's effect/capability semantics.
- Canonical constraint identity or result semantics.
- Whether evaluators must be defined within their constrained
  target state rather than separately deployed.
- Any existing golden expectation or frozen Task 24 contract.

The provisional architecture is deliberately scoped so these
decisions are not prerequisites for the initial independent
evaluator-deployment experiment.

If a decision becomes essential, return to the owner before
implementing a language-shaping change.

## 17. Plan completion and Review gate (historical)

At Plan freeze, substantive Execute work remained. Execute was later
completed and independently approved at `e26430c`. The original
pre-Execute checklist below is retained as historical Plan text.

Before freezing the revised Plan:

- Register Task 32 in the roadmap without unrelated edits.
- Add executable positive and negative acceptance tests.
- Register their test lane and verify their collection.
- Fix complete expected observations independently of production.
- Record the exact baseline and full Plan-owned file inventory.
- Record the revised frozen Plan content head in `handoff.md`.
- Confirm no production or golden records changed.
- Request fresh independent Plan re-Review.

Review must challenge architectural feasibility, bootstrap ordering,
effect-proof completeness, independent oracles, owner-controlled
decisions, hidden fallback, mechanism counting and the adequacy of
negative/inconclusive disposition.

Do not begin Execute or open a PR until the revised Plan is approved.
