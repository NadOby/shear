"""Acceptance tests for the two operations the interpreter needs and for the
bytecode interpreter written in SHEAR (docs/vm_in_shear.md, roadmap
task 10).
"""

import random
import unittest
from unittest import mock

from shear import (
    ActivationRejected,
    CellDeclaration,
    EntityID,
    IntRange,
    Runtime,
    State,
    canonical_serialize,
    canonicalize,
)
from shear import bytecode
from shear.bytecode import chunk_of
from shear.examples import self_hosting, vm
from shear.examples._support import program
from shear.lang import (
    Function,
    LanguageError,
    _definition_of,
    define,
    function_at,
    links,
    load,
    run,
)
from shear.relations import relation_of

T = EntityID("t")
G = EntityID("g")
C = EntityID("c")
LOWER = self_hosting.LOWER


def same(test: unittest.TestCase, actual, expected, message=None) -> None:
    test.assertEqual(
        canonical_serialize(canonicalize(actual)),
        canonical_serialize(canonicalize(expected)),
        message,
    )


def x() -> tuple:
    return ("arg", "x")


def user_entities(body: tuple, params: tuple = ("x",)) -> dict:
    """``t`` with the given body, and helpers it may call, link or apply."""

    return {
        T: Function(params, body),
        EntityID("t.links"): links(
            T, aa=EntityID("aa"), g=G, tw=EntityID("tw"), t=T, c=C
        ),
        EntityID("aa"): Function(("a",), ("sub", ("arg", "a"), ("lit", 1))),
        EntityID("aa.links"): links(EntityID("aa")),
        G: Function(("a", "b"), ("add", ("arg", "a"), ("mul", ("arg", "b"), ("lit", 2)))),
        EntityID("g.links"): links(G),
        EntityID("tw"): Function(("a",), ("add", ("arg", "a"), ("arg", "a"))),
        EntityID("tw.links"): links(EntityID("tw")),
        C: CellDeclaration(IntRange(0, 100), 0),
    }


_BASE = None


def machine(body: tuple, params: tuple = ("x",)) -> Runtime:
    """The compiler, the interpreter and the helpers, with ``t`` set to
    ``body``. The base state is built once: its nodes keep their chunks.
    """

    global _BASE

    if _BASE is None:
        _BASE = load(program({
            **self_hosting.compiler_entities(),
            **vm.vm_entities(),
            **user_entities(("lit", 0)),
        }))

    return Runtime(define(_BASE, {T: Function(params, body)}).destination)


def link_table(runtime: Runtime, entity: EntityID = T) -> tuple:
    definition = _definition_of(runtime.active.state.values[entity])

    return tuple(sorted(
        (name, target)
        for name, target in definition.links.items()
        if isinstance(target, EntityID)
    ))


def native(runtime: Runtime, *args):
    try:
        return "value", run(runtime, T, *args)
    except LanguageError as error:
        return "raised", type(error).__name__


def compiled(runtime: Runtime):
    """The chunk of ``t``, compiled by ``lower`` written in SHEAR."""

    return run(runtime, LOWER, function_at(runtime.active.state, T).body)


def interpreted(runtime: Runtime, chunk, *args):
    """Run ``t`` on the interpreter: hand its chunk to ``vm``."""

    definition = function_at(runtime.active.state, T)

    try:
        return "value", run(
            runtime, vm.VM, chunk, definition.params, args, link_table(runtime)
        )
    except LanguageError as error:
        return "raised", type(error).__name__


