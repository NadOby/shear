"""A bytecode interpreter written in SHEAR (docs/vm_in_shear.md,
roadmap task 10).

``vm(chunk, params, args, links)`` runs a chunk as ``lower`` in
``self_hosting.py`` emits it: a tuple of instructions in which ``EVAL``,
``GOTO``, ``BRANCH``, ``LETBIND`` and ``CLOSURE`` hold the chunk of their
child. It runs the instructions of a pure function: arithmetic, comparison,
tuples, ``let``, ``if``, ``seq``, ``call``, ``ref``, ``apply`` and lexical
closures.

The interpreter represents callable values internally as capability-tagged
tuples. References are ``(token, "ref", entity)``. Closures are
``(token, "closure", body, params, captures, links)`` where ``captures`` is
the captured environment. ``token`` is a real SHEAR closure created by
``vm`` and never exposed to interpreted code, so an ordinary tuple built by
that code cannot forge an internal callable. This representation need not be
the host Python Closure record.

``links`` is the interpreted function's link table as ``linksof`` returns it.
A direct ``CALL`` resolves there and enters the callee with ``applyv``.

The machine is ``run(chunk, pc, stack, env, links, token)``. The operand stack
is a tuple, the environment a tuple of ``(name, value)`` pairs, and the
program counter an index. ``run`` calls itself in tail position for every
instruction, ``EVAL`` calls it for the child, and ``GOTO``, ``BRANCH`` and
``LETBIND`` tail call it, so a tail call of the interpreted function is a tail
call of the machine.

It has no way to raise an error of its own, so a check is made by doing the
operation: ``INT`` adds zero, ``TUPLE`` takes the length, and ``trap`` indexes
an empty tuple. The error is a ``LanguageError`` all the same.
"""

from __future__ import annotations

from typing import Any

from .. import ActivationRejected, EntityID
from ..instructions import INSTRUCTIONS
from ..lang import FUNCTION_ROLE, Function, links
from . import Example, Raises, Step
from ._support import program
from .self_hosting import LOWER, UPPER, _arg, _item, _lit

RUN = EntityID("vm_run")
LOOKUP = EntityID("vm_lookup")
HAS = EntityID("vm_has")
FIND = EntityID("vm_find")
BIND = EntityID("vm_bind")
CAPTURE = EntityID("vm_capture")
APPLY_CALLABLE = EntityID("vm_apply")
TRAP = EntityID("vm_trap")
VM = EntityID("vm")

_CHUNK, _PC, _STACK, _ENV, _LINKS, _TOKEN = (
    _arg("chunk"),
    _arg("pc"),
    _arg("stack"),
    _arg("env"),
    _arg("links"),
    _arg("token"),
)
_INS = _arg("ins")
_N = ("len", _STACK)


def _sub(left: tuple, right: Any) -> tuple:
    return (
        "sub",
        left,
        _lit(right) if isinstance(right, int) else right,
    )


def _top(depth: int = 1) -> tuple:
    """The value ``depth`` from the top of the stack (1 is the top)."""

    return ("item", _STACK, _sub(_N, depth))


def _drop(count: Any) -> tuple:
    """The stack without its top ``count``."""

    return ("slice", _STACK, _lit(0), _sub(_N, count))


def _push(base: tuple, value: tuple) -> tuple:
    return ("concat", base, ("tuple", value))


def _next(stack: tuple) -> tuple:
    return (
        "call",
        "vm_run",
        _CHUNK,
        ("add", _PC, _lit(1)),
        stack,
        _ENV,
        _LINKS,
        _TOKEN,
    )


def _enter(
    chunk: tuple,
    env: tuple = _ENV,
    links_: tuple = _LINKS,
) -> tuple:
    """Run a child chunk from its start with an empty stack."""

    return (
        "call",
        "vm_run",
        chunk,
        _lit(0),
        _lit(()),
        env,
        links_,
        _TOKEN,
    )


