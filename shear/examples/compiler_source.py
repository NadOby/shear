"""The compiler of bytecode.md written in SHEAR (docs/self_hosting.md,
roadmap tasks 8 and 30).

One lowering core, ``lower_op(e, mode)``, makes every lowering decision: which
instructions an operation produces, their operands and their order. Two thin
entry points differ only in how they refer to children and link targets:

* ``lower(e)`` (expanded mode) takes an expression in input form, as
  ``("code", f)`` returns it, and gives the chunk of that expression with every
  ``EVAL``, ``GOTO``, ``BRANCH``, ``CATCH``, ``LETBIND`` and ``CLOSURE``
  holding the chunk of its child, and every call, read, write, ``ref``,
  ``code`` and ``linksof`` naming its link.
* ``compile_node(d)`` (node mode) takes a descriptor ``(e, identity)`` that the
  host builds from one graph-form node: ``e`` is the node's operation and
  operands in input-form order, with children as ``EntityID`` and link names
  replaced by their resolved targets. It gives the node's chunk exactly as
  ``shear.bytecode.lower`` does, children and targets by ``EntityID``.

Expanded mode covers every operation but ``quote``, ``unquote``, ``function``,
``activate`` and ``trial``, which lower to the ``RAISE`` of an unknown
operation. Node mode lowers those five too (``NODE_LOWERED``; the task-31
hosted route, docs/live_evolution.md section 2.3) and an ``invalid`` node to
the ``RAISE`` of its problem. Their operands are the descriptor's:
``quote`` takes its template, then its holes; ``function`` its parameters and
body; ``activate`` its ``(link, problem)`` entries, its resolved targets and
its values as a tuple; ``trial`` its entries, targets, call problem and call
target, then its arguments and values as two tuples.
``tests/test_self_hosting.py`` and ``tests/test_hosted_pipeline.py`` check
both entry points against ``shear.bytecode``.

``self_hosting.py`` re-exports this module's public names.
"""

from __future__ import annotations

from typing import Any

from .. import EntityID
from ..lang import Function, links

LOWER = EntityID("lower")
UPPER = EntityID("upper")
EVALS = EntityID("evals")
SEQ_CODE = EntityID("seq_code")
LOWER_OP = EntityID("lower_op")
CHILD = EntityID("child")
NAMED_TAIL = EntityID("named_tail")
COMPILE_NODE = EntityID("compile_node")
SELF_LOWER = EntityID("self_lower")

# The entry points; the host selects node mode by calling compile_node.
EXPANDED = 0
NODE = 1

# The operations the compiler lowers.
LOWERED = frozenset({
    "lit",
    "arg",
    "add",
    "sub",
    "mul",
    "lt",
    "eq",
    "if",
    "seq",
    "call",
    "tuple",
    "inspect",
    "record",
    "len",
    "item",
    "slice",
    "concat",
    "let",
    "ref",
    "apply",
    "read",
    "write",
    "code",
    "label",
    "applyv",
    "linksof",
    "closure",
    "catch",
    "raise",
})

# What only node mode lowers. Expanded mode gives these the RAISE of an
# unknown operation, as it always has.
NODE_ONLY = frozenset({
    "quote",
    "unquote",
    "function",
    "activate",
    "trial",
})

# The operations node mode lowers: its input-form operations (``label`` is
# input-form only) and the five above. The host's ``invalid`` node is lowered
# as well; ``hosted_bootstrap.descriptors`` adds it.
NODE_LOWERED = (LOWERED - {"label"}) | NODE_ONLY


def _lit(value: Any) -> tuple:
    return ("lit", value)


def _arg(name: str) -> tuple:
    return ("arg", name)


def _item(tuple_: tuple, index: int) -> tuple:
    return ("item", tuple_, _lit(index))


def _op(name: str, *operands: tuple) -> tuple:
    """An instruction: its opcode and operands, built from expressions."""

    return ("tuple", _lit(name), *operands)


_END_CHUNK = ("tuple", _lit(("END",)))


def _chunk(*instructions: tuple) -> tuple:
    """A finished chunk: the instructions and END."""

    return ("concat", ("tuple", *instructions), _END_CHUNK)


