"""Task 24 candidate B: ordinary-function capability probes.

The original bounded experiment demonstrated that canonical records, maps,
and non-tuple sequences could not be inspected through ordinary functions.

GH-123 introduces the approved generic semantic inspection operations.
These tests now verify the newly available capabilities using real SHEAR
execution, without an incumbent constraint-evaluation fallback.

The historical negative findings remain in the Task 24 documentation and
repository history; they are not claims about the current implementation.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from shear import (
    AllOf,
    Constraint,
    EntityID,
    IntRange,
    IsKind,
    Length,
    OneOf,
    Role,
    Runtime,
    State,
    Value,
)
from shear.lang import Function, LanguageError, load, run


ENTRY = EntityID("task24.b.probe")


def ordinary_runtime(params: tuple[str, ...], body: tuple) -> Runtime:
    """Load a genuine SHEAR function with no effectful links."""
    state = State.create({
        ENTRY: Value.create(ENTRY, Function(params, body)),
    })
    return Runtime(load(state))


def argument(name: str) -> tuple:
    return ("arg", name)


def literal(value: object) -> tuple:
    return ("lit", value)


def element(value: tuple, index: int) -> tuple:
    return ("item", value, literal(index))


class CandidateBCapabilityTests(unittest.TestCase):
    def assert_wrong_kind(self, runtime: Runtime, *args: object) -> None:
        with self.assertRaises(LanguageError) as caught:
            run(runtime, ENTRY, *args)

        self.assertEqual(caught.exception.error[0], "language")
        self.assertEqual(caught.exception.error[1], "wrong_kind")

    def test_ordinary_tuple_interpretation_works(self) -> None:
        program = argument("program")
        subject = argument("subject")

        body = (
            "if",
            ("eq", element(program, 0), literal("equals")),
            (
                "if",
                ("eq", subject, element(program, 1)),
                literal("satisfied"),
                literal("violated"),
            ),
            literal("unsupported"),
        )
        runtime = ordinary_runtime(("program", "subject"), body)
        before = runtime.active.state.id

        with patch.object(
            Constraint,
            "evaluate",
            side_effect=AssertionError("incumbent fallback"),
        ):
            self.assertEqual(
                run(runtime, ENTRY, ("equals", 7), 7),
                "satisfied",
            )
            self.assertEqual(
                run(runtime, ENTRY, ("equals", 7), 8),
                "violated",
            )

        self.assertEqual(runtime.active.state.id, before)
        self.assertEqual(runtime.active.holds, frozenset())

    def test_canonical_constraints_expose_public_fields(self) -> None:
        constraint = argument("constraint")
        form = ("item", constraint, literal("form"))
        arguments = ("item", constraint, literal("arguments"))

        runtime = ordinary_runtime(
            ("constraint",),
            (
                "tuple",
                element(("inspect", constraint), 0),
                ("len", constraint),
                element(constraint, 0),
                form,
                ("len", arguments),
            ),
        )

        cases = (
            (IsKind("int"), "is_kind", 1),
            (IntRange(0, 10), "int_range", 2),
            (Length(0, 10), "length", 2),
            (OneOf(1, 2), "one_of", 1),
            (Role("item", IsKind("int")), "role", 2),
            (
                AllOf(IsKind("int"), IntRange(0, 10)),
                "all_of",
                1,
            ),
        )

        before = runtime.active.state.id

        with patch.object(
            Constraint,
            "evaluate",
            side_effect=AssertionError("incumbent fallback"),
        ):
            for value, name, arity in cases:
                with self.subTest(kind=type(value).__name__):
                    self.assertEqual(
                        run(runtime, ENTRY, value),
                        (
                            "constraint",
                            2,
                            ("form", name),
                            name,
                            arity,
                        ),
                    )

        self.assertEqual(runtime.active.state.id, before)
        self.assertEqual(runtime.active.holds, frozenset())

    def test_record_access_rejects_unknown_fields(self) -> None:
        runtime = ordinary_runtime(
            ("constraint",),
            ("item", argument("constraint"), literal("missing")),
        )

        with self.assertRaises(LanguageError) as caught:
            run(runtime, ENTRY, IsKind("int"))

        self.assertEqual(caught.exception.error[0], "language")
        self.assertEqual(caught.exception.error[1], "out_of_range")
        self.assertIn(
            ("field", "missing"),
            caught.exception.error[2],
        )

    def test_canonical_maps_are_positionally_inspectable(self) -> None:
        subject = argument("subject")
        runtime = ordinary_runtime(
            ("subject",),
            (
                "tuple",
                element(("inspect", subject), 0),
                ("len", subject),
                element(subject, 0),
                element(subject, 1),
            ),
        )

        for mapping in (
            {"b": 2, "a": 1},
            {"a": 1, "b": 2},
        ):
            with self.subTest(mapping=mapping):
                self.assertEqual(
                    run(runtime, ENTRY, mapping),
                    (
                        "map",
                        2,
                        ("a", 1),
                        ("b", 2),
                    ),
                )

        named_lookup = ordinary_runtime(
            ("subject",),
            ("item", argument("subject"), literal("a")),
        )
        self.assert_wrong_kind(named_lookup, {"a": 1})

        # Positional map access does not change tuple semantics.
        tuples = ordinary_runtime(
            ("subject",),
            element(argument("subject"), 0),
        )
        self.assertEqual(run(tuples, ENTRY, (7,)), 7)

    def test_length_is_generic_semantic_length(self) -> None:
        runtime = ordinary_runtime(
            ("subject",),
            ("len", argument("subject")),
        )

        cases = (
            ((1, 2), 2),
            ("ab", 2),
            ("e\u0301", 2),
            (b"ab", 2),
            ([1, 2], 2),
            ({"item": 1}, 1),
        )

        for subject, expected in cases:
            with self.subTest(subject=subject):
                self.assertEqual(
                    run(runtime, ENTRY, subject),
                    expected,
                )

        self.assert_wrong_kind(runtime, 7)

    def test_probes_do_not_change_runtime_versions(self) -> None:
        runtime = ordinary_runtime(
            ("subject",),
            ("eq", argument("subject"), literal(7)),
        )
        version = runtime.active
        state_id = version.state.id

        self.assertTrue(run(runtime, ENTRY, 7))
        self.assertFalse(run(runtime, ENTRY, 8))
        self.assertIs(runtime.active, version)
        self.assertEqual(runtime.active.state.id, state_id)
        self.assertEqual(runtime.active.holds, frozenset())


if __name__ == "__main__":
    unittest.main()
