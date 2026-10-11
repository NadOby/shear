# SHEAR

**Semantic Hypergraphs Evolving Algebraic Relations**
(recursively, SHEAR Hypergraphs Evolve Algebraic Relations)

SHEAR is a minimalist systems programming language built around a semantic
graph as the canonical representation of a program.

Every SHEAR program carries its own compiler. A running program retains its
semantic graph and the transformation machinery that produced its executable
representation, so it keeps the ability to modify itself: it can produce a new
version of its own program state, validate it, and activate it.

Much of the design follows from this goal:

- immutable states and separate produce and activate steps make
  self-modification safe, because a new version is built and checked before it
  replaces anything;
- explicit continuity tells the running program how live state in the old
  version corresponds to the new one;
- capabilities decide whether a program may modify itself at all.

> Graph is the program. Every program carries its compiler. Values are
> immutable. Identity is not equality. States are immutable. Transformations
> produce states. References are state-relative. Continuity is explicit.
> Runtime and semantic computation use the same function model. Capabilities
> describe authority. Effects describe behaviour. Constraints establish what
> is known. Contracts describe values. Source and machine code are
> representations. Tooling operates on semantics.

## Status of the reference model

The executable reference model in `shear/` (section 24) now demonstrates
three of the claims above. Design and history: [`docs/`](docs/),
[`CHANGES.md`](CHANGES.md), [`docs/roadmap.md`](docs/roadmap.md).

**The graph is the program.** Immutable states with content-derived
identity; transformations with explicit continuity (renames, merges,
splits, disappearance), which relation endpoints and ownership follow;
three-valued constraints, including constraints over relations. Code itself
is graph form: every expression node is a relation entity owned by its
function, so an edit, a rename or a deletion keeps the identity of
everything it does not touch ([`graph_form.md`](docs/graph_form.md)).

**Programs modify themselves.** A running program builds code as data,
tries it in an isolated runtime, and activates it atomically, for whole
functions or single labelled nodes, under a capability grant and its own
constraints. Mutable cells keep their content across activations; running
frames finish in the version they started in
([`metaprogramming.md`](docs/metaprogramming.md),
[`language_trials.md`](docs/language_trials.md),
[`activation_model.md`](docs/activation_model.md)).

**Programs carry their compiler.** Graph form is lowered to bytecode, cached
per node version, and run on a VM with an explicit stack. The lowering pass
and a bytecode interpreter are also written in SHEAR, and the compiler
reaches a bootstrap fixpoint on its own source
([`bytecode.md`](docs/bytecode.md), [`self_hosting.md`](docs/self_hosting.md),
[`vm_in_shear.md`](docs/vm_in_shear.md)). The hosted pipeline compiles
and admits per-node artifacts with that compiler
([`hosted_bootstrap.md`](docs/hosted_bootstrap.md)). Constant folding is a graph
transformation that declares its merges
([`constant_folding.md`](docs/constant_folding.md)).

A canary corpus of small programs (`shear/examples/`,
[`corpus.md`](docs/corpus.md)) and seeded mutation tests check all of this.

**How the vision changed on contact with code.**

- Code is stored as graph form, not as opaque function bodies; tuple bodies
  with links remain only an input format (roadmap D1).
- Deletion and disappearance are one operation: an owner's disappearance
  ends what it owns, and a transformation places what it creates
  ([`ownership_model.md`](docs/ownership_model.md) §7, §10).
- A constraint over an owner sees its owned subtree
  ([`relation_model.md`](docs/relation_model.md) §7), and a relation may
  have no roles.
- Ownership edges follow declared continuity, as relation endpoints do.
- The compiler emits bytecode, data a program can produce itself, rather
  than host closures (roadmap D2).

**Provisional**, named where they are specified: switching code in flight
at every call; the per-run activation grant and trials without it; a
function's `definition` relation, node identities and flat node ownership;
function references as `EntityID`s that do not follow renames when held in
cells; the bytecode and VM shapes; the operations of constant folding; the
output of the SHEAR lowering pass and the pure-code limits of the SHEAR
VM.

**Text editing now exists.** `parse` and `render` provide the text
representation, and `reconcile(state, text)` turns edited text into a
transformation using the same continuity inference as `define`. Lexical and
program-global name resolution are specified for the current single-root
program model. Cell declaration edits and explicit modules remain deferred
([`syntax.md`](docs/syntax.md), [`name_resolution.md`](docs/name_resolution.md)).

