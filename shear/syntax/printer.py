"""Graph form to text: ``render`` and ``render_program`` (docs/syntax.md)."""

from __future__ import annotations

import json
import re
from typing import Any

from ..cells import CellDeclaration, cell_declaration
from ..constraints import IntRange, IsKind
from ..identity import EntityID
from ..lang import (
    _ARITY,
    _decode,
    _definition_of,
    function_at,
)
from ..state import State
from .lexer import RESERVED
from .forms import _TYPE_KINDS, _map_links, _tup


_IDENTIFIER = re.compile(r"[^\W\d]\w*")


class _NoSyntax(Exception):
    """A piece of input form the syntax cannot express (rendered as raw)."""


def _name(name: str) -> str:
    """A name as text: bare if it is an identifier, backquoted otherwise."""

    if _IDENTIFIER.fullmatch(name) and name not in RESERVED:
        return name

    out: list[str] = []

    for char in name:
        code = ord(char)

        if char in "\\`":
            out.append("\\" + char)
        elif char == "\n":
            out.append("\\n")
        elif char == "\r":
            out.append("\\r")
        elif char == "\t":
            out.append("\\t")
        elif code < 0x20 or code == 0x7F or 0xD800 <= code <= 0xDFFF:
            out.append(f"\\u{code:04x}")
        else:
            out.append(char)

    return "`" + "".join(out) + "`"


def _scalar(value: Any) -> bool:
    return value is None or isinstance(value, (bool, int, str))


def _data_text(value: Any) -> str:
    """A data literal as text; raises ``_NoSyntax`` for anything else."""

    if value is True:
        return "true"

    if value is False:
        return "false"

    if value is None:
        return "none"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)

    if _tup(value):
        items = [_data_text(item) for item in value]

        if len(items) == 1:
            return f"({items[0]},)"

        return "(" + ", ".join(items) + ")"

    raise _NoSyntax


def _raw_text(value: Any) -> str:
    """Data as text for ``raw``; a leaf the syntax cannot write is shown in
    angle brackets, which the parser rejects.
    """

    if _tup(value):
        items = [_raw_text(item) for item in value]
        return "(" + ", ".join(items) + ("," if len(items) == 1 else "") + ")"

    try:
        return _data_text(value)
    except _NoSyntax:
        return f"<{value!r}>"


# operation: (symbol, own precedence, left operand needs, right operand needs)
_INFIX = {
    "add": ("+", 2, 2, 3),
    "sub": ("-", 2, 2, 3),
    "mul": ("*", 3, 3, 4),
    "lt": ("<", 1, 2, 2),
    "eq": ("==", 1, 2, 2),
}


_PLAIN = {"inspect", "record", "len", "item", "slice", "concat", "raise"}


