# Canary Corpus

**Status: implemented.** `shear/examples/` exists; the acceptance tests in
`tests/test_corpus.py` pass.

A library of small programs with expected results. Every interpreter and
every representation of code must run the whole corpus unchanged. That
turns a change of representation (roadmap.md task 4) into a differential
test, and each program the language cannot express yet names a missing
feature.

## 1. Scope

**Decided.**

In scope: tier 1, programs the current language (`shear/lang.py`) can
express; the data format; `play`, which runs an example with a given
interpreter; the list of wanted programs the language cannot express yet.

Out of scope: host-driven transformations (renames and other host edits
stay in the acceptance tests of the language); benchmarks; a standard
library.

## 2. Format

**Decided.**

Module `shear/examples/` (a package, so programs can be split across
files):

    Raises(error)
        expected outcome of a step that must raise `error` (a subclass
        counts)

    Step(entry, args, expect, may_activate=False, cells={})
        one run: `run(runtime, entry, *args, may_activate=...)` must
        return a value semantically equal to `expect` (compared by
        canonical serialization, so True != 1), or raise as `Raises`
        says; afterwards each cell in `cells` must hold that content

    Example(name, tags, program, scenarios, context=None, description="")
        `program` is a State in the input format (tuple Function bodies
        and links relations); each scenario is a tuple of Steps run in
        order against one fresh `Runtime(load(program), context)`, the
        program loaded into graph form (graph_form.md)

    Wanted(name, needs)
        a program the language cannot express yet, and the feature it
        needs

    EXAMPLES: tuple[Example, ...]
    MISSING: tuple[Wanted, ...]
    TAGS = frozenset({"recursion", "side effects", "control",
                      "self-modification", "data", "higher order",
                      "errors"})

    ExampleFailed(AssertionError)
    play(example, run)
        runs every scenario with the given `run` function and raises
        ExampleFailed, naming the example, scenario and step, at the
        first mismatch; a step expecting a value that raises instead is a
        mismatch too

`run` has the signature of `shear.lang.run`; another interpreter passes
its own.

## 3. Tier 1 programs

**Decided**, the list itself is open-ended.

At least ten programs, covering every tag:

- recursion: factorial, fibonacci, gcd, sum to n, Collatz step count;
- control: absolute value, max, clamp or sign;
- side effects: a counter, an account whose balance cell rejects an
  overdraft (a step that raises `CellContentRejected` and a later step
  showing the balance unchanged);
- self-modification: the power compiler that compiles and activates, a
  compile that installs only after a `trial`, a function that replaces
  itself.

A side-effect example must check cells, or have a later step whose result
depends on an earlier write. A self-modification example must have a step
whose result shows the new code, run with `may_activate=True` where it
activates.

Tier 2 (roadmap.md task 6, language_data.md section 5) adds:

