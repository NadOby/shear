"""Regression tests for Task 24 candidate boundary acceptance.

These tests validate the Plan-owned grader with test doubles.
They are not evidence that an experimental candidate passes.
"""

from __future__ import annotations

from dataclasses import fields, replace
import unittest

from shear import EntityID, canonicalize
from tests.constraint_function_boundary_acceptance import (
    BOUNDARY_CASES,
    BoundaryCase,
    BoundaryExpected,
    BoundaryInput,
    BoundaryObservation,
    assess_boundaries,
)
from tests.constraint_function_oracle import BOUNDARIES


def observation(expected: BoundaryExpected) -> BoundaryObservation:
    """Construct a test double from expected values.

    This helper is used only to test the grader, never by a
    candidate adapter or an experimental implementation.
    """
    values = {
        field.name: getattr(expected, field.name)
        for field in fields(BoundaryExpected)
    }
    return BoundaryObservation(
        **values,
        route="interpreted",
        incumbent_calls=0,
    )


def case_named(name: str) -> BoundaryCase:
    return next(
        case for case in BOUNDARY_CASES
        if case.name == name
    )


class BoundaryInventoryTests(unittest.TestCase):
    def test_every_registered_witness_has_a_script(self) -> None:
        self.assertEqual(
            tuple(case.name for case in BOUNDARY_CASES),
            tuple(witness.name for witness in BOUNDARIES),
        )
        self.assertEqual(len(BOUNDARY_CASES), 14)
        self.assertEqual(
            len({case.name for case in BOUNDARY_CASES}),
            len(BOUNDARY_CASES),
        )

    def test_scripts_are_nonempty_and_structured(self) -> None:
        for case in BOUNDARY_CASES:
            with self.subTest(case=case.name):
                self.assertIsInstance(case.input, BoundaryInput)
                self.assertTrue(case.input.script)
                self.assertTrue(
                    all(
                        isinstance(step, tuple) and step
                        for step in case.input.script
                    )
                )
                self.assertIsInstance(
                    case.expected, BoundaryExpected
                )

    def test_adapter_input_has_no_expected_metadata(self) -> None:
        self.assertEqual(
            tuple(field.name for field in fields(BoundaryInput)),
            ("script",),
        )

        seen = []

        def candidate(inputs: BoundaryInput) -> BoundaryObservation:
            self.assertIsInstance(inputs, BoundaryInput)
            self.assertNotIsInstance(inputs, BoundaryCase)

            for name in ("expected", "name", "status", "seed"):
                self.assertFalse(hasattr(inputs, name))

            seen.append(inputs.script)
            return observation(BOUNDARY_CASES[0].expected)

        report = assess_boundaries(
            "test-double",
            candidate,
            (BOUNDARY_CASES[0],),
        )

        self.assertEqual(report.checked, 1)
        self.assertEqual(report.failures, ())
        self.assertFalse(report.complete_contract)
        self.assertEqual(seen, [BOUNDARY_CASES[0].input.script])

    def test_frozen_rejection_outcomes(self) -> None:
        for name, status in (
            ("load_unknown", "cell_rejected"),
            ("write_unknown", "cell_rejected"),
            ("relation_unknown", "relation_rejected"),
            ("activation_unknown", "activation_rejected"),
            ("trial_unknown", "activation_rejected"),
        ):
            with self.subTest(name=name):
                expected = case_named(name).expected
                self.assertEqual(expected.status, status)
                self.assertEqual(expected.results, ("unknown",))
                self.assertIs(expected.state_unchanged, True)

    def test_frozen_host_and_effect_boundaries(self) -> None:
        host = case_named("external_under_catch").expected
        self.assertEqual(host.status, "host_failure")
        self.assertIs(host.caught, False)
        self.assertIs(host.state_unchanged, True)

        effect = case_named("candidate_effect").expected
        self.assertEqual(effect.status, "effect_rejected")
        self.assertEqual(effect.effect_count, 0)
        self.assertIs(effect.state_unchanged, True)

        version = case_named("candidate_version").expected
        self.assertIs(version.identity_preserved, True)
        self.assertEqual(
            version.results,
            ("satisfied", "satisfied"),
        )

    def test_owned_subtree_matches_reference_canonical_form(
        self,
    ) -> None:
        case = case_named("owned_subtree")
        raw_subject = {
            "root": {
                "value": 1,
                "owned": {EntityID("child"): 2},
            },
        }
        actual = canonicalize(raw_subject)

        self.assertEqual(
            tuple(actual)[:2],
            ("__type__", "map"),
        )

        report = assess_boundaries(
            "canonical-control",
            lambda _: replace(
                observation(case.expected),
                observed_subject=actual,
            ),
            (case,),
        )

        self.assertEqual(report.failures, ())

    def test_owned_subtree_rejects_malformed_canonical_subjects(
        self,
    ) -> None:
        case = case_named("owned_subtree")
        frozen = case.expected.observed_subject
        nested_entries = frozen[2][0][1][2]

        reversed_entries = (
            "__type__", "map", (
                (
                    "root",
                    ("__type__", "map", nested_entries[::-1]),
                ),
            ),
        )

        malformed = {
            "untagged": {
                "root": {
                    "value": 1,
                    "owned": {EntityID("child"): 2},
                },
            },
            "reordered": reversed_entries,
            "bool_instead_of_int": canonicalize({
                "root": {
                    "value": True,
                    "owned": {EntityID("child"): 2},
                },
            }),
            "string_instead_of_entity_id": canonicalize({
                "root": {
                    "value": 1,
                    "owned": {"child": 2},
                },
            }),
        }

        for name, subject in malformed.items():
            with self.subTest(name=name):
                report = assess_boundaries(
                    "canonical-negative-control",
                    lambda _: replace(
                        observation(case.expected),
                        observed_subject=subject,
                    ),
                    (case,),
                )
                self.assertIn(
                    "observed_subject",
                    [failure.field for failure in report.failures],
                )

    def test_scripts_are_detached_from_the_frozen_cases(
        self,
    ) -> None:
        mutable = {"values": [1]}
        case = BoundaryCase(
            "mutation-isolation",
            BoundaryInput((("probe", mutable),)),
            BoundaryExpected("completed"),
        )

        def candidate(inputs: BoundaryInput) -> BoundaryObservation:
            inputs.script[0][1]["values"].append(2)
            return observation(case.expected)

        report = assess_boundaries("test-double", candidate, (case,))

        self.assertEqual(report.failures, ())
        self.assertFalse(report.passed)
        self.assertEqual(mutable, {"values": [1]})
        self.assertEqual(
            case.input.script[0][1],
            {"values": [1]},
        )


