"""Examples of the compiler written in SHEAR, and a program that rewrites
itself (docs/self_hosting.md, roadmap task 8).

The compiler itself is ``compiler_source.py``; its public names are
re-exported here. ``tests/test_self_hosting.py`` checks it against
``shear.bytecode`` on the whole language it covers, and on the compiler
itself.

The examples here run the compiler on a few expressions, and a program that
reads its own function with ``code``, swaps in a version that counts its
calls, and compiles what it installed.
"""

from __future__ import annotations

from typing import Any

from .. import ActivationRejected, CellDeclaration, EntityID, IntRange
from ..lang import Function, LanguageError, links
from . import Example, Raises, Step
from ._support import program

from .compiler_source import (  # noqa: F401  (re-exported)
    COMPILE_NODE,
    EVALS,
    LOWER,
    LOWERED,
    SELF_LOWER,
    SEQ_CODE,
    UPPER,
    _arg,
    _item,
    _lit,
    compiler_entities,
)


def _compiler() -> Example:
    def step(
        expression: tuple,
        expect: Any,
    ) -> Step:
        return Step(
            LOWER,
            (expression,),
            expect,
        )

    end = ("END",)
    x = (
        ("ARG", "x"),
        end,
    )
    one = (
        ("LIT", 1),
        end,
    )

    return Example(
        name="compiler",
        tags=frozenset({
            "data",
            "recursion",
        }),
        program=program(
            compiler_entities()
        ),
        scenarios=(
            (
                step(
                    ("lit", 7),
                    (
                        ("LIT", 7),
                        end,
                    ),
                ),
                step(
                    ("arg", "x"),
                    x,
                ),
                step(
                    (
                        "add",
                        ("arg", "x"),
                        ("lit", 1),
                    ),
                    (
                        (
                            "EVAL",
                            x,
                        ),
                        (
                            "INT",
                            "add",
                        ),
                        (
                            "EVAL",
                            one,
                        ),
                        (
                            "INT",
                            "add",
                        ),
                        ("ADD",),
                        end,
                    ),
                ),
                step(
                    (
                        "if",
                        (
                            "lt",
                            ("arg", "x"),
                            ("lit", 1),
                        ),
                        ("lit", 1),
                        ("arg", "x"),
                    ),
                    (
                        (
                            "EVAL",
                            (
                                (
                                    "EVAL",
                                    x,
                                ),
                                (
                                    "INT",
                                    "lt",
                                ),
                                (
                                    "EVAL",
                                    one,
                                ),
                                (
                                    "INT",
                                    "lt",
                                ),
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
                    ),
                ),
                step(
                    ("seq",),
                    (
                        (
                            "RAISE",
                            "seq needs at least one expression",
                        ),
                        end,
                    ),
                ),
                step(
                    (
                        "seq",
                        ("lit", 1),
                        ("arg", "x"),
                    ),
                    (
                        (
                            "EVAL",
                            one,
                        ),
                        ("POP",),
                        (
                            "GOTO",
                            x,
                        ),
                        end,
                    ),
                ),
                step(
                    (
                        "call",
                        "f",
                        ("lit", 1),
                        ("arg", "x"),
                    ),
                    (
                        (
                            "EVAL",
                            one,
                        ),
                        (
                            "EVAL",
                            x,
                        ),
                        (
                            "CALL",
                            "f",
                            2,
                        ),
                        end,
                    ),
                ),
                step(
                    (
                        "let",
                        "a",
                        ("lit", 1),
                        ("arg", "a"),
                    ),
                    (
                        (
                            "LETCHECK",
                            "a",
                        ),
                        (
                            "EVAL",
                            one,
                        ),
                        (
                            "LETBIND",
                            "a",
                            (
                                (
                                    "ARG",
                                    "a",
                                ),
                                end,
                            ),
                        ),
                        end,
                    ),
                ),
                step(
                    (
                        "label",
                        "k",
                        ("lit", 1),
                    ),
                    one,
                ),
                step(
                    (
                        "closure",
                        ("x",),
                        ("n",),
                        (
                            "add",
                            ("arg", "n"),
                            ("arg", "x"),
                        ),
                    ),
                    (
                        (
                            "CLOSURE",
                            (
                                (
                                    "EVAL",
                                    (
                                        (
                                            "ARG",
                                            "n",
                                        ),
                                        end,
                                    ),
                                ),
                                (
                                    "INT",
                                    "add",
                                ),
                                (
                                    "EVAL",
                                    (
                                        (
                                            "ARG",
                                            "x",
                                        ),
                                        end,
                                    ),
                                ),
                                (
                                    "INT",
                                    "add",
                                ),
                                ("ADD",),
                                end,
                            ),
                            ("x",),
                            ("n",),
                        ),
                        end,
                    ),
                ),
                step(
                    (
                        "quote",
                        ("lit", 1),
                    ),
                    (
                        (
                            "RAISE",
                            "unknown operation",
                        ),
                        end,
                    ),
                ),
            ),
        ),
        description=(
            "lower(e), the lowering pass of bytecode.md written in SHEAR: "
            "an expression in input form in, its chunk out with children "
            "in place of references (self_hosting.md section 3)."
        ),
    )


def _instrument() -> Example:
    work = EntityID("work")
    hits = EntityID("hits")
    instrument = EntityID("instrument")
    counted = (
        "write",
        "hits",
        (
            "add",
            ("read", "hits"),
            ("lit", 1),
        ),
    )
    entities = {
        hits: CellDeclaration(
            IntRange(0, 100),
            0,
        ),
        work: Function(
            ("x",),
            (
                "add",
                ("arg", "x"),
                ("lit", 1),
            ),
        ),
        EntityID("work.links"): links(
            work,
            hits=hits,
        ),
        instrument: Function(
            (),
            (
                "seq",
                (
                    "activate",
                    "work",
                    (
                        "function",
                        _item(
                            ("code", "work"),
                            0,
                        ),
                        (
                            "quote",
                            (
                                "seq",
                                counted,
                                (
                                    "unquote",
                                    _item(
                                        ("code", "work"),
                                        1,
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
                (
                    "call",
                    "lower",
                    _item(
                        ("code", "work"),
                        1,
                    ),
                ),
            ),
        ),
        EntityID("instrument.links"): links(
            instrument,
            work=work,
            lower=LOWER,
        ),
        **compiler_entities(),
    }

    end = ("END",)

    add = (
        (
            "EVAL",
            (
                (
                    "ARG",
                    "x",
                ),
                end,
            ),
        ),
        (
            "INT",
            "add",
        ),
        (
            "EVAL",
            (
                (
                    "LIT",
                    1,
                ),
                end,
            ),
        ),
        (
            "INT",
            "add",
        ),
        ("ADD",),
        end,
    )

    count = (
        (
            "EVAL",
            (
                (
                    "READ",
                    "hits",
                ),
                end,
            ),
        ),
        (
            "INT",
            "add",
        ),
        (
            "EVAL",
            (
                (
                    "LIT",
                    1,
                ),
                end,
            ),
        ),
        (
            "INT",
            "add",
        ),
        ("ADD",),
        end,
    )

    installed = (
        (
            "EVAL",
            (
                (
                    (
                        "EVAL",
                        count,
                    ),
                    (
                        "WRITE",
                        "hits",
                    ),
                    end,
                )
            ),
        ),
        ("POP",),
        (
            "GOTO",
            add,
        ),
        end,
    )

    return Example(
        name="instrument",
        tags=frozenset({
            "self-modification",
            "side effects",
        }),
        program=program(entities),
        scenarios=(
            (
                Step(
                    work,
                    (5,),
                    6,
                    cells={
                        hits: 0,
                    },
                ),
                Step(
                    instrument,
                    (),
                    Raises(
                        ActivationRejected
                    ),
                ),
                Step(
                    instrument,
                    (),
                    installed,
                    may_activate=True,
                ),
                Step(
                    work,
                    (5,),
                    6,
                    cells={
                        hits: 1,
                    },
                ),
                Step(
                    work,
                    (7,),
                    8,
                    cells={
                        hits: 2,
                    },
                ),
            ),
        ),
        description=(
            "A program reads its own function with `code`, swaps in a version "
            "that counts its calls, and compiles the installed code with its "
            "own compiler, which sees the new version (self_hosting.md "
            "section 4)."
        ),
    )


EXAMPLES: tuple[Example, ...] = (
    _compiler(),
    _instrument(),
            )
