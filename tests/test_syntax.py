"""Acceptance tests for text syntax version 0 (docs/syntax.md)."""

import dataclasses
import unittest

from shear import EntityID, Runtime, canonical_serialize, canonicalize, transform_with_mapping
from shear.constraints import IsKind
from shear.examples import EXAMPLES, play
from shear.lang import load, run
from shear.syntax import SourceError, parse, render, render_program

COUNTER_TEXT = """\
cell counter: int in 0..100 = 0

fn increment():
    counter = counter + 1

fn double(x):
    x + x

fn quad(x):
    double(double(x))
"""


def same(a: object, b: object) -> bool:
    return canonical_serialize(canonicalize(a)) == canonical_serialize(canonicalize(b))


def runtime(text: str) -> Runtime:
    return Runtime(load(parse(text)))


class ParseTests(unittest.TestCase):
    def test_parse_and_run(self) -> None:
        rt = runtime(COUNTER_TEXT)

        self.assertEqual(run(rt, EntityID("increment")), 1)
        self.assertEqual(rt.read(EntityID("counter")), 1)
        self.assertEqual(run(rt, EntityID("quad"), 3), 12)

    def test_blocks_let_and_if(self) -> None:
        rt = runtime("""\
fn fib(n):
    if n < 2:
        n
    else:
        let a = fib(n - 1)
        let b = fib(n - 2)
        a + b
""")

        self.assertEqual(run(rt, EntityID("fib"), 10), 55)

    def test_data_and_higher_order(self) -> None:
        rt = runtime("""\
fn twice(f, x):
    f(f(x))

fn inc(x):
    x + 1

fn main():
    let t = (1, 2, 3)
    (len(t), item(t, 0), slice(t, 1, 3), concat(t, (4,)), twice(ref(inc), 5), apply(ref(inc), (9,)))
""")

        self.assertTrue(same(
            run(rt, EntityID("main")),
            (3, 1, (2, 3), (1, 2, 3, 4), 7, 10),
        ))

    def test_semantic_inspection_and_record_construction(self) -> None:
        source = """\
fn kind_of(x):
    item(inspect(x), 0)

fn int_constraint():
    record("constraint", ("is_kind", ("int",)))
"""
        state = load(parse(source))
        rt = Runtime(state)

        self.assertEqual(run(rt, EntityID("kind_of"), 7), "int")
        self.assertTrue(same(
            run(rt, EntityID("int_constraint")),
            IsKind("int").canonical_node(),
        ))

        text = render_program(state)
        self.assertIn("item(inspect(x), 0)", text)
        self.assertIn(
            'record("constraint", ("is_kind", ("int",)))',
            text,
        )
        self.assertEqual(render_program(load(parse(text))), text)

    def test_semantic_operation_syntax_errors(self) -> None:
        for source, line in (
            ("fn inspect(x):\n    x\n", 1),
            ("fn record(x):\n    x\n", 1),
            ("fn f(x):\n    inspect()\n", 2),
            ("fn f(x):\n    inspect(x, x)\n", 2),
            ("fn f(x):\n    record(x)\n", 2),
            ("fn f(x):\n    record(x, x, x)\n", 2),
        ):
            with self.subTest(source=source):
                with self.assertRaises(SourceError) as caught:
                    parse(source)

                self.assertEqual(caught.exception.line, line)

    def test_self_modification_in_text(self) -> None:
        rt = runtime("""\
fn emit(n):
    if n == 0:
        quote(1)
    else:
        quote(x * unquote(emit(n - 1)))

fn power(x):
    1

fn compile(n):
    activate(power = function(("x",), emit(n)))

fn tune(k):
    activate(power = fn(x): x * literal(k))
""")

        run(rt, EntityID("compile"), 3, may_activate=True)
        self.assertEqual(run(rt, EntityID("power"), 2), 8)
        run(rt, EntityID("tune"), 5, may_activate=True)
        self.assertEqual(run(rt, EntityID("power"), 3), 15)

    def test_labels_node_edits_and_trials(self) -> None:
        rt = runtime(COUNTER_TEXT + """
fn stepped():
    counter = counter + label(step, 1)

fn patch(k):
    activate(stepped.step = quote(literal(k)))

fn try_triple():
    trial(quad(3), double = fn(x): x * 3)
""")
        state = rt.active.state

        self.assertEqual(run(rt, EntityID("try_triple"), may_activate=True), 27)
        self.assertEqual(rt.active.id, state.id)

        run(rt, EntityID("patch"), 5, may_activate=True)
        self.assertEqual(run(rt, EntityID("stepped")), 5)

    def test_source_errors_name_the_line(self) -> None:
        for text, line in (
            ("fn f():\n    y\n", 2),  # unknown name
            ("fn f(x):\n    x = 1\n", 2),  # assignment to a parameter
            ("fn f():\n    let y = 1\n", 2),  # let with nothing after it
            ("fn len(x):\n    x\n", 1),  # reserved name
            ("fn f():\n\t1\n", 2),  # tab indentation
            ("cell c: int = 0\nfn f():\n    c(1)\n", 3),  # calling a cell
            ("fn f(x):\n    unquote(x)\n", 2),  # unquote outside a quote
            ("fn f():\n    1 < 2 < 3\n", 2),  # chained comparison
        ):
            with self.subTest(text=text):
                with self.assertRaises(SourceError) as caught:
                    parse(text)

                self.assertIsInstance(caught.exception, ValueError)
                self.assertEqual(caught.exception.line, line)


class RenderTests(unittest.TestCase):
    def test_render_prints_the_source_view(self) -> None:
        state = load(parse(COUNTER_TEXT))

        self.assertEqual(render(state, EntityID("quad")), "fn quad(x):\n    double(double(x))\n")
        self.assertEqual(
            render(state, EntityID("increment")),
            "fn increment():\n    counter = counter + 1\n",
        )

    def test_render_shows_renames(self) -> None:
        state = load(parse(COUNTER_TEXT))
        double, twice = EntityID("double"), EntityID("twice")
        renamed = transform_with_mapping(
            state,
            {twice: state.values[double].content},
            {**{e: e for e in state.values if e != double}, double: twice},
        ).destination

        self.assertEqual(render(renamed, EntityID("quad")), "fn quad(x):\n    twice(twice(x))\n")

    def test_program_text_is_a_fixpoint(self) -> None:
        text = render_program(load(parse(COUNTER_TEXT)))

        self.assertEqual(render_program(load(parse(text))), text)


class CorpusRoundTripTests(unittest.TestCase):
    def test_every_example_round_trips_through_text(self) -> None:
        for example in EXAMPLES:
            with self.subTest(example=example.name):
                text = render_program(load(example.program))
                program = parse(text, base=example.program)

                play(dataclasses.replace(example, program=program), run)
                self.assertEqual(render_program(load(program)), text)

                if "self-modification" not in example.tags:
                    self.assertNotIn("raw(", text)


if __name__ == "__main__":
    unittest.main()
