# Activation Model

This document describes what happens when a running program activates a new
version of its own program state.

Every SHEAR program carries its compiler and can modify itself. Program
modification produces a new immutable state (see
[`transformation_model.md`](transformation_model.md)). Activation is the
separate step that makes the running program execute that state.

Status markers used in this document are:

- **Decided:** agreed direction; later changes should be deliberate.
- **Provisional:** current direction, not fully settled.
- **Open:** options are listed; no direction is chosen.

## 1. Program state and runtime state

**Decided:**

A running program has two kinds of state:

    program state
        immutable semantic state identified by StateID:
        values, ownership, and the existence, identity and type of
        mutable cells

    runtime state
        everything produced by execution: stack frames, heap data,
        mutable cell content, execution positions, native code

Runtime state does not contribute to `StateID`.

Activation connects the two. Runtime state produced while `S₀` was active must
become valid, or remain explicitly pinned, when `S₁` becomes active.

## 2. Activation as a transition

**Decided:**

Activation takes:

    active state          S₀
    produced state        S₁
    transformation result S₀ → S₁ with explicit continuity
    state-transfer functions, where required

and makes `S₁` active.

Activation uses the transformation result, not only `S₁`. Continuity is what
tells the runtime how live state in `S₀` corresponds to `S₁`.

Activation is atomic from the program's point of view: either `S₁` becomes
active with every required transfer completed, or `S₀` stays active and
runtime state is unchanged.