class _Renderer:
    """Prints the input form of one function as text.

    ``names`` maps the function's link names to the names of their current
    target entities; ``known`` is every global name. Precedence levels: 0
    inline if, ``fn`` and ``closure``, 1 comparison, 2 addition, 3
    multiplication, 4 atoms. ``mode`` is 0 in ordinary code, 1 in a quote
    template (holes allowed) and 2 in a template that is a literal's value
    (no holes).
    """

    def __init__(
        self,
        names: dict[str, str],
        known: frozenset[str],
    ) -> None:
        self.names = names
        self.known = known

    def raw(self, node: Any) -> str:
        mapped = _map_links(
            node,
            lambda name: self.names.get(name, name),
        )
        return "raw(" + _raw_text(mapped) + ")"

    # -- blocks ------------------------------------------------------------

    def block(
        self,
        node: Any,
        locs: frozenset[str],
        depth: int,
        tail: bool = True,
    ) -> list[str]:
        if _tup(node) and len(node) > 1 and node[0] == "seq":
            items = node[1:]
            lines: list[str] = []

            for index, item in enumerate(items):
                lines += self.statement(
                    item,
                    locs,
                    depth,
                    tail and index == len(items) - 1,
                )

            return lines

        return self.statement(node, locs, depth, tail)

    def statement(
        self,
        node: Any,
        locs: frozenset[str],
        depth: int,
        tail: bool,
    ) -> list[str]:
        pad = "    " * depth

        try:
            if _tup(node) and node and isinstance(node[0], str):
                op, rest = node[0], node[1:]

                if op == "seq" and len(rest) > 0:
                    return self.block(node, locs, depth, tail)

                if op == "let" and len(rest) == 3 and tail:
                    name = rest[0]

                    if (
                        not isinstance(name, str)
                        or not name
                        or name in self.known
                    ):
                        raise _NoSyntax

                    value = self.let_value(rest[1], locs)
                    return [
                        f"{pad}let {_name(name)} = {value}",
                        *self.block(
                            rest[2],
                            locs | {name},
                            depth,
                            True,
                        ),
                    ]

                if op == "if" and len(rest) == 3:
                    condition = self.operand(
                        rest[0],
                        locs,
                        0,
                        False,
                        0,
                    )
                    return [
                        f"{pad}if {condition}:",
                        *self.block(rest[1], locs, depth + 1, True),
                        f"{pad}else:",
                        *self.block(rest[2], locs, depth + 1, True),
                    ]

                if op == "write" and len(rest) == 2:
                    target = self.link(rest[0], 0)

                    if target in locs:
                        raise _NoSyntax

                    value = self.operand(
                        rest[1],
                        locs,
                        0,
                        False,
                        0,
                    )
                    return [f"{pad}{_name(target)} = {value}"]

            return [pad + self.expr(node, locs)[0]]
        except _NoSyntax:
            return [pad + self.raw(node)]

    def let_value(
        self,
        node: Any,
        locs: frozenset[str],
    ) -> str:
        """The value of a let: an expression, or a cell write."""

        if _tup(node) and len(node) == 3 and node[0] == "write":
            try:
                target = self.link(node[1], 0)

                if target not in locs:
                    return (
                        f"{_name(target)} = "
                        f"{self.operand(node[2], locs, 0, False, 0)}"
                    )
            except _NoSyntax:
                pass

        return self.operand(node, locs, 0, False, 0)

    # -- expressions -------------------------------------------------------

    def expr(
        self,
        node: Any,
        locs: frozenset[str],
        mode: int = 0,
        strict: bool = False,
    ) -> tuple[str, int]:
        try:
            return self._expr(node, locs, mode, strict)
        except _NoSyntax:
            if strict:
                raise

            return self.raw(node), 4

    def operand(
        self,
        node: Any,
        locs: frozenset[str],
        mode: int,
        strict: bool,
        need: int,
    ) -> str:
        text, prec = self.expr(node, locs, mode, strict)
        return text if prec >= need else "(" + text + ")"

    def link(
        self,
        link: Any,
        mode: int,
    ) -> str:
        """The global name for a link name: the current target entity's name
        in code; in a template the link name itself, which the code built
        from the template resolves through its own function's links.
        """

        if not isinstance(link, str):
            raise _NoSyntax

        target = (
            self.names.get(link)
            if mode == 0
            else (link if link in self.known else None)
        )

        if target is None:
            raise _NoSyntax

        return target

    def _expr(
        self,
        node: Any,
        locs: frozenset[str],
        mode: int,
        strict: bool,
    ) -> tuple[str, int]:
        if not _tup(node) or not node or not isinstance(node[0], str):
            raise _NoSyntax

        op, rest = node[0], node[1:]

        if op in _ARITY and len(rest) != _ARITY[op]:
            raise _NoSyntax

        def operand(child: Any, need: int = 0) -> str:
            return self.operand(
                child,
                locs,
                mode,
                strict,
                need,
            )

        if op == "lit":
            return self.literal(rest[0], locs, mode), 4

        if op == "arg":
            name = rest[0]

            if (
                not isinstance(name, str)
                or not name
                or name in self.known
            ):
                raise _NoSyntax

            if mode == 0 and name not in locs:
                raise _NoSyntax

            return _name(name), 4

        if op in _INFIX:
            symbol, prec, left, right = _INFIX[op]
            return (
                f"{operand(rest[0], left)} "
                f"{symbol} "
                f"{operand(rest[1], right)}",
                prec,
            )

        if op == "if":
            return (
                f"{operand(rest[1], 1)} "
                f"if {operand(rest[0], 1)} "
                f"else {operand(rest[2])}",
                0,
            )

        if op in ("call", "read", "ref", "code", "linksof"):
            if not rest:
                raise _NoSyntax

            name = self.link(rest[0], mode)

            if mode == 0 and name in locs:
                raise _NoSyntax

            if op == "read":
                return _name(name), 4

            if op == "call":
                return (
                    f"{_name(name)}("
                    f"{', '.join(operand(arg) for arg in rest[1:])}"
                    f")",
                    4,
                )

            return f"{op}({_name(name)})", 4

        if op == "apply":
            head = rest[0] if rest else None

            if (
                _tup(head)
                and len(head) == 2
                and head[0] == "arg"
                and isinstance(head[1], str)
            ):
                name = head[1]

                if (
                    name
                    and name not in self.known
                    and (mode != 0 or name in locs)
                ):
                    return (
                        f"{_name(name)}("
                        f"{', '.join(operand(arg) for arg in rest[1:])}"
                        f")",
                        4,
                    )

            target = operand(head)
            args = [operand(arg) for arg in rest[1:]]

            if len(args) == 1:
                packed = f"({args[0]},)"
            else:
                packed = "(" + ", ".join(args) + ")"

            return f"apply({target}, {packed})", 4

        if op == "applyv":
            return (
                f"apply({operand(rest[0])}, {operand(rest[1])})",
                4,
            )

        if op == "tuple":
            items = [operand(item) for item in rest]

            if len(items) == 1:
                return f"({items[0]},)", 4

            return "(" + ", ".join(items) + ")", 4

        if op in _PLAIN:
            return (
                f"{op}({', '.join(operand(arg) for arg in rest)})",
                4,
            )

        if op == "catch":
            if len(rest) == 1:
                return f"catch({operand(rest[0])})", 4

            if (
                len(rest) != 2
                or not _tup(rest[1])
                or not rest[1]
                or not all(
                    isinstance(kind, str) and kind
                    for kind in rest[1]
                )
                or len(set(rest[1])) != len(rest[1])
            ):
                raise _NoSyntax

            kinds = ", ".join(
                json.dumps(kind, ensure_ascii=False)
                for kind in rest[1]
            )
            return (
                f"catch({operand(rest[0])}, {kinds})",
                4,
            )

        if op == "quote":
            if mode != 0:
                raise _NoSyntax

            return (
                "quote("
                + self.expr(rest[0], locs, 1, True)[0]
                + ")",
                4,
            )

        if op == "unquote":
            if mode != 1 or len(rest) != 1:
                raise _NoSyntax

            return (
                "unquote("
                + self.expr(rest[0], locs, 0, False)[0]
                + ")",
                4,
            )

        if op == "function":
            if mode == 0:
                text = self.fn_form(rest, locs)

                if text is not None:
                    return text, 0

            return (
                f"function({operand(rest[0])}, {operand(rest[1])})",
                4,
            )

        if op == "closure":
            return self.closure_form(rest, locs, mode, strict), 0

        if op == "label":
            if (
                len(rest) != 2
                or not isinstance(rest[0], str)
                or not rest[0]
            ):
                raise _NoSyntax

            return (
                f"label({_name(rest[0])}, {operand(rest[1])})",
                4,
            )

        if op == "activate":
            if not rest or len(rest) % 2:
                raise _NoSyntax

            return (
                "activate("
                + ", ".join(
                    self.pairs(rest, locs, mode, strict)
                )
                + ")",
                4,
            )

        if op == "trial":
            call = rest[0] if rest else None

            if (
                not (
                    _tup(call)
                    and len(call) >= 2
                    and call[0] == "call"
                )
                or len(rest) % 2 == 0
            ):
                raise _NoSyntax

            name = self.link(call[1], mode)

            if mode == 0 and name in locs:
                raise _NoSyntax

            head = (
                f"{_name(name)}("
                f"{', '.join(operand(arg) for arg in call[2:])}"
                f")"
            )
            return (
                "trial("
                + ", ".join(
                    [
                        head,
                        *self.pairs(
                            rest[1:],
                            locs,
                            mode,
                            strict,
                        ),
                    ]
                )
                + ")",
                4,
            )

        raise _NoSyntax

    def pairs(
        self,
        items: tuple,
        locs: frozenset[str],
        mode: int,
        strict: bool,
    ) -> list[str]:
        """``TARGET = VALUE`` texts for the interleaved targets and values."""

        if len(items) % 2:
            raise _NoSyntax

        texts = []

        for target, value in zip(
            items[0::2],
            items[1::2],
        ):
            if (
                _tup(target)
                and len(target) == 2
                and isinstance(target[1], str)
                and target[1]
            ):
                name = self.link(target[0], mode)
                suffix = "." + _name(target[1])
            else:
                name = self.link(target, mode)
                suffix = ""

            if mode == 0 and name in locs:
                raise _NoSyntax

            texts.append(
                f"{_name(name)}{suffix} = "
                f"{self.operand(value, locs, mode, strict, 0)}"
            )

        return texts

    def literal(
        self,
        value: Any,
        locs: frozenset[str],
        mode: int,
    ) -> str:
        if mode == 0:
            if _scalar(value):
                return _data_text(value)

            if _tup(value):
                try:
                    return (
                        "quote("
                        + self.expr(value, locs, 2, True)[0]
                        + ")"
                    )
                except _NoSyntax:
                    return _data_text(value)

            raise _NoSyntax

        if _scalar(value):
            return _data_text(value)

        if (
            mode == 1
            and _tup(value)
            and len(value) == 2
            and value[0] == "unquote"
        ):
            return (
                "literal("
                + self.expr(value[1], locs, 0, False)[0]
                + ")"
            )

        raise _NoSyntax

    def fn_form(
        self,
        rest: tuple,
        locs: frozenset[str],
    ) -> str | None:
        """``fn(params): body`` for a function value with a literal body."""

        params, body = rest

        if not (
            _tup(params)
            and len(params) == 2
            and params[0] == "lit"
            and _tup(params[1])
            and all(
                isinstance(name, str) and name
                for name in params[1]
            )
            and len(set(params[1])) == len(params[1])
            and not any(name in self.known for name in params[1])
        ):
            return None

        if (
            _tup(body)
            and len(body) == 2
            and body[0] == "quote"
        ):
            mode, template = 1, body[1]
        elif (
            _tup(body)
            and len(body) == 2
            and body[0] == "lit"
            and _tup(body[1])
        ):
            mode, template = 2, body[1]
        else:
            return None

        try:
            text = self.expr(
                template,
                locs,
                mode,
                True,
            )[0]
        except _NoSyntax:
            return None

        return (
            "fn("
            + ", ".join(_name(name) for name in params[1])
            + "): "
            + text
        )

    def closure_form(
        self,
        rest: tuple,
        locs: frozenset[str],
        mode: int,
        strict: bool,
    ) -> str:
        """``closure(params) captures(names): body``."""

        if mode != 0 or len(rest) != 3:
            raise _NoSyntax

        params, captures, body = rest

        if not (
            _tup(params)
            and _tup(captures)
            and all(
                isinstance(name, str) and name
                for name in params
            )
            and all(
                isinstance(name, str) and name
                for name in captures
            )
            and len(set(params)) == len(params)
            and len(set(captures)) == len(captures)
            and not set(params) & set(captures)
            and not any(name in self.known for name in params)
            and not any(name in self.known for name in captures)
            and all(name in locs for name in captures)
        ):
            raise _NoSyntax

        closure_locs = frozenset((*captures, *params))
        body_text = self.expr(
            body,
            closure_locs,
            0,
            True,
        )[0]

        return (
            "closure("
            + ", ".join(_name(name) for name in params)
            + ") captures("
            + ", ".join(_name(name) for name in captures)
            + "): "
            + body_text
        )


