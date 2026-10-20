"""Frozen T6 runtime integration acceptance for SHEAR #123.

The candidate supplies boundary(BoundaryInput) -> BoundaryObservation.

New script operations:
- rename_continuity(old, new): explicitly map old to new, then
  activate the transformed state through the actual runtime.
- assert_entity_absent(name): inspect the live active state.
- assert_relation_role(relation, role, target): inspect the live
  relation's actual endpoint, not an adapter-side name table.

Assertion operations produce no semantic result entries.
All operations must use real SHEAR runtime/state facilities.
The existing 17 Task 24 boundary cases remain unchanged.
This module is outside ordinary Plan-time test discovery.
"""

from dataclasses import dataclass, fields
from importlib import import_module
import unittest
from unittest.mock import patch

from shear import Runtime
from tests.constraint_function_acceptance import ROUTES
from tests.constraint_function_boundary_acceptance import (
    BoundaryExpected,
    BoundaryObservation,
    _case,
)
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
)


POLICY = (
    "external", "policy", "role_table",
    (
        ("item", 0, "satisfied"),
        ("item", 7, "satisfied"),
        ("item", 11, "violated"),
    ),
)

GRAPH = (
    ("cell", "c", ("is_kind", "int"), 0),
    ("relation", "r", ("item", "c"),
     ("external", "policy")),
)


@dataclass(frozen=True)
class Scenario:
    case: object
    writes: tuple


SCENARIOS = (
    Scenario(
        _case(
            "relation_initial_success",
            (POLICY, ("load_graph", GRAPH)),
            "completed",
            results=("satisfied",),
        ),
        (),
    ),
    Scenario(
        _case(
            "relation_write_success",
            (
                POLICY, ("load_graph", GRAPH),
                ("write", "c", 7),
            ),
            "completed",
            results=("satisfied",),
            state_unchanged=False,
            live_cells=(("c", 7),),
            active_version_changed=False,
        ),
        (("c", 7),),
    ),
    Scenario(
        _case(
            "relation_write_rejected",
            (
                POLICY, ("load_graph", GRAPH),
                ("write", "c", 11),
            ),
            "relation_rejected",
            results=("violated",),
            state_unchanged=True,
            live_cells=(("c", 0),),
            active_version_changed=False,
        ),
        (("c", 11),),
    ),
    Scenario(
        _case(
            "rename_preserves_relation_endpoint",
            (
                POLICY, ("load_graph", GRAPH),
                ("rename_continuity", "c", "d"),
                ("assert_entity_absent", "c"),
                ("assert_relation_role", "r", "item", "d"),
                ("write", "d", 7),
            ),
            "completed",
            results=("satisfied",),
            live_cells=(("d", 7),),
            active_version_changed=False,
        ),
        (("d", 7),),
    ),
    Scenario(
        _case(
            "renamed_relation_still_rejects",
            (
                POLICY, ("load_graph", GRAPH),
                ("rename_continuity", "c", "d"),
                ("assert_entity_absent", "c"),
                ("assert_relation_role", "r", "item", "d"),
                ("write", "d", 11),
            ),
            "relation_rejected",
            results=("violated",),
            state_unchanged=True,
            live_cells=(("d", 0),),
            active_version_changed=False,
        ),
        (("d", 11),),
    ),
    Scenario(
        _case(
            "failed_activation_retains_live_cells",
            (
                ("load_cell", "c", ("is_kind", "int"), 0),
                ("write", "c", 4),
                ("activate_constraint", "c",
                 ("int_range", 8, 20), "preserve_content"),
            ),
            "activation_rejected",
            results=("violated",),
            state_unchanged=True,
            live_cells=(("c", 4),),
            active_version_changed=False,
        ),
        (("c", 4),),
    ),
    Scenario(
        _case(
            "trial_preserves_unmodified_second_cell",
            (
                ("load_graph", (
                    ("cell", "c", ("is_kind", "int"), 0),
                    ("cell", "d", ("is_kind", "int"), 0),
                )),
                ("write", "c", 4),
                ("write", "d", 3),
                ("trial_constraint", "c",
                 ("int_range", 0, 100), "preserve_content"),
            ),
            "completed",
            results=("satisfied",),
            state_unchanged=True,
            live_cells=(("c", 4), ("d", 3)),
            trial_cells=(("c", 4), ("d", 3)),
            active_version_changed=False,
            trial_version_matches_staged=True,
        ),
        (("c", 4), ("d", 3)),
    ),
)


class FrozenRuntimeAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.adapter = import_module(
                "tests.constraint_functions_complete_candidate"
            )
        cls.entries = cls.adapter.EVALUATOR_ENTRIES
        if not callable(getattr(cls.adapter, "boundary", None)):
            raise AssertionError("candidate lacks boundary")

    def test_t6_runtime_scenarios(self):
        self.assertEqual(len(SCENARIOS), 7)
        self.assertEqual(
            len({item.case.name for item in SCENARIOS}), 7,
        )

        original_write = Runtime.write
        observed_writes = []

        def traced_write(runtime, cell, content):
            observed_writes.append((cell.value, content))
            return original_write(runtime, cell, content)

        for scenario in SCENARIOS:
            with self.subTest(case=scenario.case.name):
                observed_writes.clear()

                with (
                    patch.object(Runtime, "write", new=traced_write),
                    candidate_execution_guard(self.entries) as opened,
                ):
                    actual = self.adapter.boundary(
                        scenario.case.input
                    )

                self.assertTrue(
                    opened,
                    "runtime admission bypassed admitted SHEAR",
                )
                self.assertIsInstance(actual, BoundaryObservation)
                self.assertIn(actual.route, ROUTES)
                self.assertEqual(actual.incumbent_calls, 0)

                for field in fields(BoundaryExpected):
                    expected = getattr(
                        scenario.case.expected, field.name,
                    )
                    observed = getattr(actual, field.name)
                    self.assertIs(
                        type(observed), type(expected),
                        field.name,
                    )
                    self.assertEqual(
                        observed, expected,
                        f"{scenario.case.name}: {field.name}",
                    )

                self.assertEqual(
                    observed_writes, list(scenario.writes),
                    f"{scenario.case.name}: public runtime writes",
                )


if __name__ == "__main__":
    unittest.main()