def _is(name: str) -> tuple:
    return ("eq", _arg("op"), _lit(name))


def _length_minus(amount: int) -> tuple:
    return ("sub", ("len", _arg("e")), _lit(amount))


def _sub_expr(index: int) -> tuple:
    return _item(_arg("e"), index)


def _ref(expression: tuple) -> tuple:
    """How a chunk refers to a child: its chunk, or the child itself."""

    return ("call", "child", expression, _arg("mode"))


def _child(index: int) -> tuple:
    """The instruction that evaluates operand ``index`` of ``e``."""

    return _op("EVAL", _ref(_sub_expr(index)))


def _evals_from(index: int, trailer: tuple) -> tuple:
    """The ``EVAL`` instructions of every operand from ``index`` on, then
    ``trailer`` (one instruction), then END."""

    return (
        "concat",
        (
            "concat",
            (
                "call",
                "evals",
                _arg("e"),
                _lit(index),
                _lit(()),
                _arg("mode"),
            ),
            ("tuple", trailer),
        ),
        _END_CHUNK,
    )


def _evals_of(children: tuple) -> tuple:
    """The ``EVAL`` instructions of every child in the tuple ``children``."""

    return (
        "call",
        "evals",
        children,
        _lit(0),
        _lit(()),
        _arg("mode"),
    )


def _evals_chunk(groups: list[tuple], trailer: tuple) -> tuple:
    """The ``EVAL`` instructions of each tuple of children in ``groups``, then
    ``trailer`` (one instruction), then END."""

    code = _evals_of(groups[0])

    for group in groups[1:]:
        code = ("concat", code, _evals_of(group))

    return ("concat", ("concat", code, ("tuple", trailer)), _END_CHUNK)


def _node_only(chunk: tuple) -> tuple:
    """``chunk`` in node mode; in expanded mode the ``RAISE`` of an unknown
    operation."""

    return (
        "if",
        ("eq", _arg("mode"), _lit(NODE)),
        chunk,
        _chunk(_op("RAISE", _lit("unknown operation"))),
    )


def _named(opcode: str) -> tuple:
    """An instruction naming a link target: the target itself in expanded
    mode (a link name) and in node mode (an entity), then, in node mode only,
    the link name the node was written with."""

    return _chunk((
        "concat",
        _op(opcode, _sub_expr(1)),
        ("call", "named_tail", _arg("e"), _arg("mode")),
    ))