class HostOperationTests(unittest.TestCase):
    def state(self, body: tuple):
        return load(program(user_entities(body)))

    def test_applyv_calls_a_reference_with_a_tuple_of_arguments(self) -> None:
        runtime = Runtime(self.state(("applyv", ("ref", "g"), ("tuple", x(), ("lit", 5)))))

        self.assertEqual(run(runtime, T, 1), 11)

    def test_applyv_takes_the_arguments_from_any_tuple_value(self) -> None:
        runtime = Runtime(self.state(("applyv", ("ref", "g"), ("lit", (3, 4)))))

        self.assertEqual(run(runtime, T, 0), 11)

    def test_applyv_needs_a_tuple_a_reference_and_the_right_count(self) -> None:
        for body in (
            ("applyv", ("ref", "g"), ("lit", 3)),
            ("applyv", ("lit", 3), ("tuple",)),
            ("applyv", ("ref", "g"), ("tuple", x())),
            ("applyv", ("ref", "g"), ("tuple", x(), x(), x())),
            ("applyv", ("ref", "c"), ("tuple",)),
        ):
            with self.subTest(body=body):
                with self.assertRaises(LanguageError):
                    run(Runtime(self.state(body)), T, 1)

    def test_applyv_checks_the_reference_before_it_evaluates_the_arguments(self) -> None:
        body = ("applyv", ("lit", 3), ("seq", ("write", "c", ("lit", 7)), ("tuple",)))
        runtime = Runtime(self.state(body))

        with self.assertRaises(LanguageError):
            run(runtime, T, 1)

        self.assertEqual(runtime.read(C), 0)

    def test_applyv_keeps_tail_calls_tail(self) -> None:
        loop = EntityID("loop")
        body = (
            "if",
            ("eq", ("arg", "n"), ("lit", 0)),
            ("lit", "done"),
            ("applyv", ("ref", "loop"), ("tuple", ("sub", ("arg", "n"), ("lit", 1)))),
        )
        state = load(program({
            loop: Function(("n",), body),
            EntityID("loop.links"): links(loop, loop=loop),
        }))

        with mock.patch.object(bytecode, "CALL_DEPTH_LIMIT", 50):
            self.assertEqual(run(Runtime(state), loop, 3000), "done")

    def test_linksof_returns_the_link_table_as_name_and_entity_pairs(self) -> None:
        body = ("linksof", "t")
        state = self.state(body)

        self.assertEqual(
            run(Runtime(state), T, 0),
            (
                ("aa", EntityID("aa")), ("c", C), ("g", G), ("t", T),
                ("tw", EntityID("tw")),
            ),
        )

    def test_linksof_of_something_that_is_not_a_function_raises(self) -> None:
        state = load(program({
            T: Function((), ("linksof", "c")),
            EntityID("t.links"): links(T, c=C),
            C: CellDeclaration(IntRange(0, 100), 0),
        }))

        with self.assertRaises(LanguageError):
            run(Runtime(state), T)

    def test_both_survive_the_round_trip_through_graph_form(self) -> None:
        for body in (
            ("applyv", ("ref", "g"), ("tuple", x(), x())),
            ("linksof", "g"),
        ):
            with self.subTest(body=body):
                self.assertEqual(function_at(self.state(body), T).body, body)

    def test_both_lower_to_the_instructions_the_interpreter_reads(self) -> None:
        state = self.state(("applyv", ("ref", "g"), ("tuple", x(), x())))
        root = _definition_of(state.values[T]).body

        self.assertEqual(
            [instruction[0] for instruction in chunk_of(state, root)],
            ["EVAL", "REFCHECK", "EVAL", "TUPLE", "APPLYV", "END"],
        )

        state = self.state(("linksof", "g"))
        root = _definition_of(state.values[T]).body

        self.assertEqual(chunk_of(state, root)[0], ("LINKS", G, "g"))


class EqualityTests(unittest.TestCase):
    """``eq`` is equality of canonical values: kinds are never mixed."""

    def value(self, left, right) -> bool:
        runtime = Runtime(load(program(user_entities(("eq", ("lit", left), ("lit", right))))))

        return run(runtime, T, 0)

    def test_equal_and_different_primitives(self) -> None:
        cases = [
            (1, 1, True), (1, 2, False), ("a", "a", True), ("a", "b", False),
            (None, None, True), (True, True, True), (True, False, False),
            (1, True, False), (0, False, False), (1, "1", False),
            (None, 0, False), ("", None, False), ((1, 2), (1, 2), True),
            ((1,), (True,), False), ((), (), True), (1, (1,), False),
        ]

        for left, right, expected in cases:
            with self.subTest(left=left, right=right):
                self.assertIs(self.value(left, right), expected)


