"""Self-rebuilding compiler demonstration using the SHEAR-written VM.

This module contains the bootstrap example, generation tracking, and compiler
replacement logic. The interpreter itself remains in vm.py.

Imports of VM and vm_entities are deferred until bootstrap construction so
the interpreter can re-export this module without an import cycle.
"""

from __future__ import annotations

from typing import Any

from .. import ActivationRejected, EntityID
from ..lang import FUNCTION_ROLE, Function, links
from . import Example, Raises, Step
from ._support import program
from .self_hosting import LOWER, UPPER, _arg, _item, _lit


ARG_EXPRS = EntityID("arg_exprs")
SWAP_ALL = EntityID("swap_all")
GENERATION = EntityID("generation")

# Functions of the expanded lowering pass, each replaced by a wrapper
# executing its compiled chunk through the SHEAR-written VM.
SWAPPED = (
    "upper",
    "named_tail",
    "child",
    "evals",
    "seq_code",
    "lower_op",
    "lower",
)


def source_name(name: str) -> EntityID:
    return EntityID(f"{name}_source")


def _swap_name(target: str) -> EntityID:
    return EntityID(f"swap_{target}")


def _arg_exprs_body() -> tuple:
    params = _arg("params")
    i = _arg("i")

    return (
        "if",
        ("lt", i, ("len", params)),
        (
            "concat",
            (
                "tuple",
                (
                    "tuple",
                    _lit("arg"),
                    ("item", params, i),
                ),
            ),
            (
                "call",
                "arg_exprs",
                params,
                ("add", i, _lit(1)),
            ),
        ),
        _lit(()),
    )


def _swapped_function(
    target: str,
    chunk: tuple,
) -> tuple:
    """The value that replaces target."""

    params = _item(
        ("code", target),
        0,
    )

    return (
        "function",
        params,
        (
            "quote",
            (
                "call",
                "vm",
                (
                    "lit",
                    ("unquote", chunk),
                ),
                (
                    "lit",
                    ("unquote", params),
                ),
                (
                    "unquote",
                    (
                        "concat",
                        _lit(("tuple",)),
                        (
                            "call",
                            "arg_exprs",
                            params,
                            _lit(0),
                        ),
                    ),
                ),
                (
                    "lit",
                    (
                        "unquote",
                        ("linksof", target),
                    ),
                ),
            ),
        ),
    )


def _compiled(target: str) -> tuple:
    """Compile the retained source of target with the active lower."""

    return (
        "call",
        "lower",
        _item(
            ("code", source_name(target).value),
            1,
        ),
    )


def _swap_body(target: str) -> tuple:
    """Replace one function; the value is the chunk installed."""

    return (
        "let",
        "chunk",
        _compiled(target),
        (
            "seq",
            (
                "activate",
                target,
                _swapped_function(
                    target,
                    _arg("chunk"),
                ),
            ),
            _arg("chunk"),
        ),
    )


def _generation_function(record: tuple) -> tuple:
    """Build a no-argument function returning record as literal data."""

    return (
        "function",
        _lit(()),
        (
            "quote",
            (
                "lit",
                ("unquote", record),
            ),
        ),
    )


def _swap_all_body() -> tuple:
    """Replace the compiler and record one rebuild generation."""

    chunk_names = {
        target: f"{target}_chunk"
        for target in SWAPPED
    }
    generation_number = "generation_number"
    record = (
        "tuple",
        _arg(generation_number),
        (
            "tuple",
            *(
                (
                    "tuple",
                    _lit(target),
                    _arg(chunk_names[target]),
                )
                for target in SWAPPED
            ),
        ),
    )
    pairs: list[tuple] = []

    for target in SWAPPED:
        pairs += [
            target,
            _swapped_function(
                target,
                _arg(chunk_names[target]),
            ),
        ]

    pairs += [
        GENERATION.value,
        _generation_function(record),
    ]

    body: tuple = (
        "let",
        generation_number,
        (
            "add",
            _item(("call", GENERATION.value), 0),
            _lit(1),
        ),
        (
            "seq",
            ("activate", *pairs),
            _lit(True),
        ),
    )

    for target in reversed(SWAPPED):
        body = (
            "let",
            chunk_names[target],
            _compiled(target),
            body,
        )

    return body