**Not touched yet:** systems data (structures, layout, references between
cells), explicit modules, concurrency, native code, capabilities beyond one
grant, and formal semantics.

## Contents

- [Status of the reference model](#status-of-the-reference-model)
- [Canonical program representation](#1-canonical-program-representation)
- [Semantic values](#2-semantic-values)
- [Identity](#3-identity)
- [Immutable states](#4-immutable-states)
- [Transformations](#5-transformations)
- [References](#6-references)
- [Ownership](#7-ownership)
- [Functions and computation](#8-functions-and-computation)
- [Explicitness](#9-explicitness)
- [Types and constraints](#10-types-and-constraints)
- [Equality](#11-equality)
- [Mutation](#12-mutation)
- [Effects and capabilities](#13-effects-and-capabilities)
- [Contracts](#14-contracts)
- [Collections and representations](#15-collections-and-representations)
- [Numeric and textual values](#16-numeric-and-textual-values)
- [Errors and control flow](#17-errors-and-control-flow)
- [Concurrency](#18-concurrency)
- [Modules and names](#19-modules-and-names)
- [Entry points](#20-entry-points)
- [Foreign integration](#21-foreign-integration)
- [Opaque and external values](#22-opaque-and-external-values)
- [Compiler and semantic tooling](#23-compiler-and-semantic-tooling)
- [Reference semantic model](#24-reference-semantic-model)
- [Semantic test corpus](#25-semantic-test-corpus)
- [Formal verification](#26-formal-verification)
- [High-value invariants](#27-high-value-invariants)
- [State identity and provenance](#28-state-identity-and-provenance)
- [Caching and incremental computation](#29-caching-and-incremental-computation)
- [Program modification](#30-program-modification)
- [Metaprogramming](#31-metaprogramming)
- [Representation independence](#32-representation-independence)
- [Serialization and persistence](#33-serialization-and-persistence)
- [Reproducibility and dependencies](#34-reproducibility-and-dependencies)
- [Design philosophy](#35-design-philosophy)
- [Non-goals](#36-non-goals)
- [Open design areas](#37-open-design-areas)

## 1. Canonical program representation

The semantic graph is the canonical representation of a program.

The graph generalizes a hypergraph: it has no nodes and edges, only entities.
A relation is itself an entity, and any entity, including a relation, can be
related.

Source code, intermediate representations, machine code, documentation, debug
information, and other artifacts are representations or derived products of
the semantic program.

Every program image contains:

- the semantic graph;
- the compiler and transformation machinery needed to transform the semantic
  graph and regenerate the program's executable representation.

A program image may also contain:

- semantic states;
- transformations and metaprograms;
- dependency information;
- optional source information;
- optional transformation history;
- cached intermediate or native representations.

Removing source text or transformation history must not change the semantic
program.

History and provenance may be retained for tooling, debugging, reproducibility,
and analysis, but they are not inherently part of semantic identity.

See [`docs/semantic_graph.md`](docs/semantic_graph.md) and
[`docs/relation_model.md`](docs/relation_model.md).

## 2. Semantic values

Everything semantically meaningful is represented as a semantic value.

This includes ordinary data, types, functions, constraints, effects,
capabilities, contracts, transformations, modules, semantic states,
representations, resources, and metadata.

There is no separate fundamental metaprogramming object model.

Metaprogramming operates on the same semantic value model as ordinary
programming.

## 3. Identity

SHEAR distinguishes conceptual entity identity, semantic value version
identity, semantic state identity, and runtime identity.

In particular:

    Entity identity != semantic equality
    State identity != provenance
    Runtime identity != semantic identity

Entity identity is primitive: it cannot be derived from structure, position
or content, because continuity across transformations is stated in its
terms. The semantic-core experiment tested the alternative and falsified it
([`identity_model.md`](docs/identity_model.md) §10).

See [`docs/identity_model.md`](docs/identity_model.md).

## 4. Immutable states

Semantic states are immutable.

A transformation produces a new state rather than mutating an existing state.

Producing a new state and activating that state are separate operations.

Immutable states support persistence, rollback, branching, speculation,
structural sharing, caching, reproducibility, and alternative program
versions.

See [`docs/state_model.md`](docs/state_model.md).

## 5. Transformations

Transformations produce new immutable semantic states and may explicitly
describe entity continuity between the source and destination states.

Continuity is represented as an explicit zero/one/many relation. Reference
transfer across a transformation is state-local and explicit.

Continuity composition currently operates on explicit transformation mappings.
It does not yet constitute full semantic composition of transformation
changes or complete state transitions.

The current transformation semantics are specified in
[`docs/transformation_model.md`](docs/transformation_model.md).

The current continuity-composition semantics are specified in
[`docs/transformation_composition.md`](docs/transformation_composition.md) and
[`docs/transformation_composition_api.md`](docs/transformation_composition_api.md).

## 6. References

References are state-relative and version-pinned.

A reference identifies:

    StateID
    EntityID
    VersionID

Cross-state transfer is explicit and follows a declared transformation
mapping one transition at a time.

Rebinding is separate from continuity-preserving transfer.

See [`docs/reference_model.md`](docs/reference_model.md).

## 7. Ownership

Ownership is a semantic relation concerned with lifetime authority.

Ownership forms a forest: an entity has at most one owner and ownership is
acyclic.

Ordinary references are independent and may form arbitrary cycles.

Recursive destruction of an owned subtree is distinct from transformation
disappearance.

See [`docs/ownership_model.md`](docs/ownership_model.md).

## 8. Functions and computation

Functions are ordinary semantic values.

The same function model is intended to cover:

- runtime computation;
- compile-time computation;
- graph inspection;
- metaprogramming;
- semantic transformations;
- analysis.

There is no fundamental "meta-function" category.

The context in which a function is invoked determines what it may observe or
modify.

**Provisional:** possible contexts include runtime, compilation, expansion,
transformation, trial, migration and analysis. A context may decide the
available capabilities, external access, resource limits, visible semantic
state, allowed mutation, reproducibility requirements, failure handling and
execution budget. A function does not become a different kind of function
because it runs during compilation. Today only a run and a trial exist, and
they differ by the activation grant (docs/metaprogramming.md section 4).

## 9. Explicitness

SHEAR does not require every operation to be syntactically explicit.

Implicit behaviour is acceptable where it has clear, predictable semantics
and provides substantial practical value.

Explicitness is particularly important for:

- semantic-state transitions;
- mutation;
- effects;
- evaluation;
- conversions;
- expensive operations;
- dangerous operations;
- state activation;
- cross-state references.

The purpose is not to maximize syntax. It is to prevent hidden semantic
transitions from becoming difficult to reason about.

## 10. Types and constraints

Types are semantic values.

The type system is intended to be primarily constraint-based.

Constraint evaluation has three possible semantic results:

    Satisfied
    Violated
    Unknown

`Unknown` is a first-class result rather than an implicit failure or success.

Potentially expensive semantic computation may be subject to explicit resource
budgets.

Constraints are immutable semantic values and are evaluated separately from
the constraints themselves.

See [`docs/constraint_model.md`](docs/constraint_model.md).

## 11. Equality

Ordinary equality means semantic equality, not identity.

Equality may be progressive or lazy and may require increasingly expensive
semantic reasoning.

The possible results are:

    Equal
    NotEqual
    Unknown

Expensive, stateful, or potentially nonterminating computation should not be
performed implicitly merely to establish equality.

## 12. Mutation

Values are immutable by default.

Bindings are immutable.

Mutable state is explicitly represented and accessed.

The language distinguishes between:

- creating a new immutable value;
- creating a new semantic state;
- modifying explicitly mutable runtime state;
- activating a different semantic state.

These operations are not interchangeable.

A mutable cell is itself a semantic entity: its existence, identity, and type
(a constraint its content must satisfy) are part of semantic program state and
are versioned like any other entity. The cell's current content is runtime
state. Writing to a cell changes its content in place; it does not produce a
new semantic state and does not change `StateID`. Otherwise every write would
make every reference pinned to that state stale.

Content written to a cell must satisfy the cell's constraint. A runtime
checks each cell's initial content when it loads a version and checks every
write; only `Satisfied` is accepted, so `Violated` and `Unknown` are both
rejected. Program state itself stays pure data: declaring a cell does not
evaluate its constraint.

## 13. Effects and capabilities

An effect describes observable behaviour or dependency.

A capability describes authority.

These are separate concepts.

The initial core effect set is intended to remain small, with additional
effects introduced only where justified.

Capabilities are semantic values representing authority or access.

The exact effect and capability systems remain under development.

## 14. Contracts

Contracts are immutable semantic values that describe other semantic values.

Conceptually:

    Contract -> describes -> Value

Contracts contain requirements and guarantees expressed through constraints.

A contract is not restricted to callable values. It may describe:

- callable values;
- transformations;
- types;
- modules;
- data;
- resources;
- representations;
- semantic states;
- other semantic values.

Requirements describe conditions for contractual applicability or validity.

Guarantees describe properties established when the applicable contractual
conditions hold.

Contract evaluation must preserve the distinction between established,
violated, and unknown conditions where those distinctions apply.

The contract system does not introduce a separate predicate system.

The exact contract composition, refinement, validation, and checking models
remain under development.

See [`docs/contract_model.md`](docs/contract_model.md).

## 15. Collections and representations

SHEAR aims for a small primitive semantic core.

Higher-level abstractions should normally be derived from general primitives
when doing so remains simple and natural.

An abstraction should become primitive where deriving it would introduce
substantial complexity, awkwardness, performance problems, or semantic
ambiguity.

Physical representation is generally distinct from semantic meaning.

## 16. Numeric and textual values

The initial numeric family is expected to include conventional fixed-width
integer and floating-point types.

Byte-oriented data is distinct from text.

The exact numeric promotion, string, Unicode, normalization, and indexing
semantics remain open.

## 17. Errors and control flow

SHEAR does not use exceptions as its fundamental error mechanism.

Errors are explicit values.

A result can therefore be represented conceptually as:

    Result<T, E>

Control-flow semantics remain under development.

## 18. Concurrency

The core language should express concurrency without forcing one implementation
strategy.

Possible implementations include threads, processes, asynchronous I/O,
event loops, work stealing, and other runtime scheduling strategies.

Concurrency safety is expected to integrate with ownership, lifetime, alias
analysis, effects, and capabilities.

The concurrency memory model and task semantics remain open.

## 19. Modules and names

Modules are semantic values.

Changing a module produces a new immutable semantic value or state rather than
silently modifying dependents.

Names are immutable semantic bindings.

Name resolution is intended to operate through semantic scope and graph
relations rather than requiring namespaces as a fundamental semantic primitive.

The exact module, scope, visibility, and name-resolution semantics remain open.

## 20. Entry points

Entry points are ordinary semantic values with execution significance.

A program may contain multiple entry points.

`main` may be a convention rather than a unique semantic primitive.

Executable construction should eventually resolve selected entry points into
explicit semantic references so that program state is coherent and
reproducible.

## 21. Foreign integration

Foreign integration is treated as semantic derivation rather than requiring
SHEAR to parse every foreign language.

A foreign artifact may be used to derive declarations, types, ABI information,
effects, capabilities, contracts, ownership information, and representation
constraints.

Claims about foreign behaviour require explicit contracts, annotations,
analysis, external specifications, or trusted derivation rules.

C ABI interoperability is therefore primarily a semantic integration problem.

## 22. Opaque and external values

Not every semantic value needs to be fully expanded into the semantic graph.

Useful cases include:

    inline semantic value
    opaque represented value
    external resource

An opaque value remains semantically meaningful while its internal
representation is intentionally not exposed.

Expansion is an explicit transformation.

Semantic uniformity does not imply physical uniformity: relationships stay
uniform, representations stay as specialized as efficiency needs, and only
semantic authority must stay with the graph.

## 23. Compiler and semantic tooling

The compiler is primarily a transformation layer operating on the semantic
graph.

The compiler is not only an external build tool. It is part of every program
image, so a running program can apply the same transformation pipeline to its
own semantic graph and regenerate its own executable representation.

Conceptually:

    semantic graph
          |
          v
    semantic transformations
          |
          v
    lower representation
          |
          v
    LLVM / other IR
          |
          v
    target transformations
          |
          v
    machine representation

The same transformation machinery is intended to support compilation,
optimization, refactoring, metaprogramming, program generation, verification,
analysis, and representation conversion.

Tooling should operate on semantic entities wherever possible.

## 24. Reference semantic model

The language specification is accompanied by an executable semantic reference
model.

The initial model is implemented in Python so that semantic behaviour can be
inspected, changed, and tested before introducing formal proof systems.

The Python model is not the language implementation.

It is an executable model of the semantic rules.

Besides the core, it contains a small language layer: `lang.py` (code as
graph form), `bytecode.py` (lowering and the virtual machine), `fold.py`
(constant folding), and `shear/examples/` (the canary corpus, and the
compiler and VM written in SHEAR).

Where the architecture is unresolved, the reference model should expose that
uncertainty rather than silently selecting an arbitrary interpretation.

## 25. Semantic test corpus

The reference model is accompanied by a semantic test corpus.

The corpus checks semantic behaviour and architectural invariants, including
identity, state evolution, references, ownership, transformations,
canonicalization, and negative cases.

Tests should target semantic contracts rather than incidental implementation
details.

A canary corpus of example programs with expected results
([`docs/corpus.md`](docs/corpus.md)) runs under every interpreter and
representation, and seeded mutation tests (`tests/test_mutation.py`) check
that the suite notices planted bugs.

See [`docs/testing_model.md`](docs/testing_model.md).

## 26. Formal verification

Formal verification is a later layer rather than a prerequisite for initial
language development.

Rocq/Coq and K are candidates for future formalization of selected semantic
properties.

Formalization should follow demonstrated semantic stability rather than
freezing immature design.

Likely first targets are stable areas: identity and state, transformation
continuity, activation and version coexistence, and reference transfer. A
formal model is added where it answers a concrete question or verifies a
named invariant, as roadmap task 25 plans with Alloy.

## 27. High-value invariants

The current architecture is organized around several high-value invariants:

1. The semantic graph is the canonical program representation.
2. Semantic values are immutable.
3. Semantic states are immutable.
4. Identity is not equality.
5. Entity identity represents conceptual continuity, not semantic equivalence.
6. State identity represents semantic state content rather than history.
7. References are state-relative and version-pinned.
8. Cross-state reference transfer is explicit.
9. Producing a state and activating it are separate operations.
10. Transformations do not silently mutate source states.
11. Capabilities describe authority; effects describe behaviour.
12. Constraints distinguish `Satisfied`, `Violated`, and `Unknown`.
13. Contracts are independent immutable semantic values.
14. Ownership and ordinary references are separate relations.
15. Source and machine code are representations rather than the canonical
    semantic program.
16. Opaque values do not need to be fully graph-expanded.
17. Foreign integration relies on explicit semantic derivation.
18. Continuity composition does not infer continuity from preservation.
19. Unknown continuity is distinct from known disappearance.
20. Full semantic transformation composition is not implied by continuity
    composition.
21. Every program image carries the compiler needed to transform and
    recompile itself.
22. A mutable cell is versioned semantic state; its current content is
    runtime state and does not contribute to `StateID`.

## 28. State identity and provenance

State identity describes semantic content, not the path by which the state was
produced.

Two transformations can therefore produce semantically identical states while
having different mappings or provenance.

Provenance belongs to transition or transformation records rather than to
semantic state identity.

## 29. Caching and incremental computation

Semantic identity permits caching and incremental computation without making
cache state part of semantic state.

Caches and dependency indexes are implementation data.

An optimization must remain semantically equivalent to recomputation from the
relevant semantic inputs.

## 30. Program modification

Program modification is a transformation over semantic program state.

It produces a new immutable state rather than mutating the currently active
program state.

The resulting state can then be inspected, validated, transformed, compared,
stored, or activated.

Program modification is available to the running program itself, not only to
external tools. Self-modification follows the same path: the program produces
a new state, validates it, and activates it. Whether a program may modify
itself is governed by capabilities.

Activating a new program state while the program runs requires carrying live
runtime state across the change. The intended direction follows Erlang's hot
code loading in spirit: explicit continuity mappings state which entities of
the new state continue which entities of the old one, and the content of
mutable cells is transferred along those mappings at activation, possibly
through an explicit conversion function.

When activation is safe, how long superseded code versions remain alive, and
how they are reclaimed without garbage collection remain open.

See [`docs/activation_model.md`](docs/activation_model.md).

## 31. Metaprogramming

Metaprogramming is performed through ordinary semantic functions.

There is no separate macro language or fundamentally different metaprogramming
object model.

A metaprogram receives semantic values and produces semantic values or
transformations.

Access to program structure is controlled by the relevant capabilities and
contracts.

## 32. Representation independence

A semantic value may have multiple physical representations.

For example:

    semantic value
       |
       +--> source representation
       +--> semantic IR
       +--> LLVM IR
       +--> machine code
       +--> serialized representation

Representation equality is distinct from semantic equality.

A representation may also be opaque.

## 33. Serialization and persistence

Semantic states should eventually be persistable independently of source text
where practical.

Runtime resources require explicit reconstruction or rebinding rather than
being treated as ordinary serialized semantic values.

The serialization format remains open.

## 34. Reproducibility and dependencies

Reproducibility depends on semantic inputs and explicitly selected
dependencies, transformations, representations, and relevant external
assumptions.

Dependencies are semantic relationships and do not necessarily imply
ownership.

The system should prefer explicit coherent dependency state over ambient
mutable environments.

## 35. Design philosophy

SHEAR is not minimal merely for the sake of having few primitives.

The objective is to identify a small set of general semantic mechanisms from
which useful language features can be composed.

A feature should normally be derived from existing primitives when the
derivation is simple, natural, and semantically clear.

A feature should become primitive where deriving it would introduce
substantial complexity, awkwardness, performance cost, semantic ambiguity, or
implementation fragility.

The intended balance is pragmatic.

### Long-term direction

**Provisional:** not scheduled. Recorded so the goals are not lost; the
roadmap decides what is built when (docs/reviews/2026-10-08_ledger.md).

SHEAR's distinctive machinery (the graph, the compiler and the versions every
program carries) is expected to pay off most in large, long-lived systems
that change while they run. The owner does not expect it to suit small
programs such as a hello world or a simple web server; that is an
expectation, not a scope decision. Whether SHEAR is best described as glue
for complex systems or as their control layer is open; either way it remains
a systems programming language.

Beyond the current roadmap, SHEAR aims to make these ordinary programming
rather than compiler construction:

- language malleability in the spirit of Lisp and Forth images: a program
  defines a small DSL (syntax, semantic forms, validation, transformations,
  interpretation or compilation) through ordinary functions and values. The
  machinery stays proportional to the DSL, measured in concepts, code,
  privileged APIs, compile-time and runtime overhead, and integration
  burden. A normal DSL needs no change to the compiler's dispatch, the
  parser's internals, VM instructions or core semantic kinds;
- compiling newly introduced language structures from inside a running
  program;
- independently written libraries whose entities, relations and
  transformations compose through shared language mechanisms;
- unusual applications built as libraries: a new application domain should
  normally need library code, not new primitives.

Unusual programs of these kinds are design tests (docs/corpus.md section 7).
A failure identifies a design pressure to investigate: it may justify a
language change, a library or opaque boundary, or no action yet.

## 36. Non-goals

SHEAR does not aim to:

- make every feature a primitive;
- require formal proofs for every program;
- make every semantic value fully graph-expanded;
- provide unrestricted implicit conversions;
- hide mutation behind ordinary value syntax;
- make source code the canonical representation;
- make machine code the canonical representation;
- require garbage collection;
- provide exceptions as the primary error mechanism;
- force one concurrency implementation strategy;
- solve every systems-programming problem inside the language core;
- absorb application domains into the core: ontology and knowledge-graph
  systems, databases and graph databases, AI architectures and agent
  frameworks, workflow engines, a DSL framework as a product, theorem
  provers, deployment platforms, a particular image format or compiler
  backend. **Provisional:** SHEAR should make unusual systems implementable
  without making unusual systems part of SHEAR.

## 37. Open design areas

The architecture intentionally leaves several areas unresolved until the
semantic model provides enough evidence to choose among alternatives.

Important open areas include:

- exact semantic graph representation;
- exact scope and name-resolution graph;
- module root semantics;
- module version activation;
- pointer and reference rules;
- borrowing;
- alias analysis;
- lifetime analysis;
- ownership transfer;
- object movement and pinning;
- exact string and Unicode semantics;
- collection primitives;
- numeric promotion rules;
- control-flow semantics;
- asynchronous suspension;
- task lifetime;
- concurrency memory model;
- capability revocation;
- capability branding;
- effect inference;
- effect hiding;
- contract composition;
- contract refinement;
- contract validation;
- contract evidence and certificates;
- metaprogram resource budgets;
- exact provenance representation;
- transformation identity and equality;
- full semantic transformation composition;
- formal lossless/lossy transformation semantics;
- transformation deltas and distance measures;
- serialization format;
- foreign export ABI model;
- representation-level guarantees;
- formal operational semantics;
- runtime activation: safe update points, live-state transfer, and
  reclamation of superseded code versions;
- footprint of the compiler embedded in every program;
- self-modification on platforms that restrict runtime code generation.

These are not assumed to be solved merely because a plausible syntax exists.

They should be resolved through consistency with the core semantic model,
implementation evidence, test-corpus behaviour, and practical systems
requirements.

---

<sub>SHEAR was called SEMIROH until October 2026; git history, closed
pull requests and old links use that name.</sub>