def _lower_op_cases() -> list[tuple[str, tuple]]:
    return [
        ("lit", _chunk(_op("LIT", _sub_expr(1)))),
        ("arg", _chunk(_op("ARG", _sub_expr(1)))),
        ("eq", _chunk(_child(1), _child(2), _op("EQ"))),
        (
            "if",
            _chunk(
                _child(1),
                _op(
                    "BRANCH",
                    _ref(_sub_expr(2)),
                    _ref(_sub_expr(3)),
                ),
            ),
        ),
        (
            "seq",
            (
                "if",
                ("eq", ("len", _arg("e")), _lit(1)),
                _chunk(
                    _op(
                        "RAISE",
                        _lit("seq needs at least one expression"),
                    )
                ),
                (
                    "concat",
                    (
                        "call",
                        "seq_code",
                        _arg("e"),
                        _lit(1),
                        _arg("mode"),
                    ),
                    _END_CHUNK,
                ),
            ),
        ),
        (
            "call",
            _evals_from(
                2,
                _op("CALL", _sub_expr(1), _length_minus(2)),
            ),
        ),
        ("tuple", _evals_from(1, _op("MKTUPLE", _length_minus(1)))),
        (
            "inspect",
            _chunk(
                _child(1),
                _op("INSPECT"),
            ),
        ),
        (
            "record",
            _chunk(
                _child(1),
                _child(2),
                _op("RECORD"),
            ),
        ),
        (
            "len",
            _chunk(
                _child(1),
                _op("LEN"),
            ),
        ),
        (
            "item",
            _chunk(
                _child(1),
                _child(2),
                _op("ITEM"),
            ),
        ),
        (
            "slice",
            _chunk(
                _child(1),
                _child(2),
                _child(3),
                _op("SLICE"),
            ),
        ),
        (
            "concat",
            _chunk(
                _child(1),
                _op("TUPLE", _lit("concat")),
                _child(2),
                _op("TUPLE", _lit("concat")),
                _op("CONCAT"),
            ),
        ),
        (
            "let",
            _chunk(
                _op("LETCHECK", _sub_expr(1)),
                _child(2),
                _op("LETBIND", _sub_expr(1), _ref(_sub_expr(3))),
            ),
        ),
        ("ref", _named("REF")),
        (
            "closure",
            _chunk(
                _op(
                    "CLOSURE",
                    _ref(_sub_expr(3)),
                    _sub_expr(1),
                    _sub_expr(2),
                )
            ),
        ),
        (
            "apply",
            (
                "concat",
                (
                    "concat",
                    ("tuple", _child(1), _op("REFCHECK")),
                    (
                        "concat",
                        (
                            "call",
                            "evals",
                            _arg("e"),
                            _lit(2),
                            _lit(()),
                            _arg("mode"),
                        ),
                        ("tuple", _op("APPLY", _length_minus(2))),
                    ),
                ),
                _END_CHUNK,
            ),
        ),
        (
            "applyv",
            _chunk(
                _child(1),
                _op("REFCHECK"),
                _child(2),
                _op("TUPLE", _lit("applyv")),
                _op("APPLYV"),
            ),
        ),
        ("linksof", _named("LINKS")),
        ("read", _chunk(_op("READ", _sub_expr(1)))),
        ("write", _chunk(_child(2), _op("WRITE", _sub_expr(1)))),
        ("code", _named("CODE")),
        (
            "catch",
            _chunk(
                _op(
                    "CATCH",
                    _ref(_sub_expr(1)),
                    (
                        "if",
                        ("eq", ("len", _arg("e")), _lit(2)),
                        _lit(None),
                        _sub_expr(2),
                    ),
                )
            ),
        ),
        (
            "raise",
            _chunk(_child(1), _child(2), _op("FAIL")),
        ),
        (
            "label",
            ("call", "lower_op", _sub_expr(2), _arg("mode")),
        ),
        (
            "quote",
            _node_only(
                _evals_from(2, _op("QUOTE", _sub_expr(1), _length_minus(2)))
            ),
        ),
        ("unquote", _node_only(_chunk(_op("GOTO", _ref(_sub_expr(1)))))),
        (
            "function",
            _node_only(_chunk(_child(1), _child(2), _op("FUNCTION"))),
        ),
        (
            # (entries, targets, values): host lowering raises, with no
            # instruction before it, when the entries and values disagree.
            "activate",
            _node_only((
                "if",
                ("eq", ("len", _sub_expr(1)), ("len", _sub_expr(3))),
                _evals_chunk(
                    [_sub_expr(3)],
                    _op("ACTIVATE", _sub_expr(1), _sub_expr(2)),
                ),
                _chunk(_op("RAISE", _lit("activate needs link/value pairs"))),
            )),
        ),
        (
            # (entries, targets, problem, target, args, values): on a
            # disagreement the arguments are still evaluated first.
            "trial",
            _node_only((
                "if",
                ("eq", ("len", _sub_expr(1)), ("len", _sub_expr(6))),
                _evals_chunk(
                    [_sub_expr(5), _sub_expr(6)],
                    _op(
                        "TRIAL",
                        _sub_expr(1),
                        _sub_expr(2),
                        _sub_expr(3),
                        _sub_expr(4),
                        ("len", _sub_expr(5)),
                    ),
                ),
                _evals_chunk(
                    [_sub_expr(5)],
                    _op("RAISE", _lit("trial needs link/value pairs")),
                ),
            )),
        ),
        (
            # Only the host's node descriptors say "invalid"; as input form
            # it is an operation like any other unknown one.
            "invalid",
            (
                "if",
                ("eq", _arg("mode"), _lit(NODE)),
                _chunk(_op("RAISE", _sub_expr(1))),
                _chunk(_op("RAISE", _lit("unknown operation"))),
            ),
        ),
    ]