class BoundaryGraderTests(unittest.TestCase):
    def test_entire_contract_can_pass(self) -> None:
        expected = iter(
            case.expected for case in BOUNDARY_CASES
        )
        seen = []

        def candidate(inputs: BoundaryInput) -> BoundaryObservation:
            seen.append(inputs.script)
            return observation(next(expected))

        report = assess_boundaries("test-double", candidate)

        self.assertTrue(report.passed)
        self.assertTrue(report.complete_contract)
        self.assertEqual(report.checked, len(BOUNDARY_CASES))
        self.assertEqual(report.failures, ())
        self.assertEqual(
            seen,
            [case.input.script for case in BOUNDARY_CASES],
        )

    def test_partial_contract_is_not_a_full_pass(self) -> None:
        case = BOUNDARY_CASES[0]
        report = assess_boundaries(
            "test-double",
            lambda _: observation(case.expected),
            (case,),
        )

        self.assertEqual(report.checked, 1)
        self.assertEqual(report.failures, ())
        self.assertFalse(report.complete_contract)
        self.assertFalse(report.passed)

    def test_empty_contract_cannot_pass(self) -> None:
        report = assess_boundaries(
            "test-double",
            lambda _: None,
            (),
        )

        self.assertEqual(report.checked, 0)
        self.assertFalse(report.complete_contract)
        self.assertFalse(report.passed)

    def test_duplicate_cases_cannot_qualify(self) -> None:
        first = BOUNDARY_CASES[0]
        duplicates = (first,) * len(BOUNDARY_CASES)

        report = assess_boundaries(
            "test-double",
            lambda _: observation(first.expected),
            duplicates,
        )

        self.assertEqual(report.checked, len(BOUNDARY_CASES))
        self.assertEqual(report.failures, ())
        self.assertFalse(report.complete_contract)
        self.assertFalse(report.passed)

    def test_reordered_cases_cannot_qualify(self) -> None:
        reordered = BOUNDARY_CASES[::-1]
        expected = iter(case.expected for case in reordered)

        report = assess_boundaries(
            "test-double",
            lambda _: observation(next(expected)),
            reordered,
        )

        self.assertEqual(report.checked, len(BOUNDARY_CASES))
        self.assertEqual(report.failures, ())
        self.assertFalse(report.complete_contract)
        self.assertFalse(report.passed)

    def test_modified_scripts_cannot_qualify(self) -> None:
        first = BOUNDARY_CASES[0]
        changed = replace(
            first,
            input=BoundaryInput(
                first.input.script + (("extra_step",),)
            ),
        )
        selected = (changed,) + BOUNDARY_CASES[1:]
        expected = iter(case.expected for case in selected)

        report = assess_boundaries(
            "test-double",
            lambda _: observation(next(expected)),
            selected,
        )

        self.assertEqual(report.checked, len(BOUNDARY_CASES))
        self.assertEqual(report.failures, ())
        self.assertFalse(report.complete_contract)
        self.assertFalse(report.passed)

    def test_modified_expectations_cannot_qualify(self) -> None:
        first = BOUNDARY_CASES[0]
        changed = replace(
            first,
            expected=replace(first.expected, status="completed"),
        )
        selected = (changed,) + BOUNDARY_CASES[1:]
        expected = iter(case.expected for case in selected)

        report = assess_boundaries(
            "test-double",
            lambda _: observation(next(expected)),
            selected,
        )

        self.assertEqual(report.checked, len(BOUNDARY_CASES))
        self.assertEqual(report.failures, ())
        self.assertFalse(report.complete_contract)
        self.assertFalse(report.passed)

    def test_modified_names_cannot_qualify(self) -> None:
        first = BOUNDARY_CASES[0]
        changed = replace(first, name="renamed")
        selected = (changed,) + BOUNDARY_CASES[1:]
        expected = iter(case.expected for case in selected)

        report = assess_boundaries(
            "test-double",
            lambda _: observation(next(expected)),
            selected,
        )

        self.assertEqual(report.failures, ())
        self.assertFalse(report.complete_contract)
        self.assertFalse(report.passed)

    def test_every_expected_field_is_checked(self) -> None:
        case = BOUNDARY_CASES[0]
        baseline = observation(case.expected)
        wrong_values = {
            "status": "completed",
            "results": ("unexpected",),
            "state_unchanged": False,
            "caught": False,
            "effect_count": 1,
            "observed_subject": ("unexpected",),
            "identity_preserved": False,
        }

        for field, wrong in wrong_values.items():
            with self.subTest(field=field):
                candidate_result = replace(
                    baseline, **{field: wrong}
                )
                report = assess_boundaries(
                    "test-double",
                    lambda _: candidate_result,
                    (case,),
                )

                self.assertIn(
                    field,
                    [failure.field for failure in report.failures],
                )

    def test_wrong_execution_route_is_rejected(self) -> None:
        case = BOUNDARY_CASES[0]

        for route in ("", "python-fallback", "dedicated-evaluator"):
            with self.subTest(route=route):
                candidate_result = replace(
                    observation(case.expected),
                    route=route,
                )
                report = assess_boundaries(
                    "test-double",
                    lambda _: candidate_result,
                    (case,),
                )
                self.assertIn(
                    "route",
                    [failure.field for failure in report.failures],
                )

    def test_reported_incumbent_fallback_is_rejected(self) -> None:
        case = BOUNDARY_CASES[0]

        for count in (1, -1, True, 0.0, None):
            with self.subTest(count=count):
                candidate_result = replace(
                    observation(case.expected),
                    incumbent_calls=count,
                )
                report = assess_boundaries(
                    "test-double",
                    lambda _: candidate_result,
                    (case,),
                )
                self.assertIn(
                    "incumbent_calls",
                    [failure.field for failure in report.failures],
                )

    def test_effect_count_is_not_boolean(self) -> None:
        case = case_named("candidate_effect")
        candidate_result = replace(
            observation(case.expected),
            effect_count=False,
        )

        report = assess_boundaries(
            "test-double",
            lambda _: candidate_result,
            (case,),
        )

        self.assertIn(
            "effect_count",
            [failure.field for failure in report.failures],
        )

    def test_candidate_exception_does_not_skip_later_cases(
        self,
    ) -> None:
        selected = BOUNDARY_CASES[:2]
        seen = []

        def candidate(inputs: BoundaryInput) -> BoundaryObservation:
            seen.append(inputs.script)
            if len(seen) == 1:
                raise RuntimeError("candidate failed")
            return observation(selected[1].expected)

        report = assess_boundaries(
            "test-double",
            candidate,
            selected,
        )

        self.assertEqual(report.checked, 2)
        self.assertEqual(
            seen,
            [case.input.script for case in selected],
        )
        self.assertEqual(len(report.failures), 1)
        self.assertEqual(
            report.failures[0].name,
            selected[0].name,
        )
        self.assertEqual(
            report.failures[0].field,
            "execution",
        )

    def test_unsupported_script_fails(self) -> None:
        case = BOUNDARY_CASES[0]
        report = assess_boundaries(
            "test-double",
            lambda _: None,
            (case,),
        )

        self.assertFalse(report.passed)
        self.assertEqual(report.failures[0].field, "observation")

    def test_missing_semantic_outcome_fails(self) -> None:
        case = case_named("missing_external")
        candidate_result = replace(
            observation(case.expected),
            results=(),
        )

        report = assess_boundaries(
            "test-double",
            lambda _: candidate_result,
            (case,),
        )

        self.assertIn(
            "results",
            [failure.field for failure in report.failures],
        )

    def test_candidate_name_is_required(self) -> None:
        with self.assertRaises(ValueError):
            assess_boundaries(
                "",
                lambda _: None,
            )


if __name__ == "__main__":
    unittest.main()