A result must start from the active state. A result whose source is a
state this runtime had active earlier is rebased over every result
activated since, in order (continuity_inference.md §5): disjoint edits
combine, and overlapping ones raise `ActivationConflict`, which is both
`ActivationRejected` and `TransformationConflict`. A result from a state
the runtime never had active is rejected as stale ("does not start from
the active state"), not as a conflict. `trial` does the same.

**Provisional:**

The runtime remembers every result it activated.

Activating a state for which no transformation from the active state
exists gives every live entity unknown continuity. Such an activation is
therefore rejected whenever any mutable cell holds live content (section 4),
and references into `S₀` stay pinned (section 6).

## 3. Validation and authority

**Decided:**

Producing a new state with the embedded compiler and activating a state are
both governed by capabilities. A program without the activation capability
cannot replace its own running version.
Until capabilities are modelled, the language grants it per run
(metaprogramming.md section 4).

Order:

1. produce `S₁`;
2. validate `S₁` (constraints and contracts);
3. run state-transfer functions into staged runtime state;
4. switch atomically;
5. release superseded versions when nothing depends on them (section 7).

Any failure before step 4 leaves `S₀` active and runtime state unchanged.
`Unknown` validation results do not permit activation unless an explicit
policy says otherwise.

### 4. Mutable cell content

**Decided:**

This section, except the conversion rule and the placement of conversions.

**Provisional:**

The conversion rule and the placement of conversions.

A mutable cell is versioned program state; its content is runtime state. At
activation, cell content is carried along explicit continuity:

    cell A in S₀ → cell A' in S₁
        content of A is transferred into A'

This corresponds to Erlang's `code_change`: the new version receives the old
state and may convert it.

A cell's type is its constraint. Rules by mapping cardinality:

    A → A', content satisfies the constraint of A'
        content transferred unchanged, even if the constraint changed
        (for example, a widened range)

    A → A', content violates the constraint of A' or is Unknown under it
        an explicit conversion is required; without one, activation is
        rejected

    A → ∅
        content is discarded; resources it owns stay owned by the
        old version and are destroyed when that version is retired
        (section 7)

    A → (A', A'')
        an explicit transfer function must produce each destination's
        content; content is never duplicated implicitly

    (A, B) → C
        an explicit merge function is required

    A with no declared continuity
        activation is rejected if A holds live content

    A → X, where X is not a cell
        activation is rejected: the content would be lost without an
        explicit disappearance

The last rule follows the transformation model: preservation is not
continuity. Tools that produce transformations, including the embedded
compiler, are expected to declare identity mappings (`A → A`) for cells they
leave untouched, so this rule costs nothing in the common case.

A cell in `S₁` with no incoming mapping from a cell, including one whose only
incoming mappings come from non-cell entities, is initialized by its own
initializer. A conversion declared for such a cell rejects the activation,
because there is no content to convert.

Every content that reaches a cell of `S₁` is checked against that cell's
constraint in the runtime's evaluation context: transferred content,
conversion output, and initial content alike. Anything but `Satisfied`
rejects the activation.

Provisionally, conversions are the third component of the transformation
definition, next to changes and mappings. A conversion is declared per
destination cell and receives the content of every cell mapped into it,
keyed by source cell, which covers one-to-one changes, splits, and merges
alike. The definition names each conversion; executable converters are
supplied at activation, as evaluators are for External constraints, so the
definition stays pure data. A missing converter rejects the activation, and
a converter failure propagates without changing the runtime.

A conversion declared for a one-to-one mapping is always used, even when the
transferred content would already satisfy the destination's constraint. Its
output is checked like any other content.

## 5. Code in flight

**Decided:**

A frame that is executing when an activation happens keeps executing in the
version it started in, and holds that version.

**Open:**

The strategy for switching code in flight, described below.

Some threads may be executing code of entities that the transformation
changed or removed. Options:

    version coexistence
        running frames continue in the old version; new calls enter the
        new version. Erlang switches at fully qualified calls; local calls
        stay in the version already running.

    explicit update points
        the program declares where activation may take effect; activation
        waits until every thread reaches one (Kitsune for C).

    quiescence
        activation waits until no thread executes changed code.

    on-stack replacement
        live frames are rewritten into frames of the new version. This
        requires continuity for locals and execution positions and is the
        most general and the most complex option.

These can be combined per thread: each thread switches when it reaches a safe
point, as Linux kernel livepatch does per task.

A reasonable starting point is version coexistence with switching at call
boundaries or explicit update points. On-stack replacement can come later.

**Provisional:**

The language uses version coexistence with switching at every call
(metaprogramming.md section 5). The running language frame retains its
starting version, while every subsequent linked call resolves and enters
the function from the currently active version.

## 6. References across activation

**Decided:**

References are state-pinned. Activation is exactly the one step through which
runtime-held references into `S₀` are transferred:

    unique continuation
        reference is transferred to S₁ (transfer_reference)

    disappearance, ambiguity, or unknown continuity
        reference stays pinned to S₀

A pinned reference keeps the old version alive (section 7). It is never
silently rebound to an unrelated entity in `S₁`.

Pinning is the default. A program may opt into a stricter policy that
rejects activation when any live reference cannot be transferred.

## 7. Retiring superseded versions

**Decided:**

Retirement of old versions uses the ownership model rather than a separate
lifetime mechanism. The same rules apply to runtime state as to program
state: one owner per entity, no cycles, and recursive destruction of an owned
subtree.

    runtime root
        owns the active version
        owns superseded versions that are still in use

    version
        owns its native code
        owns cells and resources that did not transfer at activation

Retiring a version destroys its owned subtree. Resources of cells that
disappeared at activation (`A → ∅`, section 4) remain owned by the old version
and are destroyed with it.

Ownership alone cannot say when retirement is allowed. Many threads, frames
and pinned references can depend on the same old version, and ownership
permits only one owner. These dependencies are therefore recorded as holds on
the version:

    frame executing old code             holds its version
    reference pinned to S₀ (section 6)   holds the version of S₀
    function pointer, return address     holds the version it points into

A superseded version is retired when nothing holds it any more.

A hold is deliberately much narrower than a borrow:

- it is coarse: it applies to a whole version, not to individual objects;
- it is dynamic: the runtime tracks it, for example with an epoch or
  RCU-style grace period, or a count per version;
- it is internal: it does not appear in types, has no lifetimes or aliasing
  rules, and user code never creates or checks one.

SHEAR does not introduce a general borrowing system to retire versions.

At most two versions run in one runtime: the active version and the previous
one, as in Erlang. Two is the minimum compatible with pinned references
(section 6) and with activation that does not stop every thread. A
single-version bound would require every activation to wait until no thread
runs old code, and to reject every reference it cannot transfer.

A new activation that arrives while the previous version is still held is
rejected by default. The active version and runtime state stay unchanged,
consistent with atomic activation (section 2).

A program may explicitly choose another policy instead: wait for the holds
to end (possibly with a timeout), or terminate the holders, as Erlang
terminates processes still running purged code. Terminating a thread is
destruction of what that thread owns.

## 8. Speculative versions

**Decided:**

The two-version bound applies to versions running in one runtime, not to
produced states. Candidate states are immutable values: any number of them can
be produced, compared and validated without activation.

A candidate that must be exercised, not only validated, runs in an isolated
runtime:

- it has its own runtime root, so its versions do not count against the main
  runtime's bound;
- its live state is a copy of the relevant main-runtime state, produced by the
  same transfer functions that activation would use;
- it receives only the capabilities the trial grants, so its effects stay
  contained.

A trial run therefore also tests the state-transfer functions before the real
activation. A candidate becomes a version of the main runtime only through
activation (section 2).

A trial copies cell content only. Runtime-held references and frames belong
to the main runtime and are not copied, so the isolated runtime starts with
no holds. Until capabilities are modelled, what a trial grants is its
evaluation context, which defaults to the main runtime's, and the converters
it is given.

**Provisional:**

The language runs code under trial without the activation capability
(language_trials.md section 3).

## 9. Rollback

**Decided:**

`S₀` remains an immutable, valid state after activation. Returning to it is a
new activation `S₁ → S₀` with its own continuity mappings and conversion
functions.

Runtime state transferred during the first activation is not automatically
restored. Consistent with the transformation model, reversibility is not
implied by the existence of a forward transformation.

## 10. Native code

**Open:**

The embedded compiler regenerates the executable representation of `S₁`.
Native code can be cached by `VersionID`, so entities whose version is
unchanged reuse existing code.

**Provisional:**

The reference model's hosted route (live_evolution.md,
hosted_bootstrap.md section 6) has the analogue for its admitted artifacts. A
loaded version owns the artifacts compiled for its state, not the `StateID`,
because two loaded versions can have one state. A candidate built by a
running program is compiled and admitted whole when it is activated or tried,
before the switch or the trial run; an artifact is reused when the entity and
its version are unchanged, the owner is the same, the same compiler produced
it and the chunk still validates against the new state. A version's set is
released when the version retires, and a trial's when the trial ends. This
concerns derived artifacts only; native code and its platform policies stay
open.

Installing new native code interacts with W^X memory policies, code signing,
and platforms that forbid runtime code generation. These are listed as open
areas in the README.

## 11. Relation to other models

- **Transformation model**: supplies `S₁` and the continuity mappings.
  Activation adds no continuity of its own.
- **Reference model**: activation is the one-step transfer for runtime-held
  references.
- **Ownership model**: retirement of superseded versions is recursive
  destruction of an owned subtree, gated by runtime holds (section 7). No
  general borrowing system is introduced.
- **Constraint and contract models**: supply the validation performed before
  activation.
- **State model**: activation selects a state; it does not mutate any state.

## 12. Current implementation status

The Python reference model currently provides:

    CellDeclaration
        declares a mutable cell (constraint and initial content) as a value in
        program state

    Runtime
        mutable runtime state of one program: the runtime root owns the
        loaded versions, each Version owns the content of its cells, and
        reads and writes never change program state or StateID; cell
        content is checked against the cell's constraint on load and on
        every write, and anything but Satisfied is rejected

    Hold, Frame, KeptReference
        runtime-internal holds on a version from simulated frames and from
        references kept in runtime state

    Runtime.activate
        staged, atomic activation of a transformation result (or of a bare
        state, with unknown continuity): cell transfer by the rules of
        section 4 with named Converters, reference transfer or pinning
        (section 6), rejection while the previous version is held, and
        retirement of a superseded version when its last hold is released
        (section 7); a result from an earlier active state is rebased over
        the results activated since (section 2)

    Runtime.trial
        runs a candidate in an isolated runtime with its own root: cell
        content is staged exactly as activation would stage it, the trial
        is rejected whenever the activation would be, and the main runtime
        is unchanged and not limited by its two-version bound (section 8)

The language layer in `shear.lang` additionally provides:

    Function
        semantic function value containing parameter names and expression
        body

    quote / unquote
        construction of expression trees with evaluated holes

    function
        construction of Function values from evaluated parameter and body
        expressions

    activate
        capability-gated self-modification using an explicit identity mapping
        for every entity and the existing atomic Runtime.activate path

    trial
        exercises a candidate in an isolated runtime via the same pair
        checks and identity mapping as activate, then calls the linked
        function there with the activation capability withheld
        (language_trials.md)

Frames keep executing in the version they started in; the switching strategy
for code in flight (section 5) is implemented by the language as
version coexistence with switching at every linked call.

`shear.runtime.listening` and `VersionListener` let a host follow versions
for a run: it is told of a staged and accepted candidate of an activation or
trial before anything changes (and may refuse it), of a retiring version and
of the end of a trial. The hosted route uses it to keep per-version artifact
sets (section 10); a runtime with no listener behaves as before.

## 13. Unresolved areas

- switching strategy for code in flight beyond the language's provisional
  one (section 5);
- conversion rule and placement, currently provisional (section 4);
- how the runtime tracks holds on versions (section 7);
- capability isolation for trial runs beyond the language's provisional one
  (section 8);
- concurrency: per-thread switching and its memory model;
- native code installation under platform restrictions.

## 14. Design principle

Activation is an explicit, atomic transition of the running program from one
immutable program state to another.

Live runtime state crosses that transition only along declared continuity,
with explicit conversion where its shape changes. Anything that cannot cross
stays pinned to the version it belongs to, or the activation is rejected.