def _instruction_operand(index: int) -> tuple:
    return _item(_INS, index)


def _binary(operation: str) -> tuple:
    return _next(
        _push(
            _drop(2),
            (
                operation,
                _top(2),
                _top(1),
            ),
        )
    )


def _callable_tagged(
    value: tuple,
    token: tuple = _TOKEN,
) -> tuple:
    """Check the VM's capability-tagged callable representation."""

    length = ("len", value)
    marker = ("item", value, _lit(0))
    tag = ("item", value, _lit(1))
    trap = ("call", "vm_trap")

    return (
        "if",
        ("lt", length, _lit(2)),
        trap,
        (
            "if",
            ("eq", marker, token),
            (
                "if",
                ("eq", tag, _lit("ref")),
                (
                    "if",
                    ("eq", length, _lit(3)),
                    _lit(True),
                    trap,
                ),
                (
                    "if",
                    ("eq", tag, _lit("closure")),
                    (
                        "if",
                        ("eq", length, _lit(6)),
                        _lit(True),
                        trap,
                    ),
                    trap,
                ),
            ),
            trap,
        ),
    )


def _validate_names(names: tuple) -> tuple:
    """Use the language's Function constructor to validate a name tuple."""

    return (
        "function",
        names,
        _lit(("lit", None)),
    )