- data: `insertion_sort`, and `let_bindings` (a discriminant named once, a
  side-effecting bound expression that runs once, a `let` that reuses a
  parameter's name and raises);
- higher order: `map` and `fold`, run with function references passed as
  arguments;
- recursion: `deep_loop`, tail-recursive loops thousands of calls deep,
  through `call`, through `apply` and between two functions; and, after
  roadmap.md task 7, `deep_recursion`, a sum by recursion that is not a
  tail call, ten thousand calls deep;
- higher order and recursion: `map_long_tuple`, `map` over tuples of a
  thousand and two thousand elements;
- self-hosting (roadmap.md task 8): `compiler`, `lower` written in SHEAR,
  and `instrument`, a program that reads its own function, swaps in a
  version that counts its calls and compiles what it installed
  (self_hosting.md);
- self-hosting (roadmap.md task 10): `bootstrap`, the compiler swapped for
  functions that run their own chunks on an interpreter written in SHEAR,
  then compiling again (vm_in_shear.md);
- self-modification: `sort_swap`, which sorts a tuple in a cell with the
  function `order` refers to, activates a different `order` between two
  runs, and sorts again with the data still in its cell;
- closures (roadmap.md task 17): `make_adder`, which returns a closure
  capturing its argument by value, and `compose`, which returns a closure
  capturing callable values and applying them in composition;
- errors (roadmap.md task 20): `safe_install`, `account_report` and
  `lookup`, covering catchable failures, selective filters, program-raised
  errors and failure values.

The task-20 error examples exercise distinct boundaries:

- `safe_install` trials candidate implementations of `power` under `catch`.
  A candidate that indexes an empty tuple reports `out_of_range`, and a
  runaway recursive candidate reports `depth_limit`; neither is installed.
  A candidate that merely returns the wrong value is rejected normally, and
  only the correct candidate is activated.
- `account_report` increments an attempt counter before writing a constrained
  balance. It catches only `cell_rejected`, so an overdraft becomes
  `("refused", "violated")` while the earlier attempt write remains visible:
  `catch` does not roll back effects. Passing a string instead of an integer
  produces a language error that is not accepted by the filter and therefore
  still escapes.
- `lookup` uses `raise("missing", ...)` for an absent key. `find_or` catches
  only that program error and returns a default, while malformed table data
  still produces the language's `wrong_kind`. `why` catches both and exposes
  their origin, kind and detail as ordinary values.

## 4. Wanted programs

**Open.** Recorded in `shear/examples/missing.py` (`MISSING`).

`MISSING` is currently empty. The gaps discovered while extending the corpus
have all been closed by implemented roadmap tasks.

**Closed** by roadmap.md task 17: `make_adder`, the last remaining gap.
It needed an executable anonymous callable that captures bindings from its
creating lexical environment. `ref` names an already-installed function,
while `function` remains code as data that must be installed with `activate`.
Closures add the missing distinction: an executable value with explicit,
by-value lexical captures. `make_adder` and `compose` are now corpus examples.

**Closed** by roadmap.md task 7: `map_long_tuple`, which needed non-tail
recursion deeper than the Python stack. Tail calls (task 6) made loops
unbounded, but a call that was not in tail position still nested about 5
Python frames, so `map` failed from a tuple of 200 elements and
`insertion_sort` from 200. The bytecode machine keeps its calls on its own
stack (bytecode.md), and the examples `map_long_tuple` (a thousand and two
thousand elements) and `deep_recursion` (a sum ten thousand calls deep) are
tier 2.

**Closed** by roadmap.md task 6: the four programs this list first
recorded, now tier 2 examples. What each needed, as first written:

- `insertion_sort` needs a way to take a tuple apart at runtime (head/tail
  or an index operation) and a length operation, to iterate over a sequence
  of unknown length. The language only has fixed-shape literal tuples and
  `quote`/`unquote` for shaping code, not for walking runtime data whose
  length isn't known when the program is written.
- `map_and_fold` needs an `apply` operation that calls a function *value*
  directly: `call` only dispatches through a static link name resolved via
  the calling function's own links relation, so a function received as an
  argument or read from a cell cannot be invoked. It also needs the same
  tuple decomposition as insertion sort.
- `local_variables` needs a `let`/local-binding form to name an
  intermediate value within one function body; the only binding mechanism
  is a call's parameters.
- `deep_loop` needs tail-call elimination, or an iteration primitive, in
  the reference interpreter. The language has no loop construct, only
  recursion, and every `call` nests further Python stack frames in
  `shear/lang.py`'s `_call`/`_eval`. Measured against the `sum_to_n`
  tier-1 example: under the interpreter's default recursion limit of 1000,
  `sum_to_n(197)` succeeds and `sum_to_n(198)` raises `RecursionError` -
  about 5 Python stack frames per SHEAR call (measured on graph form;
  the tuple-body interpreter stopped one call earlier).

## 5. Acceptance tests

`tests/test_corpus.py` pins the format and the canary property: the corpus
must fail under deliberately broken interpreters (wrong integer results,
lost cell writes, an ignored activation grant, swallowed errors). The
implementation is done when it passes without changes.

Task 20 additionally uses the three `errors` examples as cross-boundary
canaries. They must run under the ordinary language path, round-trip through
text syntax, and add golden records without changing the golden records of
any pre-existing program (`tests/golden.py`).

## 6. Implementation notes

- Programs are data. Build them with `shear.lang` (`Function`, `links`)
  and core constructors only; host code appears only as evaluators in an
  example's `context`.
- Keep each program small and readable; one module per tag is fine.
- When done: add a `CHANGES.md` entry and mark this document's status.

## 7. Design canaries

**Provisional:**

Unusual programs are design tests: a DSL, an ontology, a small store. Each
asks whether it can be written as an ordinary SHEAR program or library
without a new privileged mechanism. With implementation cheap, a precise
discriminator like this is the scarce resource.

A canary ends in one of: passes naturally; passes with an opaque or
specialized representation; reveals a missing reusable abstraction; reveals
too much core responsibility; not relevant yet. Failures count as evidence
for a missing core abstraction only when the canaries exercise independent
requirements, not one shared deferred prerequisite.

Canaries are not acceptance tests. Use them when adding a major semantic
mechanism, deciding what belongs in the core, generalizing, judging whether
relations earn their cost, designing metaprogramming or DSL facilities,
moving the boundary between semantic and derived representations, or adding
privileged compiler or runtime behaviour.

A canary that runs becomes a corpus example only if it is a stable semantic
discriminator worth keeping. A blocked canary becomes a `Wanted` entry
(section 4) only if review concludes that its missing capability is a
reusable language requirement, not merely something this canary needs. A
canary that re-implements a core mechanism as a library is evidence for
removing the mechanism, as roadmap task 24 tests for constraints.

The list as written on 2026-10-08
([design canaries](reviews/2026-10-08_design_canaries.txt)), with its status
then:

| Canary | Status | Needs or evidence |
| --- | --- | --- |
| 2. Small embedded language | not yet | program-defined syntax |
| 3. Radically different DSL | not yet | program-defined syntax; the SHEAR VM half-answers it |
| 4. User-defined relationships | blocked | programs creating entities and relations |
| 5. Independent libraries interacting | blocked | entity creation, modules |
| 6. Structured knowledge (an ontology) | blocked | entity creation |
| 7. Database-like application | blocked | entity creation, records |
| 8. Specialized indexed representation | blocked | entity creation, opaque values |
| 9. Large opaque data | blocked | opaque values |
| 10. External resource | blocked | external values |
| 11. Replaceable implementation | partial | interpreters run one corpus; decision D3 |
| 12. Derived executable representation | partial | task 27's wrappers; decision D3 |
| 13. Cheap local edit | passes | bytecode.md section 5 |
| 14. Rename and movement | passes | continuity corpus |
| 15. Split and merge | passes | continuity corpus |
| 16. Long-running evolution | partial | roadmap task 31 |
| 17. Rejected change | passes | `checked_compile`, `safe_install` |
| 18. Repeated evolution | partial | roadmap task 31 |
| 19. Compiler as ordinary program | passes | self_hosting.md, roadmap task 27 |
| 20. Compiler replacement | partial | artifact provenance (roadmap task 30) |
| 21. Compile-time ordinary functions | not yet | a compile-time phase |
| 22. Different execution contexts | partial | only a run and a trial exist |
| 23. Application-defined constraints | experiment | roadmap task 24 |
| 24. Application-defined transformation | blocked | programs declaring continuity |
| 25. Provenance as application data | blocked | entity creation |
| 26. Introspection | partial | artifact provenance |
| 27. Tooling without source authority | partial | Python model only (`render`, `reconcile`) |
| 28. Round trip through another representation | passes | roadmap task 11 |
| 29. Library-defined execution model | passes | the SHEAR VM |
| 30. Specialized computation, external implementation | blocked | opaque values, foreign integration |
| 31. Application stressing relations more than code | blocked | entity creation |
| 32. Application barely using relations | passes | the recursion and control examples |

**Post-D3 clarification (2026-10-10):** D3 is now Decided (roadmap
task 29, PR #91): authenticated host execution of SHEAR-compiler-produced
per-node artifacts is the primary route, with the SHEAR VM retained as an
alternative and correctness reference. The dated table above remains
historical. Canaries 11 and 12 remain partial: the architecture is selected,
but Task 29 did not demonstrate a complete replaceable runtime or
source-preserving compiler rebuild on the admitted route. Those require
Task 30 and, for live evolution, Task 31.


### Application-level canaries

**Provisional – future research, not committed roadmap work.**

The architectural canaries above test individual mechanisms. Application-level canaries test whether those mechanisms work together to make useful software substantially easier to construct, modify or reason about.

| Application | Minimal experiment | Primary discriminators |
| --- | --- | --- |
| Genetic programming | Evolve executable programs for symbolic regression through mutation, crossover, fitness evaluation and selection | Semantic identity, graph transformations, provenance, trials, activation |
| Versioned workflow engine | Change process definitions while preserving and selectively migrating active instances | Continuity, retained versions, state migration |
| Long-running simulation | Replace an algorithm or physical model without restarting the simulation | Live activation, old frames, retained state, external computation |
| Adaptive agents | Generate, evaluate and activate alternative decision procedures | Program introspection, controlled self-modification, capabilities |
| Semantic development tools | Implement structural editing, semantic diffs and refactoring independently of source-text positions | Persistent identity, transformations, source independence |
| Embedded DSLs and knowledge systems | Define application semantics, relationships and transformations using ordinary libraries | Generality of relations, extensibility, application-defined transformations |

**Evaluation protocol**

For each experiment:

1. Define a bounded workload, required capabilities and falsifiable predictions before implementation.
2. Implement it using ordinary SHEAR facilities, documenting necessary host services and missing capabilities.
3. Compare against a conventional implementation with equivalent behavior.
4. Measure development complexity, correctness, performance, resource costs and the value of semantic identity and continuity.
5. Classify the result using the existing design-canary outcomes.

A working implementation alone does not demonstrate architectural superiority. A failed application does not automatically justify another language primitive.

**Genetic programming and potential self-evolution**

Genetic programming is the first proposed substantial research application (issue #99). Begin with constrained symbolic regression and structural evolution of canonical semantic graphs.

If successful, investigate using the same mechanisms to optimize SHEAR's compiler or transformation passes. Semantic correctness and independent verification remain hard constraints; performance and implementation complexity may be optimization objectives.

Evolution of language semantics requires separate specifications and explicit decisions. Genetic search is an application/library mechanism, not a privileged language feature.

**Dependencies and timing**

Task 31 establishes the initial live-evolution foundation. Program-directed entity creation, application-defined transformations, external resources and persistence may require further work.

These experiments remain independent future research. None is a prerequisite for Task 31 or an automatic addition to the language roadmap.
