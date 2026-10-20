"""Frozen T7 failure-provenance acceptance for SHEAR #123.

Execute supplies the existing boundary(BoundaryInput) adapter.
The tests independently observe exceptions from actual Runtime
operations, including the rejected entity and semantic result.

The original Task 24 boundary cases are reused unchanged.
This module remains outside ordinary Plan-time CI discovery.
"""

from dataclasses import fields
from functools import wraps
from importlib import import_module
import unittest
from unittest.mock import patch

from shear import (
    ActivationRejected,
    CellContentRejected,
    ConstraintResult,
    EntityID,
    RelationConstraintRejected,
    Runtime,
)
from tests.constraint_function_boundary_acceptance import (
    BOUNDARY_CASES,
    BoundaryExpected,
    BoundaryObservation,
    _case,
)
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
)


FROZEN = {case.name: case for case in BOUNDARY_CASES}

VIOLATED_CELL = _case(
    "write_violated",
    (
        ("load_cell", "c", ("int_range", 0, 10), 0),
        ("write", "c", 11),
    ),
    "cell_rejected",
    results=("violated",),
    state_unchanged=True,
    live_cells=(("c", 0),),
    active_version_changed=False,
)

VIOLATED_RELATION = _case(
    "relation_violated",
    (
        (
            "external", "policy", "role_table",
            (
                ("item", 0, "satisfied"),
                ("item", 11, "violated"),
            ),
        ),
        (
            "load_graph",
            (
                ("cell", "c", ("is_kind", "int"), 0),
                (
                    "relation", "r", ("item", "c"),
                    ("external", "policy"),
                ),
            ),
        ),
        ("write", "c", 11),
    ),
    "relation_rejected",
    results=("violated",),
    state_unchanged=True,
    live_cells=(("c", 0),),
    active_version_changed=False,
)

# name, public runtime operation, error class, entity, verdict
ERROR_WITNESSES = (
    (
        "load_unknown", "__init__",
        CellContentRejected, "c", "unknown",
    ),
    (
        "write_unknown", "write",
        CellContentRejected, "c", "unknown",
    ),
    (
        "relation_unknown", "write",
        RelationConstraintRejected, "r", "unknown",
    ),
    (
        "activation_unknown", "activate",
        ActivationRejected, "c", "unknown",
    ),
    (
        "trial_unknown", "trial",
        ActivationRejected, "c", "unknown",
    ),
    (
        "write_violated", "write",
        CellContentRejected, "c", "violated",
    ),
    (
        "relation_violated", "write",
        RelationConstraintRejected, "r", "violated",
    ),
)

CASES = {
    **FROZEN,
    "write_violated": VIOLATED_CELL,
    "relation_violated": VIOLATED_RELATION,
}


def observe_runtime_errors(methods, errors):
    """Capture exceptions without changing their type or propagation."""
    patches = []

    for method in methods:
        original = getattr(Runtime, method)

        def wrapper(instance, *args, _method=method,
                    _original=original, **kwargs):
            try:
                return _original(instance, *args, **kwargs)
            except BaseException as exc:
                errors.append((_method, exc))
                raise

        patches.append(patch.object(Runtime, method, new=wrapper))

    return patches


class FrozenFailureProvenanceAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.adapter = import_module(
                "tests.constraint_functions_complete_candidate"
            )

        cls.entries = cls.adapter.EVALUATOR_ENTRIES
        if not callable(getattr(cls.adapter, "boundary", None)):
            raise AssertionError("candidate lacks boundary")

    def run_boundary(self, case, methods):
        errors = []
        patches = observe_runtime_errors(methods, errors)

        from contextlib import ExitStack

        with ExitStack() as stack:
            for entry in patches:
                stack.enter_context(entry)

            with candidate_execution_guard(self.entries) as opened:
                observation = self.adapter.boundary(case.input)

        self.assertIsInstance(observation, BoundaryObservation)
        self.assertEqual(observation.incumbent_calls, 0)

        for field in fields(BoundaryExpected):
            expected = getattr(case.expected, field.name)
            actual = getattr(observation, field.name)
            self.assertIs(type(actual), type(expected), field.name)
            self.assertEqual(
                actual, expected, f"{case.name}: {field.name}",
            )

        return errors, opened, observation

    def test_unknown_and_violated_have_distinct_provenance(self):
        self.assertEqual(len(ERROR_WITNESSES), 7)

        for name, method, error_type, entity, verdict in ERROR_WITNESSES:
            with self.subTest(name=name):
                case = CASES[name]
                errors, opened, _ = self.run_boundary(
                    case, (method,),
                )

                matches = [
                    exc for operation, exc in errors
                    if operation == method
                    and type(exc) is error_type
                    and getattr(exc, "result", None)
                    is ConstraintResult(verdict)
                ]
                self.assertTrue(
                    matches,
                    f"{name}: no matching real Runtime failure; "
                    f"observed={errors!r}",
                )

                attribute = (
                    "relation"
                    if error_type is RelationConstraintRejected
                    else "cell"
                )
                self.assertTrue(any(
                    getattr(exc, attribute, None) == EntityID(entity)
                    for exc in matches
                ))

                if name in (
                    "write_unknown", "relation_unknown",
                    "write_violated", "relation_violated",
                ):
                    self.assertTrue(
                        opened,
                        f"{name}: admitted evaluator never executed",
                    )

    def test_host_failure_is_not_a_semantic_verdict(self):
        errors, opened, observation = self.run_boundary(
            FROZEN["external_under_catch"],
            ("write",),
        )

        self.assertTrue(opened)
        self.assertEqual(observation.status, "host_failure")
        self.assertIs(observation.caught, False)

        semantic_errors = (
            CellContentRejected,
            RelationConstraintRejected,
            ActivationRejected,
        )
        self.assertTrue(
            any(
                method == "write"
                and not isinstance(exc, semantic_errors)
                for method, exc in errors
            ),
            "host failure was not observed at Runtime.write",
        )

    def test_machine_limits_are_not_semantic_unknown(self):
        limit = FROZEN["call_depth_limit"]
        errors, opened, observed = self.run_boundary(
            limit, (),
        )
        self.assertEqual(observed.status, "limit")
        self.assertEqual(observed.results, ())

        tail = FROZEN["tail_recursion"]
        _, _, observed = self.run_boundary(tail, ())
        self.assertEqual(observed.status, "completed")
        self.assertEqual(observed.results, ("end",))


if __name__ == "__main__":
    unittest.main()
