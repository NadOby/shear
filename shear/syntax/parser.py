"""Text to the input format: ``parse`` (docs/syntax.md)."""

from __future__ import annotations

from typing import Any, Callable

from ..cells import CellDeclaration, cell_declaration
from ..constraints import IntRange, IsKind
from ..identity import EntityID
from ..operations import ARITY
from ..lang import (
    FUNCTION_ROLE,
    LINKS_KIND,
    Function,
    _definition_of,
    function_of,
)
from ..relations import Relation, relation_of
from ..state import State
from ..values import Value
from .lexer import RESERVED, SourceError, Token, tokenize
from .forms import _TYPE_KINDS, _map_links


_ORDINARY, _HOLES = 0, 1


def _base_kinds(base: State | None) -> dict[str, str]:
    kinds: dict[str, str] = {}

    if base is not None:
        for entity, value in base.values.items():
            if cell_declaration(value) is not None:
                kinds[entity.value] = "cell"
            elif function_of(value) is not None or _definition_of(value) is not None:
                kinds[entity.value] = "fn"

    return kinds


class _Parser:
    def __init__(self, tokens: list[Token], base: State | None) -> None:
        self.tokens = tokens
        self.pos = 0
        self.kinds = _base_kinds(base)
        self.declared: dict[str, str] = {}
        self.mode = _ORDINARY
        self.locals: list[str] = []
        self.used: dict[str, None] = {}
        self.collectors: list[dict[str, None]] = []
        self.extra: dict[str, dict[str, None]] = {}
        self._prescan()

    # -- token access ------------------------------------------------------

    def peek(self, ahead: int = 0) -> Token:
        return self.tokens[min(self.pos + ahead, len(self.tokens) - 1)]

    def next(self) -> Token:
        token = self.peek()

        if token.kind != "eof":
            self.pos += 1

        return token

    def error(self, message: str, token: Token | None = None) -> SourceError:
        token = token or self.peek()
        return SourceError(message, token.line, token.column)

    def is_op(self, value: str, ahead: int = 0) -> bool:
        token = self.peek(ahead)
        return token.kind == "op" and token.value == value

    def is_word(self, value: str, ahead: int = 0) -> bool:
        token = self.peek(ahead)
        return token.kind == "name" and not token.quoted and token.value == value

    def accept_op(self, value: str) -> bool:
        if self.is_op(value):
            self.next()
            return True

        return False

    def expect_op(self, value: str) -> Token:
        if not self.is_op(value):
            raise self.error(f"expected {value!r}")

        return self.next()

    def expect_int(self) -> int:
        token = self.next()

        if token.kind != "int":
            raise self.error("expected a number", token)

        return token.value

    def end_of_statement(self) -> None:
        token = self.peek()

        if token.kind != "newline":
            raise self.error("unexpected " + _describe(token))

        self.next()

    def _prescan(self) -> None:
        """Register every declared name first, so uses may come before it."""

        depth = 0
        at_start = True
        tokens = self.tokens

        for index, token in enumerate(tokens):
            if token.kind == "indent":
                depth += 1
            elif token.kind == "dedent":
                depth -= 1
            elif token.kind == "newline":
                at_start = True
            else:
                if (
                    at_start
                    and depth == 0
                    and token.kind == "name"
                    and not token.quoted
                    and token.value in ("cell", "fn")
                    and tokens[index + 1].kind == "name"
                ):
                    self.kinds[tokens[index + 1].value] = token.value

                at_start = False

    # -- declarations ------------------------------------------------------

    def run(self, base: State | None) -> State:
        entities: dict[EntityID, Any] = {}
        used_by: dict[str, dict[str, None]] = {}

        while True:
            token = self.peek()

            if token.kind == "eof":
                break

            if token.kind == "indent":
                raise self.error("unexpected indent")

            if self.is_word("cell"):
                name, content = self.cell()
                entities[EntityID(name)] = content
            elif self.is_word("fn"):
                name, content, used = self.function()
                entities[EntityID(name)] = content
                used_by[name] = used
            else:
                raise self.error(
                    "expected a 'cell' or 'fn' declaration, found " + _describe(token)
                )

        for name, used in used_by.items():
            used.update(self.extra.get(name, {}))

        return _merge(base, entities, used_by, self.declared)

    def declaration_name(self, kind: str) -> Token:
        token = self.next()

        if token.kind != "name":
            raise self.error("expected a name", token)

        if not token.quoted and token.value in RESERVED:
            raise self.error(
                f"{token.value!r} is reserved and cannot be declared "
                f"(write it in backquotes to use it as a name)",
                token,
            )

        if token.value in self.declared:
            raise self.error(f"{token.value!r} is already declared", token)

        self.declared[token.value] = kind
        return token

    def cell(self) -> tuple[str, CellDeclaration]:
        self.next()
        name = self.declaration_name("cell")
        self.expect_op(":")
        type_token = self.next()

        if type_token.kind != "name" or type_token.quoted:
            raise self.error("expected a cell type", type_token)

        constraint: IntRange | IsKind

        if type_token.value == "int":
            if self.is_word("in"):
                self.next()
                low = self.optional_int()
                self.expect_op("..")
                high = self.optional_int()

                try:
                    constraint = IntRange(low, high)
                except ValueError as exc:
                    raise self.error(str(exc), type_token) from None
            else:
                constraint = IsKind("int")
        elif type_token.value in _TYPE_KINDS:
            constraint = IsKind(_TYPE_KINDS[type_token.value])
        else:
            raise self.error(f"unknown cell type {type_token.value!r}", type_token)

        self.expect_op("=")
        initial = self.data()
        self.end_of_statement()
        return name.value, CellDeclaration(constraint, initial)

    def optional_int(self) -> int | None:
        if self.accept_op("-"):
            return -self.expect_int()

        if self.peek().kind == "int":
            return self.next().value

        return None

    def function(self) -> tuple[str, Function, dict[str, None]]:
        self.next()
        name = self.declaration_name("fn")
        self.expect_op("(")
        params = self.params()
        self.expect_op(":")
        self.locals = list(params)
        self.used = {}
        self.mode = _ORDINARY
        body = self.suite()

        try:
            function = Function(tuple(params), body)
        except TypeError as exc:
            raise self.error(str(exc), name) from None

        return name.value, function, self.used

    def params(self) -> list[str]:
        """Read parameter names up to and including the closing ``)``."""

        names: list[str] = []

        if self.accept_op(")"):
            return names

        while True:
            token = self.next()
            self.check_local(token)

            if token.value in names:
                raise self.error(f"duplicate parameter {token.value!r}", token)

            names.append(token.value)

            if self.accept_op(","):
                continue

            self.expect_op(")")
            return names

    def check_local(self, token: Token) -> None:
        if token.kind != "name":
            raise self.error("expected a name", token)

        if not token.quoted and token.value in RESERVED:
            raise self.error(
                f"{token.value!r} is reserved "
                f"(write it in backquotes to use it as a name)",
                token,
            )

        if token.value in self.kinds:
            raise self.error(
                f"{token.value!r} is both a local and a global name",
                token,
            )

    # -- blocks and statements ---------------------------------------------

    def suite(self) -> Any:
        if self.peek().kind != "newline":
            raise self.error("expected the end of the line after ':'")

        self.next()

        if self.peek().kind != "indent":
            raise self.error("expected an indented block")

        self.next()
        return self.block()

    def block(self) -> Any:
        mark = len(self.locals)
        items: list[tuple] = []

        while self.peek().kind not in ("dedent", "eof"):
            items.append(self.statement())

        if self.peek().kind == "dedent":
            self.next()

        del self.locals[mark:]
        return self.fold(items)

    def fold(self, items: list[tuple]) -> Any:
        nodes: list[Any] = []

        for index, item in enumerate(items):
            if item[0] == "let":
                _, name, value, token = item

                if index == len(items) - 1:
                    raise self.error("a let must be followed by a statement", token)

                nodes.append(("let", name, value, self.fold(items[index + 1:])))
                break

            nodes.append(item[1])

        return nodes[0] if len(nodes) == 1 else ("seq", *nodes)

    def statement(self) -> tuple:
        token = self.peek()

        if token.kind == "indent":
            raise self.error("unexpected indent")

        if self.is_word("let"):
            return self.let_statement()

        if self.is_word("if"):
            return self.if_statement()

        if self.is_word("else"):
            raise self.error("else without if")

        if token.kind == "name" and self.is_op("=", 1):
            return ("expr", self.assignment())

        node = self.expr()
        self.end_of_statement()
        return ("expr", node)

    def let_statement(self) -> tuple:
        token = self.next()
        name = self.next()
        self.check_local(name)
        self.expect_op("=")
        value = (
            self.write()
            if self.peek().kind == "name" and self.is_op("=", 1)
            else self.expr()
        )
        self.end_of_statement()
        self.locals.append(name.value)
        return ("let", name.value, value, token)

    def if_statement(self) -> tuple:
        token = self.next()
        condition = self.expr()
        self.expect_op(":")
        then = self.suite()

        if not self.is_word("else"):
            raise self.error("an if needs an else part", token)

        self.next()
        self.expect_op(":")
        other = self.suite()
        return ("expr", ("if", condition, then, other))

    def assignment(self) -> Any:
        node = self.write()
        self.end_of_statement()
        return node

    def write(self) -> Any:
        """``NAME = EXPR``: a write of a global cell, without its newline."""

        name = self.next()
        self.next()

        if name.value in self.locals:
            raise self.error(
                f"cannot assign to {name.value!r}: only global cells can be assigned",
                name,
            )

        if self.kinds.get(name.value) != "cell":
            raise self.error(f"cannot assign to {name.value!r}: it is not a cell", name)

        value = self.expr()
        self.use(name)
        return ("write", name.value, value)

    def use(self, token: Token) -> None:
        if token.value == FUNCTION_ROLE:
            raise self.error("'function' cannot be used as a global name", token)

        self.record(token.value)

    def record(self, name: str) -> None:
        self.used[name] = None

        # A name in a hole, or in a call that computes the code, belongs to
        # the enclosing function only; a name in the code being built (a
        # quote or an fn body) is also a name of the target it is installed in.
        if self.mode == _HOLES:
            for collector in self.collectors:
                collector[name] = None

    # -- expressions -------------------------------------------------------

    def expr(self) -> Any:
        node = self.comparison()

        if self.is_word("if"):
            self.next()
            condition = self.comparison()

            if not self.is_word("else"):
                raise self.error("expected 'else'")

            self.next()
            return ("if", condition, node, self.expr())

        return node

    def comparison(self) -> Any:
        left = self.additive()
        token = self.peek()

        if token.kind == "op" and token.value in ("<", "=="):
            self.next()
            node = ("lt" if token.value == "<" else "eq", left, self.additive())
            follow = self.peek()

            if follow.kind == "op" and follow.value in ("<", "=="):
                raise self.error("comparisons cannot be chained", follow)

            return node

        return left

    def additive(self) -> Any:
        node = self.multiplicative()

        while self.peek().kind == "op" and self.peek().value in ("+", "-"):
            op = "add" if self.next().value == "+" else "sub"
            node = (op, node, self.multiplicative())

        return node

    def multiplicative(self) -> Any:
        node = self.atom()

        while self.is_op("*"):
            self.next()
            node = ("mul", node, self.atom())

        return node

    def atom(self) -> Any:
        token = self.peek()

        if token.kind in ("int", "string"):
            self.next()
            return ("lit", token.value)

        if token.kind == "op":
            if token.value == "-":
                self.next()
                return ("lit", -self.expect_int())

            if token.value == "(":
                self.next()
                return self.parenthesized(
                    self.expr,
                    lambda items: ("tuple", *items),
                )

            raise self.error("unexpected " + _describe(token))

        if token.kind == "name":
            if not token.quoted and token.value in RESERVED:
                return self.builtin(token)

            return self.name_use(token)

        raise self.error("unexpected " + _describe(token))

    def parenthesized(
        self,
        element: Callable[[], Any],
        build: Callable[[list], Any],
    ) -> Any:
        """Read what follows ``(``: a group, or a tuple; consumes the ``)``."""

        if self.accept_op(")"):
            return build([])

        first = element()

        if self.accept_op(")"):
            return first

        items = [first]

        while self.accept_op(","):
            if self.accept_op(")"):
                return build(items)

            items.append(element())

            if self.accept_op(")"):
                return build(items)

        self.expect_op(")")
        raise AssertionError("unreachable")

    def call_args(self) -> list[Any]:
        self.expect_op("(")
        args: list[Any] = []

        if self.accept_op(")"):
            return args

        while True:
            args.append(self.expr())

            if self.accept_op(","):
                continue

            self.expect_op(")")
            return args

    def in_mode(self, mode: int, parse: Callable[[], Any]) -> Any:
        saved = self.mode
        self.mode = mode

        try:
            return parse()
        finally:
            self.mode = saved

    def name_use(self, token: Token) -> Any:
        self.next()
        name = token.value
        kind = self.kinds.get(name)
        call = self.is_op("(")

        if self.mode == _ORDINARY and name in self.locals:
            if call:
                return ("apply", ("arg", name), *self.call_args())

            return ("arg", name)

        if kind == "cell":
            if call:
                raise self.error(f"{name!r} is a cell and cannot be called", token)

            self.use(token)
            return ("read", name)

        if kind == "fn":
            if not call:
                raise self.error(
                    f"{name!r} is a function; write ref({name}) to use it as a value",
                    token,
                )

            self.use(token)
            return ("call", name, *self.call_args())

        if self.mode == _HOLES:
            if call:
                return ("apply", ("arg", name), *self.call_args())

            return ("arg", name)

        raise self.error(f"unknown name {name!r}", token)

    def global_function(self, token: Token) -> str:
        if token.kind != "name":
            raise self.error("expected a function name", token)

        if self.kinds.get(token.value) != "fn":
            raise self.error(f"{token.value!r} is not a declared function", token)

        self.use(token)
        return token.value

    def fixed_args(self, token: Token, count: int) -> list[Any]:
        args = self.call_args()

        if len(args) != count:
            raise self.error(
                f"{token.value} takes {count} argument(s), got {len(args)}",
                token,
            )

        return args

    def builtin(self, token: Token) -> Any:
        name = token.value
        self.next()

        if name in ("true", "false", "none"):
            return ("lit", {"true": True, "false": False, "none": None}[name])

        if name in ("inspect", "record", "len", "item", "slice", "concat"):
            return (name, *self.fixed_args(token, ARITY[name]))

        if name == "apply":
            return ("applyv", *self.fixed_args(token, 2))

        if name == "function":
            return ("function", *self.fixed_args(token, 2))

        if name == "raise":
            return ("raise", *self.fixed_args(token, 2))

        if name == "catch":
            self.expect_op("(")
            body = self.expr()

            if self.accept_op(")"):
                return ("catch", body)

            self.expect_op(",")
            kinds: list[str] = []

            while True:
                kind = self.next()

                if kind.kind != "string":
                    raise self.error(
                        "catch kinds must be string literals",
                        kind,
                    )

                kinds.append(kind.value)

                if self.accept_op(")"):
                    break

                self.expect_op(",")

            return ("catch", body, tuple(kinds))

        if name in ("ref", "code", "linksof"):
            self.expect_op("(")
            target = self.global_function(self.next())
            self.expect_op(")")
            return (name, target)

        if name == "fn":
            return self.fn_value(token)

        if name == "closure":
            return self.closure_value(token)

        if name == "quote":
            if self.mode == _HOLES:
                raise self.error("quote inside quote is not supported; use raw", token)

            self.expect_op("(")
            template = self.in_mode(_HOLES, self.expr)
            self.expect_op(")")
            return ("quote", template)

        if name in ("unquote", "literal"):
            if self.mode != _HOLES:
                raise self.error(f"{name} outside quote", token)

            self.expect_op("(")
            inner = self.in_mode(_ORDINARY, self.expr)
            self.expect_op(")")
            return (
                ("unquote", inner)
                if name == "unquote"
                else ("lit", ("unquote", inner))
            )

        if name == "label":
            self.expect_op("(")
            label = self.next()

            if label.kind != "name" or (
                not label.quoted and label.value in RESERVED
            ):
                raise self.error("expected a label name", label)

            self.expect_op(",")
            inner = self.expr()
            self.expect_op(")")
            return ("label", label.value, inner)

        if name == "activate":
            self.expect_op("(")
            return ("activate", *self.pairs(self.target_pair))

        if name == "trial":
            return self.trial(token)

        if name == "raw":
            self.expect_op("(")
            data = self.data()
            self.expect_op(")")
            # Raw data is code as data: its names are names of the code built.
            return self.in_mode(_HOLES, lambda: _map_links(data, self.use_raw))

        raise self.error(f"unexpected {name!r}", token)

    def use_raw(self, name: str) -> str:
        if name in self.kinds and name != FUNCTION_ROLE:
            self.record(name)

        return name

    def fn_value(self, token: Token) -> Any:
        if self.mode == _HOLES:
            raise self.error("fn inside quote is not supported; use raw", token)

        self.expect_op("(")
        params = self.params()
        self.expect_op(":")
        body = self.in_mode(_HOLES, self.expr)
        return ("function", ("lit", tuple(params)), ("quote", body))

    def closure_value(self, token: Token) -> Any:
        """Read ``closure(params) captures(names): body``."""

        if self.mode == _HOLES:
            raise self.error(
                "closure inside quote is not supported; use raw",
                token,
            )

        outer = tuple(self.locals)

        self.expect_op("(")
        params = self.params()

        if not self.is_word("captures"):
            raise self.error("expected 'captures' after closure parameters")

        self.next()
        self.expect_op("(")
        captures = self.params()

        overlap = set(params) & set(captures)

        if overlap:
            name = sorted(overlap)[0]
            raise self.error(
                f"{name!r} is both a closure parameter and a capture",
                token,
            )

        for name in captures:
            if name not in outer:
                raise self.error(
                    f"capture {name!r} is not in scope",
                    token,
                )

        self.expect_op(":")
        saved = self.locals
        self.locals = [*captures, *params]

        try:
            body = self.expr()
        finally:
            self.locals = saved

        return ("closure", tuple(params), tuple(captures), body)

    def target_pair(self) -> list[Any]:
        """One ``TARGET = VALUE`` pair of activate or trial."""

        token = self.next()
        target: Any = self.global_function(token)

        if self.accept_op("."):
            label = self.next()

            if label.kind != "name":
                raise self.error("expected a label name", label)

            target = (target, label.value)

        self.expect_op("=")
        installed: dict[str, None] = {}
        self.collectors.append(installed)

        try:
            value = self.expr()
        finally:
            self.collectors.pop()

        # The code installed into a function is resolved through that
        # function's links, so the names it uses are links of the target too.
        self.extra.setdefault(token.value, {}).update(installed)
        return [target, value]

    def pairs(
        self,
        pair: Callable[[], list[Any]],
        first: bool = True,
    ) -> list[Any]:
        """Read ``pair`` items separated by commas, up to and including ``)``."""

        items: list[Any] = []

        if first and self.is_op(")"):
            raise self.error("expected at least one TARGET = VALUE")

        while True:
            items.extend(pair())

            if self.accept_op(","):
                continue

            self.expect_op(")")
            return items

    def trial(self, token: Token) -> Any:
        self.expect_op("(")
        callee = self.global_function(self.next())
        call = ("call", callee, *self.call_args())
        items: list[Any] = []

        while self.accept_op(","):
            items.extend(self.target_pair())

        self.expect_op(")")
        return ("trial", call, *items)

    # -- data literals -----------------------------------------------------

    def data(self) -> Any:
        token = self.next()

        if token.kind in ("int", "string"):
            return token.value

        if token.kind == "op" and token.value == "-":
            return -self.expect_int()

        if token.kind == "op" and token.value == "(":
            return self.parenthesized(self.data, tuple)

        if (
            token.kind == "name"
            and not token.quoted
            and token.value in ("true", "false", "none")
        ):
            return {"true": True, "false": False, "none": None}[token.value]

        raise self.error("expected a data literal", token)


