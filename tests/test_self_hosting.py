"""Acceptance tests for the code reader and the compiler written in SHEAR
(docs/self_hosting.md, roadmap task 8).
"""

import random
import unittest

from shear import (
    CellDeclaration,
    EntityID,
    IntRange,
    Runtime,
    State,
    canonicalize,
    canonical_serialize,
)
from shear.bytecode import chunk_of
from shear.examples import self_hosting
from shear.examples._support import program
from shear.lang import (
    Function,
    LanguageError,
    _decode,
    _definition_of,
    function_at,
    links,
    load,
    run,
)
from shear.relations import relation_of

F = EntityID("f")
G = EntityID("g")
C = EntityID("c")
T = EntityID("t")
LOWER = self_hosting.LOWER


def expand(state: State, entity: EntityID):
    """The chunk of a node with every child reference replaced by the
    child's own expanded chunk, and every entity operand by its link name,
    which is the form the compiler in SHEAR produces.
    """

    node = relation_of(state.values[entity])
    name = _decode(node.payload) if node.kind in (
        "call", "ref", "code", "linksof", "read", "write",
    ) else None
    out = []

    for instruction in chunk_of(state, entity):
        op = instruction[0]

        if op == "LIT":
            out.append(("LIT", _decode(instruction[1])))
        elif op in ("EVAL", "GOTO"):
            out.append((op if op == "EVAL" else "GOTO", expand(state, instruction[1])))
        elif op == "BRANCH":
            out.append(("BRANCH", expand(state, instruction[1]), expand(state, instruction[2])))
        elif op == "LETBIND":
            out.append(("LETBIND", instruction[1], expand(state, instruction[2])))
        elif op == "CATCH":
            out.append(("CATCH", expand(state, instruction[1]), instruction[2]))
        elif op == "CALL":
            out.append(("CALL", name, instruction[2]))
        elif op in ("REF", "CODE", "LINKS"):
            out.append((op, name))
        elif op in ("READ", "WRITE"):
            out.append((op, name))
        else:
            out.append(instruction)

    return tuple(out)


def same(test: unittest.TestCase, actual, expected, message=None) -> None:
    """Semantic equality: values taken apart at run time may be canonical
    nodes, and the language compares by canonical form.
    """

    test.assertEqual(
        canonical_serialize(canonicalize(actual)),
        canonical_serialize(canonicalize(expected)),
        message,
    )


def body_root(state: State, function: EntityID) -> EntityID:
    return _definition_of(state.values[function]).body


def host_chunk(state: State, function: EntityID):
    return expand(state, body_root(state, function))


def single(expression: tuple):
    """A loaded state with one function ``t`` whose body is ``expression``."""

    return load(program({
        F: Function(("x",), ("lit", 1)),
        C: CellDeclaration(IntRange(0, 100), 0),
        T: Function(("x",), expression),
        EntityID("t.links"): links(T, f=F, c=C, t=T),
    }))