def _cases() -> list[tuple[str, tuple]]:
    k = _instruction_operand
    def operand(opcode: str, field: str, which: int = 0) -> tuple:
        """The operand the instruction table lists under ``field``."""

        return k(getattr(INSTRUCTIONS[opcode], field)[which] + 1)

    def count(opcode: str) -> tuple:
        """The operand that gives the instruction's item count."""

        return k(INSTRUCTIONS[opcode].counted[0] + 1)

    def direct_call(
        function: tuple,
        arguments: tuple,
    ) -> tuple:
        """Call a real linked SHEAR function.

        CALL is the final operation of its chunk, so this remains a tail
        call of the interpreted program.
        """

        return ("applyv", function, arguments)

    def indirect_call(
        function: tuple,
        arguments: tuple,
    ) -> tuple:
        """Call a capability-tagged VM reference or closure."""

        return (
            "call",
            "vm_apply",
            function,
            arguments,
            _TOKEN,
        )

    return [
        (
            "LIT",
            _next(
                _push(
                    _STACK,
                    k(1),
                )
            ),
        ),
        (
            "ARG",
            _next(
                _push(
                    _STACK,
                    (
                        "call",
                        "vm_lookup",
                        _ENV,
                        operand("ARG", "names"),
                        _lit(0),
                    ),
                )
            ),
        ),
        (
            "EVAL",
            _next(
                _push(
                    _STACK,
                    _enter(operand("EVAL", "children")),
                )
            ),
        ),
        ("END", _top()),
        ("GOTO", _enter(operand("GOTO", "children"))),
        (
            "BRANCH",
            (
                "if",
                _top(),
                _enter(operand("BRANCH", "children", 0)),
                _enter(operand("BRANCH", "children", 1)),
            ),
        ),
        ("POP", _next(_drop(1))),
        (
            "INT",
            (
                "seq",
                ("add", _top(), _lit(0)),
                _next(_STACK),
            ),
        ),
        (
            "TUPLE",
            (
                "seq",
                ("len", _top()),
                _next(_STACK),
            ),
        ),
        ("ADD", _binary("add")),
        ("SUB", _binary("sub")),
        ("MUL", _binary("mul")),
        ("LT", _binary("lt")),
        ("EQ", _binary("eq")),
        (
            "LEN",
            _next(
                _push(
                    _drop(1),
                    ("len", _top()),
                )
            ),
        ),
        (
            "ITEM",
            _next(
                _push(
                    _drop(2),
                    (
                        "item",
                        _top(2),
                        _top(1),
                    ),
                )
            ),
        ),
        (
            "SLICE",
            _next(
                _push(
                    _drop(3),
                    (
                        "slice",
                        _top(3),
                        _top(2),
                        _top(1),
                    ),
                )
            ),
        ),
        (
            "CONCAT",
            _next(
                _push(
                    _drop(2),
                    (
                        "concat",
                        _top(2),
                        _top(1),
                    ),
                )
            ),
        ),
        (
            "MKTUPLE",
            _next(
                _push(
                    _drop(count("MKTUPLE")),
                    (
                        "slice",
                        _STACK,
                        _sub(_N, count("MKTUPLE")),
                        _N,
                    ),
                )
            ),
        ),
        (
            "CALL",
            direct_call(
                (
                    "call",
                    "vm_find",
                    _LINKS,
                    operand("CALL", "linked"),
                    _lit(0),
                ),
                (
                    "slice",
                    _STACK,
                    _sub(_N, count("CALL")),
                    _N,
                ),
            ),
        ),
        (
            "REFCHECK",
            (
                "seq",
                _callable_tagged(_top()),
                _next(_STACK),
            ),
        ),
        (
            "APPLY",
            indirect_call(
                (
                    "item",
                    _STACK,
                    _sub(
                        _N,
                        ("add", count("APPLY"), _lit(1)),
                    ),
                ),
                (
                    "slice",
                    _STACK,
                    _sub(_N, count("APPLY")),
                    _N,
                ),
            ),
        ),
        (
            "APPLYV",
            indirect_call(
                _top(2),
                _top(1),
            ),
        ),
        (
            "REF",
            _next(
                _push(
                    _STACK,
                    (
                        "tuple",
                        _TOKEN,
                        _lit("ref"),
                        (
                            "call",
                            "vm_find",
                            _LINKS,
                            operand("REF", "linked"),
                            _lit(0),
                        ),
                    ),
                )
            ),
        ),
        (
            "CLOSURE",
            (
                "seq",
                _validate_names(k(2)),
                _validate_names(k(3)),
                _validate_names(
                    ("concat", k(2), k(3))
                ),
                _next(
                    _push(
                        _STACK,
                        (
                            "tuple",
                            _TOKEN,
                            _lit("closure"),
                            operand("CLOSURE", "children"),
                            k(2),
                            (
                                "call",
                                "vm_capture",
                                k(3),
                                _ENV,
                                _lit(0),
                                _lit(()),
                            ),
                            _LINKS,
                        ),
                    )
                ),
            ),
        ),
        (
            "LETCHECK",
            (
                "if",
                (
                    "call",
                    "vm_has",
                    _ENV,
                    operand("LETCHECK", "names"),
                    _lit(0),
                ),
                ("call", "vm_trap"),
                _next(_STACK),
            ),
        ),
        (
            "LETBIND",
            _enter(
                operand("LETBIND", "children"),
                (
                    "concat",
                    _ENV,
                    (
                        "tuple",
                        (
                            "tuple",
                            operand("LETBIND", "names"),
                            _top(),
                        ),
                    ),
                ),
            ),
        ),
    ]


_ORDER = (
    "END",
    "EVAL",
    "LIT",
    "MKTUPLE",
    "TUPLE",
    "ARG",
    "INT",
    "ITEM",
    "CALL",
    "CONCAT",
    "EQ",
    "BRANCH",
    "GOTO",
    "POP",
    "LEN",
    "ADD",
    "SUB",
    "MUL",
    "LT",
    "SLICE",
    "LETCHECK",
    "LETBIND",
    "REF",
    "CLOSURE",
    "APPLY",
    "APPLYV",
    "REFCHECK",
)