def _describe(token: Token) -> str:
    if token.kind == "eof":
        return "end of text"

    if token.kind in ("newline", "indent", "dedent"):
        return token.kind

    return repr(token.value)


def _merge(
    base: State | None,
    entities: dict[EntityID, Any],
    used_by: dict[str, dict[str, None]],
    declared: dict[str, str],
) -> State:
    """The state for the declarations, over ``base`` if there is one."""

    declared_ids = {EntityID(name) for name in declared}
    functions = {
        EntityID(name)
        for name, kind in declared.items()
        if kind == "fn"
    }
    values: dict[EntityID, Value] = {}

    if base is not None:
        stale = {
            entity
            for entity, value in base.values.items()
            if (relation := relation_of(value)) is not None
            and relation.kind == LINKS_KIND
            and relation.roles.get(FUNCTION_ROLE) in functions
        }

        for entity, value in base.values.items():
            if entity not in declared_ids and entity not in stale:
                values[entity] = value

    taken = set(values) | declared_ids

    for entity, content in entities.items():
        values[entity] = Value.create(entity, content)

    for name, used in used_by.items():
        if not used:
            continue

        links_id = EntityID(f"{name}.links")
        suffix = 0

        while links_id in taken:
            suffix += 1
            links_id = EntityID(f"{name}.links.{suffix}")

        taken.add(links_id)
        relation = Relation(
            LINKS_KIND,
            {
                FUNCTION_ROLE: EntityID(name),
                **{target: EntityID(target) for target in used},
            },
        )
        values[links_id] = Value.create(links_id, relation)

    ownership = {}

    if base is not None:
        ownership = {
            owner: tuple(child for child in children if child in values)
            for owner, children in base.ownership.items()
            if owner in values
        }

    return State.create(values, ownership)


def parse(text: str, base: State | None = None) -> State:
    """Read program text into an input-format state.

    The state holds the declared cells and functions, and a links relation
    for each function that uses global names. With ``base`` (an input-format
    state), it also holds every entity of ``base`` that the text does not
    declare, except the links relations of functions the text declares, and
    names resolve against ``base`` too. Raises ``SourceError``.
    """

    return _Parser(tokenize(text), base).run(base)