def _lower_op_body() -> tuple:
    chain: tuple = _chunk(_op("RAISE", _lit("unknown operation")))

    for name, chunk in reversed(_lower_op_cases()):
        chain = ("if", _is(name), chunk, chain)

    arithmetic = _chunk(
        _child(1),
        _op("INT", _arg("op")),
        _child(2),
        _op("INT", _arg("op")),
        ("tuple", _arg("up")),
    )

    return (
        "let",
        "op",
        _item(_arg("e"), 0),
        (
            "let",
            "up",
            ("call", "upper", _arg("op")),
            (
                "if",
                ("eq", _arg("up"), _lit(None)),
                chain,
                arithmetic,
            ),
        ),
    )


def _upper_body() -> tuple:
    body: tuple = _lit(None)

    for name in reversed(("add", "sub", "mul", "lt")):
        body = (
            "if",
            ("eq", _arg("op"), _lit(name)),
            _lit(name.upper()),
            body,
        )

    return body


def _evals_body() -> tuple:
    e, i, acc, mode = _arg("e"), _arg("i"), _arg("acc"), _arg("mode")

    return (
        "if",
        ("lt", i, ("len", e)),
        (
            "call",
            "evals",
            e,
            ("add", i, _lit(1)),
            (
                "concat",
                acc,
                (
                    "tuple",
                    _op("EVAL", ("call", "child", ("item", e, i), mode)),
                ),
            ),
            mode,
        ),
        acc,
    )


def _seq_code_body() -> tuple:
    e, i, mode = _arg("e"), _arg("i"), _arg("mode")
    operand = ("call", "child", ("item", e, i), mode)

    return (
        "if",
        ("eq", i, _length_minus(1)),
        ("tuple", _op("GOTO", operand)),
        (
            "concat",
            ("tuple", _op("EVAL", operand), _op("POP")),
            ("call", "seq_code", e, ("add", i, _lit(1)), mode),
        ),
    )


def _child_body() -> tuple:
    return (
        "if",
        ("eq", _arg("mode"), _lit(EXPANDED)),
        ("call", "lower", _arg("x")),
        _arg("x"),
    )


def _named_tail_body() -> tuple:
    return (
        "if",
        ("eq", _arg("mode"), _lit(EXPANDED)),
        _lit(()),
        ("tuple", _sub_expr(2)),
    )


def compiler_entities(
    extra: dict[str, EntityID] | None = None,
) -> dict[EntityID, Any]:
    """The compiler's functions and links, and ``self_lower``, which compiles
    the compiler's own ``lower`` by reading it with ``code``. ``extra`` adds
    link names to every function (the interpreter of ``vm.py``, so that they
    can be swapped for versions that run on it).
    """

    more = extra or {}

    def function(
        entity: EntityID,
        params: tuple[str, ...],
        body: tuple,
        **targets: EntityID,
    ) -> dict[EntityID, Any]:
        return {
            entity: Function(params, body),
            EntityID(f"{entity.value}.links"): links(
                entity, **targets, **more,
            ),
        }

    return {
        **function(
            LOWER,
            ("e",),
            ("call", "lower_op", _arg("e"), _lit(EXPANDED)),
            lower_op=LOWER_OP,
        ),
        **function(
            COMPILE_NODE,
            ("d",),
            ("call", "lower_op", _item(_arg("d"), 0), _lit(NODE)),
            lower_op=LOWER_OP,
        ),
        **function(
            LOWER_OP,
            ("e", "mode"),
            _lower_op_body(),
            lower_op=LOWER_OP,
            upper=UPPER,
            evals=EVALS,
            seq_code=SEQ_CODE,
            child=CHILD,
            named_tail=NAMED_TAIL,
        ),
        **function(UPPER, ("op",), _upper_body()),
        **function(
            EVALS,
            ("e", "i", "acc", "mode"),
            _evals_body(),
            evals=EVALS,
            child=CHILD,
        ),
        **function(
            SEQ_CODE,
            ("e", "i", "mode"),
            _seq_code_body(),
            seq_code=SEQ_CODE,
            child=CHILD,
        ),
        **function(CHILD, ("x", "mode"), _child_body(), lower=LOWER),
        **function(NAMED_TAIL, ("e", "mode"), _named_tail_body()),
        **function(
            SELF_LOWER,
            (),
            ("call", "lower", _item(("code", "lower"), 1)),
            lower=LOWER,
        ),
    }
