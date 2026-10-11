# Reading Code, and a Compiler in SHEAR

**Status: implemented** (roadmap.md task 8; extended by task 17).
`shear/lang.py` and `shear/bytecode.py` implement `code`;
`shear/examples/compiler_source.py` holds the compiler and
`shear/examples/self_hosting.py` the self-rewriting program; `tests/test_self_hosting.py` is the main acceptance suite, with
closure lowering additionally pinned by `tests/test_closure_self_hosting.py`.

Two pieces: an operation with which a program reads the code of a function
as data, and the lowering pass of bytecode.md written in the language,
checked against the host's. The original task-8 scope was that the compiler
emits bytecode as data and is checked against the host, while the host runs
only what it lowers itself. Running what the compiler emits was added in
roadmap task 10 (section 5). D3 subsequently selected authenticated
host execution of SHEAR-compiled derived artifacts (roadmap task 29).

## 1. `code`

**Decided:**

The `code` operation, including which version it reads. Active-version
semantics were confirmed by D4 (roadmap.md, decision D4; issue #92).

    ("code", link)      (params, body) of the linked function, in input form

`params` is the tuple of parameter names and `body` the expression tree that
`function_at` returns and that `load` accepts: link names as written, labels
as `("label", name, e)`. It is the same data `quote` builds, so a program
can take it apart with `item`, `slice` and `len`, rewrite it and hand it to
`function`. In graph form `code` is a node with a `target` role and the link
name as payload, exactly like `ref`, so a rename of the function follows by
continuity. It lowers to one instruction, `CODE f name`.

- It reads the function from the **active** version, not from the version
  the running frame was entered in. After an `activate` in the same run,
  `code` shows the code the next call would run. Reading needs no
  activation capability.
- A link that does not resolve is an `invalid` node, and a link that names
  something that is not a function is a `LanguageError`, both when the node
  runs.
- Tuples in the result that come from a canonical value read at run time
  may be canonical nodes, as for any tuple the language takes apart. They
  compare equal to plain tuples by `eq` and by canonical serialization, not
  by Python `==`.
- Installing a function's own code back with `activate` and `function`
  gives the same input form. Continuity of matching nodes across a
  whole-function edit is handled by the continuity-inference rules of
  roadmap task 13.

## 2. The compiler

**Provisional:**

The shape of the output and what is covered.

`lower(e)`, in `shear/examples/compiler_source.py`, takes an expression in
input form and returns its chunk. The host's chunk names its children by
`EntityID` (bytecode.md section 2); a program has no entities for the
expression it is holding, so the chunk it produces holds each child's chunk
in place of a reference. Called the *expansion* of a node:

- `EVAL c`, `GOTO c`, `BRANCH a b`, and `LETBIND name c` hold child chunks;
- `CLOSURE body params captures` holds the expanded closure-body chunk plus
  its parameter and capture-name tuples;
- an operand that is an entity (`CALL f k`, `REF`, `CODE`, `READ`, `WRITE`)
  is the link name, and `REF f name` becomes `REF name`;
- `LIT v` holds the value.

`tests/test_self_hosting.py` computes the expansion of the host's chunk of
the same expression and compares it with `lower`'s output.
`tests/test_closure_self_hosting.py` performs the same independent comparison
for closure lowering, including expansion of the closure body.

Covered: every operation of the language except `quote`, `unquote`,
`function`, `activate`, `trial`, `catch` and `raise`; `label` costs nothing,
as in graph form.
`closure` is covered since roadmap task 17.

Anything else lowers to `RAISE "unknown operation"`. The compiler assumes a
well-formed expression: it does not check arities, link names, closure capture
validity or `let` names that the host's graph construction already validates
or turns into an `invalid` node. An empty `seq` is the one malformed shape it
checks directly, as it is the one the host also reports as a node.

The compiler is written in the language it covers: `lower`, `upper`
(opcode names), `evals` and `seq_code` (the variable-length operand lists)
use only covered operations. `self_lower()` compiles `lower` by reading it
with `code`, and the test compares that with the host's chunk of `lower`.

Adding closure lowering did not require changing the bootstrap model:
`CLOSURE` is ordinary emitted bytecode data, and the compiler itself remains
inside the subset it can compile.

The current expanded output does not preserve the host's per-node artifact
boundaries or semantic child identities. It is not itself the admitted
per-node representation selected by D3. Task 30 must establish the required
node/version mapping and compiler provenance without replacing canonical
graph source.

## 3. Checks

**Decided:**

- Every ordinary operation the compiler covers, in a curated list.
- 60 seeded random expressions over the covered pre-closure operations.
- Closure lowering compared independently against host lowering.
- Each function of the compiler, lowered by the compiler, against the host.
- `self_lower`, the program that reads and compiles its own `lower`.
- Unsupported operations lowering to `RAISE`.
- The bytecode interpreter written in SHEAR running compiled closure code
  (roadmap tasks 10 and 17).
- Mutation testing (`SHEAR_MUTATE`) of the compiler implementation.

The closure-specific comparison is structural, not merely a check that the
compiler avoided `RAISE`: the self-hosted chunk must equal the expanded host
chunk.

## 4. A program that rewrites itself

**Decided:**

The corpus example `instrument` has a cell `hits`, a function `work(x)` and
a function `instrument()`. `instrument` reads `work` with `code`, builds a
function whose body is `work`'s body behind a write that adds one to `hits`,
activates it, and then compiles the code now installed with `lower`, which
sees the new version. Its result is the chunk of what it installed. The
test compares that with the host's expansion of the installed nodes; the
scenario checks that `work` counts, that the swap needs the activation
capability, and that no function but `work` changes version.

Closures do not change this mechanism. `Function` remains code as data for
program construction and activation; `Closure` is a separate executable
runtime value and does not replace `function` in self-modifying code.

## 5. Running emitted bytecode

**Decided:**

The original task-8/task-10 boundary prohibited the host machine from
executing arbitrary program-provided chunks: bytecode is a derived artifact
of the semantic graph, and the ordinary host path runs host-lowered chunks.
That restriction on arbitrary program-supplied bytecode remains in force.

Roadmap task 10 added `vm_in_shear.md`: a bytecode interpreter written in
SHEAR runs the chunks the compiler emits. A program can therefore compile a
function of its own, pass that bytecode as data to the interpreted VM, and
bootstrap the compiler onto that path without granting arbitrary bytecode
execution to the host machine.

Roadmap task 17 extends that independent path with `CLOSURE`. The compiler
written in SHEAR emits closure bytecode, and the VM written in SHEAR
constructs and applies its own tagged closure representation.

**D3 – Decided** (roadmap task 29, PR #91): The primary hosted route
permits the host machine to execute SHEAR-compiler-produced per-node chunks
only through host-internal, fail-closed admission bound to semantic node
and version, with observed compiler provenance and structural verification.
This is not a program-visible chunk installation facility. Task 29
demonstrated the rule only for a bounded subset; Task 30 must integrate
the complete admitted-execution pipeline.

Retain the SHEAR-written VM as an alternative execution path, correctness
reference and possible bootstrap component. Share underlying semantic
contracts, operation metadata, compiler pipeline, compatible executable
IR and runtime services where practical, without forcing the two executors
to use the same runtime representation or compromising independent
behavioral checks. The exact shared implementation boundaries remain
provisional for Task 30.

Their observable behaviour over the supported subset must agree.

## 6. Open

**Open:**

- Whether `code` should take a function reference (`ref`) instead of a link,
  so a program can read a function it only holds as a value.
- Whether reading code should expose semantic node identities directly,
  rather than only collapsed input form.
- Covering `quote`, `function`, `activate`, `trial`, `catch` and `raise` in
  the compiler.
- Whether malformed closure expressions should receive more validation in
  the self-hosted compiler itself rather than relying on the ordinary graph
  construction path.
- Values taken apart at run time may be canonical nodes; whether a run
  should hand back plain tuples is open.

Host execution of authenticated compiler-produced artifacts is decided by
D3, not an open choice. Exact admission, source-preserving compilation,
artifact lifecycle and integration are Task 30 work (roadmap.md).
