"""Frozen T8 corpus acceptance for SHEAR issue #123.

Execute supplies:
    open_corpus_runtime(loaded_state, context) -> Runtime
    run_corpus_step(runtime, entry, *args, may_activate=False)
        -> ordinary SHEAR result

Runtime creation and subsequent admissions must use the candidate
constraint evaluator. Ordinary language execution may use existing
SHEAR machinery; constraint evaluation may not use the incumbent.

The candidate receives no expected step results. The harness owns
all original corpus expectations and independently checks live cells.

This module stays outside ordinary CI discovery until Execute.
"""

from importlib import import_module
import unittest

from shear import canonical_serialize, canonicalize, Runtime
from shear.cells import cells_of
from shear.examples import EXAMPLES, Raises
from shear.lang import load
from shear.relations import constraint_relations
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
)
from tests.lanes import LANES, validate_partition


REQUIRED_REGRESSIONS = frozenset({
    "test_constraints",
    "test_constraint_function_acceptance",
    "test_constraint_function_boundary_acceptance",
    "test_constraint_function_oracle",
    "test_constraint_function_boundaries",
    "test_corpus",
    "test_hosted_corpus",
    "test_restricted_execution",
    "test_restricted_execution_boundaries",
    "test_restricted_execution_lifecycle",
    "test_golden",
})


def encoded(value):
    return canonical_serialize(canonicalize(value))


class CandidateCorpusAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.adapter = import_module(
                "tests.constraint_functions_complete_candidate"
            )

        cls.entries = cls.adapter.EVALUATOR_ENTRIES
        for operation in (
            "open_corpus_runtime", "run_corpus_step",
        ):
            if not callable(getattr(cls.adapter, operation, None)):
                raise AssertionError(
                    f"candidate lacks {operation}"
                )

    def test_complete_existing_example_corpus(self):
        names = tuple(example.name for example in EXAMPLES)
        self.assertGreaterEqual(len(names), 29)
        self.assertEqual(len(names), len(set(names)))

        checked_steps = 0
        constrained_examples = 0

        for example in EXAMPLES:
            with self.subTest(example=example.name):
                state = load(example.program)
                needs_constraints = bool(
                    cells_of(state)
                    or constraint_relations(state)
                )

                for scenario_index, scenario in enumerate(
                    example.scenarios
                ):
                    with self.subTest(scenario=scenario_index):
                        with candidate_execution_guard(
                            self.entries,
                        ) as opened:
                            runtime = self.adapter.open_corpus_runtime(
                                state, example.context
                            )
                            self.assertIsInstance(runtime, Runtime)
                            self.assertEqual(
                                runtime.active.state.id,
                                state.id,
                            )

                            if needs_constraints:
                                self.assertTrue(
                                    opened,
                                    "initial constraint admission "
                                    "did not execute admitted SHEAR",
                                )

                            for step_index, step in enumerate(scenario):
                                with self.subTest(step=step_index):
                                    try:
                                        actual = (
                                            self.adapter.run_corpus_step(
                                                runtime,
                                                step.entry,
                                                *step.args,
                                                may_activate=step.may_activate,
                                            )
                                        )
                                    except Exception as exc:
                                        self.assertIsInstance(
                                            step.expect, Raises,
                                            "unexpected corpus exception: "
                                            f"{type(exc).__name__}: {exc}",
                                        )
                                        self.assertIsInstance(
                                            exc, step.expect.error,
                                        )
                                    else:
                                        self.assertNotIsInstance(
                                            step.expect, Raises,
                                            "expected corpus exception",
                                        )
                                        self.assertEqual(
                                            encoded(actual),
                                            encoded(step.expect),
                                            "candidate corpus result differs",
                                        )

                                    for cell, content in step.cells.items():
                                        self.assertEqual(
                                            encoded(runtime.read(cell)),
                                            encoded(content),
                                            "candidate corpus cell "
                                            "content differs",
                                        )

                                    checked_steps += 1

                if needs_constraints:
                    constrained_examples += 1

        self.assertGreater(checked_steps, 0)
        self.assertGreater(
            constrained_examples, 0,
            "corpus did not exercise any constraint admission",
        )

    def test_existing_regressions_remain_mandatory(self):
        validate_partition()

        assigned = {
            module
            for modules in LANES.values()
            for module in modules
        }
        self.assertTrue(
            REQUIRED_REGRESSIONS <= assigned,
            "an applicable regression lane was removed",
        )


if __name__ == "__main__":
    unittest.main()
