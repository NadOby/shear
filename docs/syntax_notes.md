# Syntax and Tooling Notes

Status: exploratory design notes by the owner, not a language decision.
The first syntax built from them is specified in syntax.md.

---

# Core Principle

SHEAR should have multiple representations of the same program.

No single representation should be forced to serve simultaneously as:

- human source language
- semantic representation
- executable IR

Instead:

```text
Human Source
      ⇅
Semantic Graph
      ⇅
Executable IR
```

The semantic graph remains authoritative.

Source and IR are projections.

---

# Representation Layers

## Human Source

Optimized for:

- readability
- writing
- code review
- learning
- maintenance

Example:

```text
fn square(x):
    x * x
```

---

## Semantic Representation

Optimized for:

- transformations
- validation
- graph operations
- persistence
- versioning

Example:

```text
Function
  params:
    x

  body:
    mul
      arg(x)
      arg(x)
```

or

```text
(
    "function",
    ("x",),
    (
        "mul",
        ("arg", 0),
        ("arg", 0),
    ),
)
```

This layer contains:

- EntityID
- VersionID
- links
- constraints
- ownership
- metadata

and is the source of truth.

---

## Executable IR

Optimized for:

- optimization
- compilation
- JIT
- code generation

Possible forms:

- SHEAR IR
- MLIR
- LLVM IR
- WASM IR

Example:

```text
%0 = load_arg 0
%1 = load_arg 0
%2 = mul %0 %1
return %2
```

---

# Syntax Direction A

Readable Function-Oriented Syntax

Example:

```text
fn increment(step):
    counter = counter + step
```

---

Example:

```text
fn fibonacci(n):
    if n < 2:
        n
    else:
        fibonacci(n - 1) + fibonacci(n - 2)
```

---

Advantages

- familiar
- concise
- easy to teach
- easy to review

Disadvantages

- hides semantic graph structure
- requires parser

---

# Syntax Direction B

Graph-Oriented Syntax

Example:

```text
function increment:
    params:
        step

    body:
        add(
            read(counter),
            step
        )
```

or

```text
function increment:
    step

    write counter:
        add(
            read(counter),
            step
        )
```

---

Advantages

- closer to semantic graph
- simpler parser

Disadvantages

- verbose
- less pleasant for humans

---

# Preferred Direction

Human source should prioritize readability.

Graph structure should be visible in editor tooling rather than source syntax.

---

# Quote / Unquote

Goal:

Code should be editable as code.

Not as nested tuples.

Preferred:

```text
quote:
    x * unquote emit(n - 1)
```

Alternative:

```text
quote {
    x * unquote emit(n - 1)
}
```

Avoid:

```text
("quote", ...)
```

in source syntax.

---

# Function Values

Declaration:

```text
fn square(x):
    x * x
```

Anonymous function:

```text
fn(x):
    x * x
```

Both produce Function values.

---

# Activation

Current semantic form:

```text
activate(...)
```

Human form:

```text
activate:
    power = fn(x):
        emit(n)
```

Possible multiple activations:

```text
activate:
    power = new_power
    helper = new_helper
```

Activation remains atomic.

---

# Links

Human source should not normally expose links.

Example:

```text
fn increment(step):
    counter = counter + step
```

implicitly creates a link to counter.

Semantic graph stores the actual relation.

---

# Variables

Source:

```text
counter
```

means read.

Source:

```text
counter = counter + 1
```

means write.

Human syntax should not expose:

```text
read(counter)
write(counter)
```

except possibly in advanced tooling.

---

# Sequencing

Avoid:

```text
seq(...)
```

Human syntax:

```text
fn bump():
    counter = counter + 1
    counter
```

Last expression returns.

---

# Tooling Vision

Editor operates on semantic graph.

Source editor is only one view.

---

Possible Views

## Source View

```text
fn square(x):
    x * x
```

---

## Semantic View

```text
Function
  EntityID: E42
  VersionID: V17

  params:
    x

  body:
    mul
      arg(x)
      arg(x)
```

---

## Graph View

```text
square
   │
   ▼
  mul
 /   \
x     x
```

---

## Executable IR View

```text
ARG 0
ARG 0
MUL
RET
```

or MLIR.

---

# MLIR Integration

Possible architecture:

```text
Semantic Graph
        ↓
SHEAR MLIR Dialect
        ↓
Standard MLIR
        ↓
LLVM Dialect
        ↓
LLVM IR
```

Possible SHEAR dialect operations:

```text
shear.entity
shear.relation
shear.function
shear.cell
shear.read
shear.write
shear.activate
shear.constraint
```

---

# LLVM / MLIR Position

LLVM and MLIR are compiler backends.

They are not the semantic model.

The semantic graph remains authoritative.

---

## Compiler- and VM-driven language server

**Provisional – future research.**

A SHEAR language server should be a client of the compiler, runtime and VM, not a second implementation of name resolution, semantics or compilation analysis. It keeps the one textual syntax and offers relations, identity, provenance and versions as annotations, navigation and inspectors.

Navigation across source, semantic graph, lowered IR and machine code (where a backend exists) needs provenance that may be many-to-many and incomplete after optimization. Navigation is not editability.

Evaluation happens only when explicitly requested, isolated from external effects and resource-bounded. The server never runs program code implicitly.

---

# Future Multi-View Workflow

```text
             Semantic Graph
                    │
      ┌─────────────┼─────────────┐
      ▼             ▼             ▼

  Source View   Graph View   IR View
```

All views refer to the same semantic program. Source and semantic transformations change it; IR and machine-code views are read-only unless a well-defined reverse transformation exists.

Changes produce a new semantic version.

---

# Long-Term Goal

A function, relation, data structure, transformation, module, or entire program can be viewed as human source, semantic graph or executable IR, and edited as source or through semantic transformations. Identity survives an edit only where continuity is established (docs/continuity_inference.md); a view does not guarantee it.

The semantic graph is primary.

Everything else is a projection.