class CodeOperationTests(unittest.TestCase):
    BODY = ("add", ("label", "one", ("lit", 1)), ("arg", "x"))

    def state(self) -> State:
        return load(program({
            F: Function(("x",), self.BODY),
            C: CellDeclaration(IntRange(0, 100), 0),
            G: Function((), ("code", "f")),
            EntityID("g.links"): links(G, f=F, c=C),
            T: Function((), ("code", "c")),
            EntityID("t.links"): links(T, c=C),
        }))

    def test_code_returns_the_parameters_and_the_body_in_input_form(self) -> None:
        state = self.state()

        result = run(Runtime(state), G)

        same(self, result, (("x",), self.BODY))
        self.assertEqual(function_at(state, F), Function(*result))

    def test_a_body_read_with_code_installs_as_the_same_input_form(self) -> None:
        state = self.state()
        again = load(program({
            F: Function(("x",), self.BODY),
            C: CellDeclaration(IntRange(0, 100), 0),
            G: Function(
                (),
                ("activate", "f", ("function", ("item", ("code", "f"), ("lit", 0)),
                                   ("item", ("code", "f"), ("lit", 1)))),
            ),
            EntityID("g.links"): links(G, f=F, c=C),
        }))
        runtime = Runtime(again)

        run(runtime, G, may_activate=True)

        # The code is the same; a whole-function swap builds new nodes, so
        # the version is not (self_hosting.md section 2).
        self.assertEqual(function_at(runtime.active.state, F), function_at(state, F))
        self.assertEqual(run(runtime, EntityID("f"), 4), 5)

    def test_reading_needs_no_capability(self) -> None:
        same(self, run(Runtime(self.state()), G, may_activate=False)[0], ("x",))

    def test_code_reads_the_active_version_after_an_activation(self) -> None:
        state = load(program({
            F: Function(("x",), ("lit", 1)),
            G: Function(
                (),
                (
                    "seq",
                    ("activate", "f", ("function", ("lit", ("y",)), ("lit", ("lit", 2)))),
                    ("code", "f"),
                ),
            ),
            EntityID("g.links"): links(G, f=F),
        }))

        same(self, run(Runtime(state), G, may_activate=True), (("y",), ("lit", 2)))

    def test_code_of_something_that_is_not_a_function_is_a_language_error(self) -> None:
        with self.assertRaises(LanguageError):
            run(Runtime(self.state()), T)

    def test_code_of_an_unknown_link_is_a_language_error(self) -> None:
        state = load(program({
            F: Function((), ("code", "nowhere")),
            EntityID("f.links"): links(F),
        }))

        with self.assertRaisesRegex(LanguageError, "unknown link 'nowhere'"):
            run(Runtime(state), F)

    def test_code_survives_the_round_trip_through_graph_form(self) -> None:
        body = ("seq", ("code", "f"), ("lit", 1))
        state = load(program({
            F: Function((), body),
            EntityID("f.links"): links(F, f=F),
        }))

        self.assertEqual(function_at(state, F), Function((), body))

    def test_code_lowers_to_one_instruction(self) -> None:
        state = self.state()
        root = body_root(state, G)

        self.assertEqual(chunk_of(state, root), (("CODE", F, "f"), ("END",)))


class CompilerAgreesWithTheHostTests(unittest.TestCase):
    """``lower`` in SHEAR gives what ``shear.bytecode`` gives."""

    def runtime(self) -> Runtime:
        return Runtime(load(program(self_hosting.compiler_entities())))

    def check(self, runtime: Runtime, expression: tuple) -> None:
        state = single(expression)

        same(self, run(runtime, LOWER, expression), host_chunk(state, T), expression)

    def test_every_operation_the_compiler_covers(self) -> None:
        runtime = self.runtime()
        x, one = ("arg", "x"), ("lit", 1)
        expressions = [
            one, ("lit", ()), ("lit", ("a", (1, 2))), ("lit", None), x,
            ("add", x, one), ("sub", x, one), ("mul", x, one), ("lt", x, one),
            ("eq", x, one), ("if", x, one, x), ("seq",), ("seq", one),
            ("seq", one, x, one), ("call", "f"), ("call", "f", x, one, x),
            ("tuple",), ("tuple", x, one), ("len", x), ("item", x, one),
            ("slice", x, one, one), ("concat", x, x),
            ("let", "a", one, ("arg", "a")), ("ref", "f"),
            ("apply", ("ref", "f")), ("apply", ("ref", "f"), x, one),
            ("read", "c"), ("write", "c", one), ("code", "f"),
            ("linksof", "f"), ("applyv", ("ref", "f"), ("tuple", x, one)),
            ("label", "k", ("add", x, one)),
            ("catch", x), ("catch", x, ("a", "b")),
            ("raise", ("lit", "k"), x),
        ]

        for expression in expressions:
            with self.subTest(expression=expression):
                self.check(runtime, expression)

    def test_seeded_random_expressions(self) -> None:
        runtime = self.runtime()

        for seed in range(60):
            with self.subTest(seed=seed):
                self.check(runtime, Generator(seed).expression(4))

    def test_operations_it_does_not_cover_lower_to_a_raise(self) -> None:
        runtime = self.runtime()

        for expression in (
            ("quote", ("lit", 1)),
            ("function", ("lit", ()), ("lit", ("lit", 1))),
            ("activate", "f", ("lit", 1)),
            ("frobnicate", ("lit", 1)),
        ):
            with self.subTest(expression=expression):
                same(
                    self,
                    run(runtime, LOWER, expression),
                    (("RAISE", "unknown operation"), ("END",)),
                )