def _global_names(state: State) -> frozenset[str]:
    return frozenset(
        entity.value
        for entity, value in state.values.items()
        if _definition_of(value) is not None
        or cell_declaration(value) is not None
    )


def _render(
    state: State,
    function: EntityID,
    known: frozenset[str],
) -> str:
    value = state.values.get(function)
    definition = (
        None
        if value is None
        else _definition_of(value)
    )
    code = function_at(state, function)

    if definition is None or code is None:
        raise ValueError(
            f"{function.value} is not a function of the state"
        )

    names = {
        link: target.value
        for link, target in definition.links.items()
        if isinstance(target, EntityID)
    }
    renderer = _Renderer(
        names,
        known | frozenset(names.values()),
    )
    params = ", ".join(
        _name(param)
        for param in code.params
    )
    lines = [
        f"fn {_name(function.value)}({params}):",
        *renderer.block(
            code.body,
            frozenset(code.params),
            1,
        ),
    ]
    return "\n".join(lines) + "\n"


def render(
    state: State,
    function: EntityID,
) -> str:
    """Print one function of a graph-form state as an ``fn`` declaration.

    Names are the current target entity names, so a rename shows in the
    text of the callers. Anything the syntax cannot express prints as
    ``raw(...)``.
    """

    return _render(
        state,
        function,
        _global_names(state),
    )