def _run_body() -> tuple:
    chain: tuple = ("call", "vm_trap")
    cases = dict(_cases())

    for op in reversed(_ORDER):
        body = cases[op]
        chain = (
            "if",
            ("eq", _arg("op"), _lit(op)),
            body,
            chain,
        )

    return (
        "let",
        "ins",
        ("item", _CHUNK, _PC),
        (
            "let",
            "op",
            _item(_INS, 0),
            chain,
        ),
    )


def _lookup_body() -> tuple:
    env = _arg("env")
    name = _arg("name")
    i = _arg("i")
    pair = ("item", env, i)

    return (
        "if",
        ("lt", i, ("len", env)),
        (
            "if",
            (
                "eq",
                ("item", pair, _lit(0)),
                name,
            ),
            ("item", pair, _lit(1)),
            (
                "call",
                "vm_lookup",
                env,
                name,
                ("add", i, _lit(1)),
            ),
        ),
        ("call", "vm_trap"),
    )


def _has_body() -> tuple:
    env = _arg("env")
    name = _arg("name")
    i = _arg("i")

    return (
        "if",
        ("lt", i, ("len", env)),
        (
            "if",
            (
                "eq",
                (
                    "item",
                    ("item", env, i),
                    _lit(0),
                ),
                name,
            ),
            _lit(True),
            (
                "call",
                "vm_has",
                env,
                name,
                ("add", i, _lit(1)),
            ),
        ),
        _lit(False),
    )


def _find_body() -> tuple:
    table = _arg("table")
    name = _arg("name")
    i = _arg("i")
    pair = ("item", table, i)

    return (
        "if",
        ("lt", i, ("len", table)),
        (
            "if",
            (
                "eq",
                ("item", pair, _lit(0)),
                name,
            ),
            ("item", pair, _lit(1)),
            (
                "call",
                "vm_find",
                table,
                name,
                ("add", i, _lit(1)),
            ),
        ),
        ("call", "vm_trap"),
    )


def _bind_body() -> tuple:
    params = _arg("params")
    args = _arg("args")
    i = _arg("i")
    env = _arg("env")

    return (
        "if",
        ("lt", i, ("len", params)),
        (
            "call",
            "vm_bind",
            params,
            args,
            ("add", i, _lit(1)),
            (
                "concat",
                env,
                (
                    "tuple",
                    (
                        "tuple",
                        ("item", params, i),
                        ("item", args, i),
                    ),
                ),
            ),
        ),
        env,
    )


def _capture_body() -> tuple:
    names = _arg("names")
    env = _arg("env")
    i = _arg("i")
    acc = _arg("acc")
    name = ("item", names, i)

    return (
        "if",
        ("lt", i, ("len", names)),
        (
            "call",
            "vm_capture",
            names,
            env,
            ("add", i, _lit(1)),
            (
                "concat",
                acc,
                (
                    "tuple",
                    (
                        "tuple",
                        name,
                        (
                            "call",
                            "vm_lookup",
                            env,
                            name,
                            _lit(0),
                        ),
                    ),
                ),
            ),
        ),
        acc,
    )


def _apply_body() -> tuple:
    function = _arg("function")
    args = _arg("args")
    token = _arg("token")
    tag = ("item", function, _lit(1))

    closure_body = ("item", function, _lit(2))
    params = ("item", function, _lit(3))
    captures = ("item", function, _lit(4))
    closure_links = ("item", function, _lit(5))

    dispatch = (
        "if",
        ("eq", tag, _lit("ref")),
        (
            "applyv",
            ("item", function, _lit(2)),
            args,
        ),
        (
            "if",
            ("eq", tag, _lit("closure")),
            (
                "if",
                ("eq", ("len", params), ("len", args)),
                (
                    "call",
                    "vm_run",
                    closure_body,
                    _lit(0),
                    _lit(()),
                    (
                        "call",
                        "vm_bind",
                        params,
                        args,
                        _lit(0),
                        captures,
                    ),
                    closure_links,
                    token,
                ),
                ("call", "vm_trap"),
            ),
            ("call", "vm_trap"),
        ),
    )

    return (
        "seq",
        _callable_tagged(function, token),
        dispatch,
    )