def _source_links(
    compiler: dict[EntityID, Any],
    target: str,
) -> dict[str, EntityID]:
    """Read a compiler function's original links from the compiler."""

    table = compiler[EntityID(f"{target}.links")]

    return {
        role: endpoint
        for role, endpoint in table.roles.items()
        if role not in (FUNCTION_ROLE, "vm")
    }


def bootstrap_entities() -> dict[EntityID, Any]:
    """The compiler, retained source, interpreter, and rebuild program."""

    from .self_hosting import compiler_entities
    from .vm import VM, vm_entities

    compiler = compiler_entities({
        "vm": VM,
    })
    entities: dict[EntityID, Any] = {
        **compiler,
        **vm_entities(),
        ARG_EXPRS: Function(
            ("params", "i"),
            _arg_exprs_body(),
        ),
        EntityID("arg_exprs.links"): links(
            ARG_EXPRS,
            arg_exprs=ARG_EXPRS,
        ),
        GENERATION: Function(
            (),
            _lit((0, ())),
        ),
    }

    for target in SWAPPED:
        source = source_name(target)
        entities[source] = compiler[EntityID(target)]
        entities[EntityID(f"{source.value}.links")] = links(
            source,
            **_source_links(compiler, target),
        )

    for target in SWAPPED:
        entity = _swap_name(target)
        source = source_name(target)
        entities[entity] = Function(
            (),
            _swap_body(target),
        )
        entities[
            EntityID(
                f"swap_{target}.links"
            )
        ] = links(
            entity,
            **{
                target: EntityID(target),
                source.value: source,
                "lower": EntityID("lower"),
                "arg_exprs": ARG_EXPRS,
            },
        )

    entities[SWAP_ALL] = Function(
        (),
        _swap_all_body(),
    )
    entities[
        EntityID("swap_all.links")
    ] = links(
        SWAP_ALL,
        **{
            target: EntityID(target)
            for target in SWAPPED
        },
        **{
            source_name(target).value: source_name(target)
            for target in SWAPPED
        },
        generation=GENERATION,
        arg_exprs=ARG_EXPRS,
    )

    return entities


def _bootstrap() -> Example:
    end = ("END",)
    one = (
        ("LIT", 1),
        end,
    )
    x = (
        ("ARG", "x"),
        end,
    )
    add = (
        ("EVAL", x),
        ("INT", "add"),
        ("EVAL", one),
        ("INT", "add"),
        ("ADD",),
        end,
    )
    branch = (
        (
            "EVAL",
            (
                ("EVAL", x),
                ("INT", "lt"),
                ("EVAL", one),
                ("INT", "lt"),
                ("LT",),
                end,
            ),
        ),
        (
            "BRANCH",
            one,
            x,
        ),
        end,
    )
    expression = (
        "if",
        (
            "lt",
            ("arg", "x"),
            ("lit", 1),
        ),
        ("lit", 1),
        ("arg", "x"),
    )

    return Example(
        name="bootstrap",
        tags=frozenset({
            "self-modification",
            "recursion",
            "data",
        }),
        program=program(
            bootstrap_entities()
        ),
        scenarios=(
            (
                Step(
                    LOWER,
                    (
                        (
                            "add",
                            ("arg", "x"),
                            ("lit", 1),
                        ),
                    ),
                    add,
                ),
                Step(
                    SWAP_ALL,
                    (),
                    Raises(
                        ActivationRejected
                    ),
                ),
                Step(
                    SWAP_ALL,
                    (),
                    True,
                    may_activate=True,
                ),
                Step(
                    LOWER,
                    (
                        (
                            "add",
                            ("arg", "x"),
                            ("lit", 1),
                        ),
                    ),
                    add,
                ),
                Step(
                    LOWER,
                    (expression,),
                    branch,
                ),
                Step(
                    UPPER,
                    ("mul",),
                    "MUL",
                ),
                Step(
                    UPPER,
                    ("frobnicate",),
                    None,
                ),
            ),
        ),
        description=(
            "The compiler of self_hosting.py swaps each of its functions "
            "for one that hands its own chunk to the interpreter written in "
            "SHEAR, then compiles again, on that bytecode, with the same "
            "results (vm_in_shear.md section 5)."
        ),
    )