def _cell_text(
    entity: EntityID,
    declaration: CellDeclaration,
) -> str:
    name = _name(entity.value)
    constraint = declaration.constraint

    try:
        if isinstance(constraint, IntRange):
            low = (
                ""
                if constraint.min is None
                else str(constraint.min)
            )
            high = (
                ""
                if constraint.max is None
                else str(constraint.max)
            )
            kind = f"int in {low}..{high}"
        elif (
            isinstance(constraint, IsKind)
            and constraint.kind == "int"
        ):
            kind = "int"
        elif (
            isinstance(constraint, IsKind)
            and constraint.kind in _TYPE_KINDS.values()
        ):
            kind = next(
                text
                for text, k in _TYPE_KINDS.items()
                if k == constraint.kind
            )
        else:
            raise _NoSyntax

        return (
            f"cell {name}: {kind} = "
            f"{_data_text(_decode(declaration.initial))}"
        )
    except _NoSyntax:
        return f"# cell {name}: not expressible in the syntax"


def render_program(state: State) -> str:
    """Print every cell, then every function, of a graph-form state.

    Cells come first, then functions in ``EntityID`` order, separated by
    one blank line.
    """

    known = _global_names(state)
    cells: list[str] = []
    parts: list[str] = []

    for entity in sorted(state.values):
        value = state.values[entity]
        declaration = cell_declaration(value)

        if declaration is not None:
            cells.append(
                _cell_text(entity, declaration)
            )
        elif _definition_of(value) is not None:
            parts.append(
                _render(state, entity, known)
            )

    if cells:
        parts.insert(
            0,
            "\n".join(cells) + "\n",
        )

    return "\n".join(parts)