def vm_entities() -> dict[EntityID, Any]:
    """The interpreter's functions and their links."""

    return {
        RUN: Function(
            (
                "chunk",
                "pc",
                "stack",
                "env",
                "links",
                "token",
            ),
            _run_body(),
        ),
        EntityID("vm_run.links"): links(
            RUN,
            vm_run=RUN,
            vm_lookup=LOOKUP,
            vm_has=HAS,
            vm_find=FIND,
            vm_capture=CAPTURE,
            vm_apply=APPLY_CALLABLE,
            vm_trap=TRAP,
        ),
        LOOKUP: Function(
            ("env", "name", "i"),
            _lookup_body(),
        ),
        EntityID("vm_lookup.links"): links(
            LOOKUP,
            vm_lookup=LOOKUP,
            vm_trap=TRAP,
        ),
        HAS: Function(
            ("env", "name", "i"),
            _has_body(),
        ),
        EntityID("vm_has.links"): links(
            HAS,
            vm_has=HAS,
        ),
        FIND: Function(
            ("table", "name", "i"),
            _find_body(),
        ),
        EntityID("vm_find.links"): links(
            FIND,
            vm_find=FIND,
            vm_trap=TRAP,
        ),
        BIND: Function(
            ("params", "args", "i", "env"),
            _bind_body(),
        ),
        EntityID("vm_bind.links"): links(
            BIND,
            vm_bind=BIND,
        ),
        CAPTURE: Function(
            ("names", "env", "i", "acc"),
            _capture_body(),
        ),
        EntityID("vm_capture.links"): links(
            CAPTURE,
            vm_capture=CAPTURE,
            vm_lookup=LOOKUP,
        ),
        APPLY_CALLABLE: Function(
            ("function", "args", "token"),
            _apply_body(),
        ),
        EntityID("vm_apply.links"): links(
            APPLY_CALLABLE,
            vm_run=RUN,
            vm_bind=BIND,
            vm_trap=TRAP,
        ),
        TRAP: Function(
            (),
            ("item", ("tuple",), _lit(0)),
        ),
        VM: Function(
            ("chunk", "params", "args", "links"),
            (
                "let",
                "token",
                (
                    "closure",
                    (),
                    (),
                    ("lit", None),
                ),
                (
                    "call",
                    "vm_run",
                    _arg("chunk"),
                    _lit(0),
                    _lit(()),
                    (
                        "call",
                        "vm_bind",
                        _arg("params"),
                        _arg("args"),
                        _lit(0),
                        _lit(()),
                    ),
                    _arg("links"),
                    _arg("token"),
                ),
            ),
        ),
        EntityID("vm.links"): links(
            VM,
            vm_run=RUN,
            vm_bind=BIND,
        ),
    }


# ---------------------------------------------------------------------------
# A program that runs its own compiler on its own bytecode
# ---------------------------------------------------------------------------

ARG_EXPRS = EntityID("arg_exprs")
SWAP_ALL = EntityID("swap_all")
GENERATION = EntityID("generation")
# The functions of the expanded lowering pass, each replaced by a wrapper that
# runs its own compiled chunk on the interpreter. compile_node and self_lower
# are not part of that pass.
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
    """The links of target's retained source: the compiler's own links of
    target, without the interpreter's, read from the compiler so that the
    twin and its original cannot disagree."""

    table = compiler[EntityID(f"{target}.links")]

    return {
        role: endpoint
        for role, endpoint in table.roles.items()
        if role not in (FUNCTION_ROLE, "vm")
    }


def bootstrap_entities() -> dict[EntityID, Any]:
    """The compiler, retained source, interpreter, and rebuild program."""

    from .self_hosting import compiler_entities

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


EXAMPLES: tuple[Example, ...] = (
    _bootstrap(),
    )
