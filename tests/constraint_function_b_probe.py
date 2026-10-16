"""Task 24 candidate B: bounded ordinary-function capability probes.

These probes test real SHEAR execution, not a Python reimplementation
of constraint evaluation. Negative witnesses are expected outcomes.

Run with: python3 -m tests.constraint_function_b_probe
This is an experimental module, not a Plan-owned acceptance test.
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
        """The VM can interpret ordinary tuple-form data."""
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

    def test_canonical_constraints_cannot_be_projected(self) -> None:
        """The existing tuple operation cannot inspect constraint data."""
        runtime = ordinary_runtime(
            ("constraint",),
            element(argument("constraint"), 2),
        )

        constraints = (
            IsKind("int"),
            IntRange(0, 10),
            Length(0, 10),
            OneOf(1, 2),
            Role("item", IsKind("int")),
            AllOf(IsKind("int"), IntRange(0, 10)),
        )

        with patch.object(
            Constraint,
            "evaluate",
            side_effect=AssertionError("incumbent fallback"),
        ):
            for constraint in constraints:
                with self.subTest(kind=type(constraint).__name__):
                    self.assert_wrong_kind(runtime, constraint)

    def test_canonical_maps_cannot_be_projected(self) -> None:
        """Role lookup lacks an ordinary map-content operation."""
        runtime = ordinary_runtime(
            ("subject",),
            element(argument("subject"), 0),
        )
        self.assert_wrong_kind(runtime, {"item": 7})

        # Ordinary tuples remain inspectable.
        self.assertEqual(run(runtime, ENTRY, (7,)), 7)

    def test_length_is_not_generic_canonical_length(self) -> None:
        """The current len operation handles tuples, not all Length kinds."""
        runtime = ordinary_runtime(
            ("subject",),
            ("len", argument("subject")),
        )

        self.assertEqual(run(runtime, ENTRY, (1, 2)), 2)

        for subject in (
            "ab",
            b"ab",
            [1, 2],
            {"item": 1},
        ):
            with self.subTest(subject=subject):
                self.assert_wrong_kind(runtime, subject)

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
