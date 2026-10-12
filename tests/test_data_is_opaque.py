"""Program data is opaque to the model (issue #111).

A value a program holds as data comes back unchanged, whatever its kind:
as a literal, as a quoted template, as an argument, in a cell, inside a
tuple, and as a literal in code the program generates and activates. The
first three are the code nodes whose payload holds program data. Parts of
the model decide what something is from its content (a constraint payload
makes a constraint relation); none of them may read program data that way.
"""

import unittest

from shear import (
    CellDeclaration,
    ConstraintResult,
    EntityID,
    EvaluationContext,
    Evaluator,
    External,
    IsKind,
    Relation,
    Runtime,
    State,
    StateID,
    Value,
    VersionID,
    canonical_serialize,
    canonicalize,
)
from shear.closures import Closure
from shear.constraints import KINDS, kind_of
from shear.lang import Function, LanguageError, links, load, run

F, G, CELL = EntityID("f"), EntityID("g"), EntityID("cell")

# One value of every kind content can have. ``function`` is the kind of a
# Function value, which IsKind does not name (metaprogramming.md §3).
EXEMPLARS = {
    "none": None,
    "bool": True,
    "int": 5,
    "str": "s",
    "bytes": b"\x00",
    "entity_id": EntityID("elsewhere"),
    "version_id": VersionID("v"),
    "state_id": StateID("s"),
    "tuple": (1, "a"),
    "list": [1, 2],
    "map": {"a": 1},
    "cell": CellDeclaration(IsKind("int"), 1),
    "constraint": IsKind("int"),
    "relation": Relation("bound", {}, IsKind("int")),
    "closure": Closure(EntityID("o"), EntityID("b"), ("x",), ()),
    "function": Function(("x",), ("arg", "x")),
}

ANYTHING = EvaluationContext({
    "anything": Evaluator(lambda subject: ConstraintResult.SATISFIED),
})


def program(params, body):
    return State.create({
        F: Value.create(F, Function(params, body)),
        G: Value.create(G, Function((), ("lit", None))),
        CELL: Value.create(CELL, CellDeclaration(External("anything"), None)),
        EntityID("f.links"): Value.create(
            EntityID("f.links"),
            links(F, g=G, cell=CELL),
        ),
    })


def literal(value):
    return run(Runtime(load(program((), ("lit", value))), ANYTHING), F)


def quoted(value):
    return run(Runtime(load(program((), ("quote", value))), ANYTHING), F)


def argument(value):
    state = load(program(("x",), ("arg", "x")))
    return run(Runtime(state, ANYTHING), F, value)


def in_a_cell(value):
    body = ("seq", ("write", "cell", ("arg", "x")), ("read", "cell"))
    return run(Runtime(load(program(("x",), body)), ANYTHING), F, value)


def in_a_tuple(value):
    body = ("item", ("tuple", ("arg", "x")), ("lit", 0))
    return run(Runtime(load(program(("x",), body)), ANYTHING), F, value)


def in_activated_code(value):
    generated = ("function", ("lit", ()), ("quote", ("lit", value)))
    body = ("activate", "g", generated)
    runtime = Runtime(load(program((), body)), ANYTHING)
    run(runtime, F, may_activate=True)
    return run(runtime, G)


ROUTES = {
    "literal": literal,
    "quoted": quoted,
    "argument": argument,
    "in a cell": in_a_cell,
    "in a tuple": in_a_tuple,
    "in activated code": in_activated_code,
}


def same(left, right) -> bool:
    return canonical_serialize(canonicalize(left)) == canonical_serialize(
        canonicalize(right)
    )


class ExemplarTests(unittest.TestCase):
    def test_every_kind_of_content_has_an_exemplar(self):
        self.assertEqual(set(EXEMPLARS), KINDS | {"function"})

        for kind, value in EXEMPLARS.items():
            with self.subTest(kind=kind):
                self.assertEqual(kind_of(value), kind)


class OpaqueDataTests(unittest.TestCase):
    def test_every_kind_comes_back_unchanged_by_every_route(self):
        for kind, value in EXEMPLARS.items():
            for route, through in ROUTES.items():
                with self.subTest(kind=kind, route=route):
                    self.assertTrue(same(through(value), value))

    def test_a_constraint_named_as_a_parameter_fails_when_it_runs(self):
        # Like any other name that is not a parameter: checked when it runs,
        # not when the program loads (metaprogramming.md §3).
        runtime = Runtime(load(program((), ("arg", IsKind("int")))), ANYTHING)

        with self.assertRaises(LanguageError):
            run(runtime, F)


if __name__ == "__main__":
    unittest.main()