class InterpreterTests(unittest.TestCase):
    """The interpreter written in SHEAR does what the machine does."""

    def agree(self, body: tuple, *arguments) -> tuple:
        runtime = machine(body)
        chunk = compiled(runtime)
        expected = native(runtime, *arguments)
        actual = interpreted(runtime, chunk, *arguments)

        self.assertEqual(actual[0], expected[0], (body, arguments))

        if expected[0] == "value":
            same(self, actual[1], expected[1], (body, arguments))
        else:
            self.assertEqual(actual, expected)

        return actual

    def test_every_instruction_it_runs(self) -> None:
        one, two = ("lit", 1), ("lit", 2)
        cases = [
            one, ("lit", (1, 2)), ("lit", None), x(),
            ("add", x(), one), ("sub", x(), two), ("mul", x(), x()),
            ("lt", x(), two), ("eq", x(), one), ("eq", one, ("lit", True)),
            ("if", ("lt", x(), two), ("add", x(), one), ("mul", x(), two)),
            ("seq",), ("seq", ("lit", 9)), ("seq", one, two, x()),
            ("tuple",), ("tuple", x(), one), ("len", ("tuple", x(), one, two)),
            ("item", ("tuple", x(), one), one),
            ("slice", ("tuple", x(), one, two), one, ("lit", 3)),
            ("concat", ("tuple", x()), ("tuple", one, two)),
            ("call", "g", x(), one), ("call", "tw", ("call", "tw", x())),
            ("let", "a", ("add", x(), one), ("mul", ("arg", "a"), ("arg", "a"))),
            ("let", "a", one, ("let", "b", two, ("add", ("arg", "a"), ("arg", "b")))),
            ("apply", ("ref", "g"), x(), one), ("apply", ("ref", "tw"), x()),
            ("call", "aa", x()), ("apply", ("ref", "aa"), x()),
            ("applyv", ("ref", "g"), ("tuple", one, x())),
            ("label", "k", ("add", x(), one)),
            ("if", ("lit", True), ("let", "a", x(), ("arg", "a")), one),
        ]

        for body in cases:
            for argument in (-1, 3):
                with self.subTest(body=body, argument=argument):
                    self.agree(body, argument)

    def test_errors_are_language_errors_on_both(self) -> None:
        one = ("lit", 1)
        cases = [
            ("add", ("lit", "a"), one), ("add", one, ("lit", True)),
            ("lt", ("lit", None), one), ("len", one), ("item", ("tuple",), one),
            ("item", ("tuple", one), ("lit", 5)),
            ("slice", ("tuple", one), one, ("lit", 4)),
            ("concat", one, ("tuple",)), ("if", one, one, one),
            ("call", "g", one), ("apply", ("lit", 3), one),
            ("apply", ("ref", "g"), one), ("apply", ("ref", "c")),
            ("let", "x", one, one), ("let", "a", one, ("let", "a", one, one)),
            ("applyv", ("ref", "g"), ("lit", 3)),
        ]

        for body in cases:
            with self.subTest(body=body):
                self.assertEqual(self.agree(body, 3), ("raised", "LanguageError"))

    def test_a_check_happens_before_the_next_operand_runs(self) -> None:
        # The chunk checks the first operand of add before the second is
        # evaluated; the second calls tw, whose result cannot be observed,
        # but an error in the first must be the one raised.
        body = ("add", ("lit", "a"), ("call", "g", ("lit", 1)))

        self.assertEqual(self.agree(body, 0), ("raised", "LanguageError"))

    def test_what_it_does_not_run_raises_where_the_machine_does_not(self) -> None:
        # Deviation (vm_in_shear.md section 3): the interpreter has no way
        # to name a cell or read a function by name, so these instructions
        # raise.
        for body in (
            ("read", "c"),
            ("write", "c", ("lit", 1)),
            ("code", "g"),
            ("linksof", "g"),
        ):
            with self.subTest(body=body):
                runtime = machine(body)

                self.assertEqual(native(runtime, 0)[0], "value")
                self.assertEqual(
                    interpreted(runtime, compiled(runtime), 0),
                    ("raised", "LanguageError"),
                )

    def test_the_interpreter_tail_calls_for_the_interpreted_tail_call(self) -> None:
        loop = EntityID("loop")
        body = (
            "if",
            ("eq", ("arg", "n"), ("lit", 0)),
            ("arg", "acc"),
            (
                "call", "loop",
                ("sub", ("arg", "n"), ("lit", 1)),
                ("add", ("arg", "acc"), ("lit", 2)),
            ),
        )
        runtime = Runtime(load(program({
            **self_hosting.compiler_entities(),
            **vm.vm_entities(),
            loop: Function(("n", "acc"), body),
            EntityID("loop.links"): links(loop, loop=loop, vm=vm.VM),
        })))
        chunk = run(runtime, LOWER, body)
        table = link_table(runtime, loop)

        # Replace `loop` by a function that runs its own chunk on the
        # interpreter; the recursion now goes through the interpreter.
        wrapper = Function(
            ("n", "acc"),
            (
                "call", "vm", ("lit", chunk), ("lit", ("n", "acc")),
                ("tuple", ("arg", "n"), ("arg", "acc")), ("lit", table),
            ),
        )
        runtime.activate(define(runtime.active.state, {loop: wrapper}))

        with mock.patch.object(bytecode, "CALL_DEPTH_LIMIT", 60):
            self.assertEqual(run(runtime, loop, 500, 0), 1000)

    def test_deep_interpreted_recursion_that_is_not_a_tail_call(self) -> None:
        total = EntityID("total")
        body = (
            "if",
            ("eq", ("arg", "n"), ("lit", 0)),
            ("lit", 0),
            ("add", ("arg", "n"), ("call", "total", ("sub", ("arg", "n"), ("lit", 1)))),
        )
        runtime = Runtime(load(program({
            **self_hosting.compiler_entities(),
            **vm.vm_entities(),
            total: Function(("n",), body),
            EntityID("total.links"): links(total, total=total, vm=vm.VM),
        })))
        chunk = run(runtime, LOWER, body)
        wrapper = Function(
            ("n",),
            (
                "call", "vm", ("lit", chunk), ("lit", ("n",)),
                ("tuple", ("arg", "n")), ("lit", link_table(runtime, total)),
            ),
        )
        runtime.activate(define(runtime.active.state, {total: wrapper}))

        self.assertEqual(run(runtime, total, 300), 300 * 301 // 2)


class Generator:
    """Seeded random programs of what the interpreter runs. Mostly well
    typed, with some mistakes so that some of them raise.
    """

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.names = 0
        self.scope: list[str] = []

    def mistake(self) -> bool:
        return self.rng.random() < 0.04

    def expression(self, depth: int) -> tuple:
        return self.number(depth)

    def number(self, depth: int) -> tuple:
        rng = self.rng

        if self.mistake():
            return rng.choice([("lit", "s"), ("lit", True), ("lit", None)])

        if depth == 0:
            leaves = [("lit", rng.randint(-2, 3)), x()]
            leaves += [("arg", name) for name in self.scope]

            return rng.choice(leaves)

        sub = lambda: self.number(depth - 1)
        kind = rng.choice([
            "add", "sub", "mul", "if", "seq", "let", "call", "call2", "apply",
            "applyv", "item", "len", "leaf",
        ])

        if kind in ("add", "sub", "mul"):
            return (kind, sub(), sub())
        if kind == "if":
            return ("if", self.boolean(depth - 1), sub(), sub())
        if kind == "seq":
            return ("seq", sub(), sub())
        if kind == "let":
            self.names += 1
            name = f"v{self.names}"
            value = sub()
            self.scope.append(name)
            body = sub()
            self.scope.pop()

            return ("let", name, value, body)
        if kind == "call":
            return ("call", "g", sub(), sub())
        if kind == "call2":
            return ("call", "tw", sub())
        if kind == "apply":
            return ("apply", ("ref", "g"), sub(), sub())
        if kind == "applyv":
            return ("applyv", ("ref", "tw"), ("tuple", sub()))
        if kind == "item":
            return ("item", self.tuple(depth - 1), ("lit", rng.randint(0, 3)))
        if kind == "len":
            return ("len", self.tuple(depth - 1))

        return self.number(0)

    def tuple(self, depth: int) -> tuple:
        rng = self.rng

        if depth <= 0:
            return rng.choice([("lit", (1, 2, 3)), ("tuple", x(), ("lit", 5))])

        kind = rng.choice(["tuple", "concat", "slice", "lit"])

        if kind == "tuple":
            return ("tuple", *(self.number(depth - 1) for _ in range(rng.randint(0, 3))))
        if kind == "concat":
            return ("concat", self.tuple(depth - 1), self.tuple(depth - 1))
        if kind == "slice":
            return ("slice", self.tuple(depth - 1), ("lit", rng.randint(0, 1)), ("lit", rng.randint(1, 2)))

        return self.tuple(0)

    def boolean(self, depth: int) -> tuple:
        rng = self.rng
        kind = rng.choice(["lt", "eq", "lit"])

        if kind == "lt":
            return ("lt", self.number(depth), self.number(depth))
        if kind == "eq":
            return ("eq", self.number(depth), self.number(depth))

        return ("lit", rng.choice([True, False]))


class InterpreterPropertyTests(unittest.TestCase):
    def test_seeded_random_programs_run_the_same_on_the_interpreter(self) -> None:
        raised = 0
        computed = 0

        for seed in range(60):
            body = Generator(seed).expression(4)

            with self.subTest(seed=seed):
                runtime = machine(body)
                chunk = compiled(runtime)

                for argument in (-1, 3):
                    expected = native(runtime, argument)
                    actual = interpreted(runtime, chunk, argument)

                    self.assertEqual(actual[0], expected[0], (body, argument))

                    if expected[0] == "value":
                        same(self, actual[1], expected[1], (body, argument))
                        computed += 1
                    else:
                        self.assertEqual(actual, expected)
                        raised += 1

        self.assertGreater(computed, 50)
        self.assertGreater(raised, 6)


class BootstrapTests(unittest.TestCase):
    """The compiler, swapped for versions that run on the interpreter."""

    EXPRESSIONS = [
        ("lit", 7), ("arg", "x"), ("add", ("arg", "x"), ("lit", 1)),
        ("if", ("lt", ("arg", "x"), ("lit", 1)), ("lit", 1), ("arg", "x")),
        ("seq",), ("seq", ("lit", 1), ("arg", "x")),
        ("call", "f", ("lit", 1), ("arg", "x")),
        ("let", "a", ("lit", 1), ("arg", "a")), ("label", "k", ("lit", 1)),
        ("quote", ("lit", 1)),
    ]

    def runtime(self) -> Runtime:
        return Runtime(load(program(vm.bootstrap_entities())))

    _swapped = None

    @classmethod
    def swapped(cls):
        """One bootstrapped runtime, with what ``lower`` gave before the swap
        and after it, shared by the tests that only read it.
        """

        if cls._swapped is None:
            runtime = cls().runtime()
            expressions = cls.EXPRESSIONS + [
                Generator(seed).expression(3) for seed in range(5)
            ]
            # The compiler's own code to compile is the lowering core;
            # ``lower`` itself only delegates to it.
            original = function_at(
                runtime.active.state, EntityID("lower_op")
            ).body
            before = [run(runtime, LOWER, e) for e in expressions]
            before_self = run(runtime, LOWER, original)

            run(runtime, vm.SWAP_ALL, may_activate=True)

            after = [run(runtime, LOWER, e) for e in expressions]
            after_self = run(runtime, LOWER, original)
            cls._swapped = (
                runtime, expressions, before, after, before_self, after_self,
            )

        return cls._swapped

    def test_the_swapped_compiler_gives_what_the_native_one_gave(self) -> None:
        _, expressions, before, after, _, _ = self.swapped()

        for expression, then, now in zip(expressions, before, after):
            with self.subTest(expression=expression):
                same(self, now, then)

    def test_every_function_of_the_compiler_is_now_a_call_of_the_interpreter(self) -> None:
        runtime = self.swapped()[0]

        for name in vm.SWAPPED:
            with self.subTest(function=name):
                body = function_at(runtime.active.state, EntityID(name)).body

                self.assertEqual(body[:2], ("call", "vm"))

        # The interpreter itself is not swapped: it would call itself.
        self.assertNotEqual(
            function_at(runtime.active.state, vm.RUN).body[:2], ("call", "vm")
        )

    def test_the_compiler_compiles_itself_to_the_same_chunk_on_its_own_bytecode(self) -> None:
        _, _, _, _, before, after = self.swapped()

        same(self, after, before)
        self.assertGreater(len(canonical_serialize(canonicalize(after))), 2000)

    def test_one_function_can_be_swapped_and_its_chunk_is_returned(self) -> None:
        runtime = self.runtime()
        state = runtime.active.state
        expected = run(runtime, LOWER, function_at(state, EntityID("upper")).body)

        returned = run(runtime, vm._swap_name("upper"), may_activate=True)

        same(self, returned, expected)
        self.assertEqual(
            function_at(runtime.active.state, EntityID("upper")).body[:2],
            ("call", "vm"),
        )
        self.assertEqual(run(runtime, EntityID("upper"), "sub"), "SUB")

    def test_swapping_needs_the_capability(self) -> None:
        with self.assertRaises(ActivationRejected):
            run(self.runtime(), vm.SWAP_ALL)

    def test_a_second_run_rebuilds_again_from_retained_source(self) -> None:
        runtime = self.runtime()
        run(runtime, vm.SWAP_ALL, may_activate=True)

        # A second run recompiles the retained source with the installed
        # compiler rather than compiling the wrappers it installed.
        run(runtime, vm.SWAP_ALL, may_activate=True)

        same(
            self,
            run(runtime, LOWER, ("add", ("arg", "x"), ("lit", 1))),
            (
                ("EVAL", (("ARG", "x"), ("END",))), ("INT", "add"),
                ("EVAL", (("LIT", 1), ("END",))), ("INT", "add"),
                ("ADD",), ("END",),
            ),
        )


if __name__ == "__main__":
    unittest.main()