class CompilerCompilesItselfTests(unittest.TestCase):
    def state(self) -> State:
        return load(program(self_hosting.compiler_entities()))

    def test_it_lowers_each_of_its_own_functions_as_the_host_does(self) -> None:
        state = self.state()
        runtime = Runtime(state)

        for name in (
            "lower", "upper", "evals", "seq_code", "self_lower",
            "lower_op", "child", "named_tail", "compile_node",
        ):
            entity = EntityID(name)

            with self.subTest(function=name):
                body = function_at(state, entity).body

                same(self, run(runtime, LOWER, body), host_chunk(state, entity))

    def test_a_program_compiles_itself_by_reading_its_own_code(self) -> None:
        state = self.state()

        same(
            self,
            run(Runtime(state), self_hosting.SELF_LOWER),
            host_chunk(state, LOWER),
        )

    def test_the_compiler_stays_inside_what_it_covers(self) -> None:
        state = self.state()
        kinds = set()

        for entity, value in state.values.items():
            node = relation_of(value)

            if node is not None:
                kinds.add(node.kind)

        self.assertLessEqual(
            kinds - {"definition", "links"},
            self_hosting.LOWERED | {"definition"},
        )


class InstrumentTests(unittest.TestCase):
    def test_the_chunk_it_returns_is_the_hosts_chunk_of_what_it_installed(self) -> None:
        example = next(e for e in self_hosting.EXAMPLES if e.name == "instrument")
        runtime = Runtime(load(example.program))

        returned = run(runtime, EntityID("instrument"), may_activate=True)
        state = runtime.active.state

        same(self, returned, host_chunk(state, EntityID("work")))
        self.assertEqual(run(runtime, EntityID("work"), 3), 4)
        self.assertEqual(runtime.read(EntityID("hits")), 1)

    def test_the_swap_changes_work_and_its_nodes_only(self) -> None:
        example = next(e for e in self_hosting.EXAMPLES if e.name == "instrument")
        state = load(example.program)
        runtime = Runtime(state)

        run(runtime, EntityID("instrument"), may_activate=True)

        after = runtime.active.state
        untouched = [
            entity for entity in state.values
            if entity not in state.owned_subtree(EntityID("work"))
            and entity != EntityID("work")
        ]

        for entity in untouched:
            with self.subTest(entity=entity.value):
                self.assertEqual(
                    after.values[entity].version_id,
                    state.values[entity].version_id,
                )


class Generator:
    """Seeded random expressions over what the compiler covers."""

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.labels = 0
        self.names = 0

    def leaf(self) -> tuple:
        return self.rng.choice([
            ("lit", self.rng.choice([0, 1, 7, "s", (), (1, 2), None, True])),
            ("arg", "x"),
            ("read", "c"),
            ("ref", "f"),
            ("code", "f"),
            ("linksof", "f"),
        ])

    def expression(self, depth: int) -> tuple:
        rng = self.rng

        if depth == 0:
            return self.leaf()

        sub = lambda: self.expression(depth - 1)
        kind = rng.choice([
            "add", "sub", "mul", "lt", "eq", "if", "seq", "call", "tuple",
            "len", "item", "slice", "concat", "let", "apply", "applyv", "write",
            "label", "leaf",
        ])

        if kind in ("add", "sub", "mul", "lt", "eq"):
            return (kind, sub(), sub())
        if kind == "if":
            return ("if", sub(), sub(), sub())
        if kind in ("seq", "tuple"):
            return (kind, *(sub() for _ in range(rng.randint(0, 3))))
        if kind == "call":
            return ("call", "f", *(sub() for _ in range(rng.randint(0, 3))))
        if kind in ("len",):
            return (kind, sub())
        if kind == "item":
            return ("item", sub(), sub())
        if kind == "slice":
            return ("slice", sub(), sub(), sub())
        if kind == "concat":
            return ("concat", sub(), sub())
        if kind == "let":
            self.names += 1
            return ("let", f"v{self.names}", sub(), sub())
        if kind == "apply":
            return ("apply", sub(), *(sub() for _ in range(rng.randint(0, 2))))
        if kind == "applyv":
            return ("applyv", sub(), sub())
        if kind == "write":
            return ("write", "c", sub())
        if kind == "label":
            self.labels += 1
            return ("label", f"l{self.labels}", sub())

        return self.leaf()


if __name__ == "__main__":
    unittest.main()
