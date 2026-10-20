"""Direct SHEAR result acceptance for issue #123.

Execute supplies:
    prepare_semantic(expression, budget, externals)
        -> (RestrictedExecutor, RestrictedDeployment, EntityID)

Preparation never receives the subject or expected result.
The resulting admitted function must accept one canonical subject
argument and return the semantic verdict directly.

This is an adapter contract, not an evaluator implementation
strategy. Compilation and generic interpretation are both allowed.

The Plan-owned test remains outside ordinary test discovery.
"""

from dataclasses import dataclass
from importlib import import_module
import unittest

from shear.hosted_bootstrap.restricted import (
    RestrictedDeployment,
    RestrictedExecutor,
)
from shear.identity import EntityID
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
)


SAT = "satisfied"
VIO = "violated"
UNK = "unknown"


@dataclass(frozen=True)
class DirectCase:
    expression: tuple
    budget: int | None
    externals: tuple
    subjects: tuple


CASES = (
    DirectCase(
        ("is_kind", "int"), None, (),
        ((5, SAT), (True, VIO), ("5", VIO), (-100, SAT)),
    ),
    DirectCase(
        ("is_kind", "bool"), None, (),
        ((True, SAT), (False, SAT), (1, VIO), (None, VIO)),
    ),
    DirectCase(
        ("int_range", 0, 10), None, (),
        ((0, SAT), (10, SAT), (11, VIO), (True, VIO)),
    ),
    DirectCase(
        ("length", 2, 2), None, (),
        (([1, 2], SAT), ([1], VIO),
         ("e\u0301", SAT), ("a", VIO)),
    ),
    DirectCase(
        ("one_of", (1, "a")), None, (),
        ((1, SAT), ("a", SAT), (True, VIO), (2, VIO)),
    ),
    DirectCase(
        ("not", ("is_kind", "bool")), None, (),
        ((True, VIO), (3, SAT), ("x", SAT)),
    ),
    DirectCase(
        ("role", "x", ("int_range", 0, 10)), None, (),
        (({"x": 3}, SAT), ({"x": 11}, VIO),
         ({"y": 3}, VIO), ((3,), VIO)),
    ),
    DirectCase(
        ("all_of", ("is_kind", "int"),
         ("int_range", 0, 10)), None, (),
        ((5, SAT), (20, VIO), ("5", VIO)),
    ),
    DirectCase(
        ("any_of", ("is_kind", "bool"),
         ("int_range", 0, 10)), None, (),
        ((True, SAT), (5, SAT), ("x", VIO)),
    ),
    DirectCase(
        ("all_of", ("is_kind", "int"),
         ("int_range", 0, 10)), 2, (),
        ((5, UNK), (20, VIO)),
    ),
    DirectCase(
        ("all_of", ("is_kind", "int"),
         ("int_range", 0, 10)), 3, (),
        ((5, SAT), (20, VIO)),
    ),
    DirectCase(
        ("is_kind", "int"), 0, (),
        ((5, UNK), (True, UNK)),
    ),
    DirectCase(
        ("is_kind", "int"), 1, (),
        ((5, SAT), (True, VIO)),
    ),
    DirectCase(
        ("not", ("is_kind", "bool")), 1, (),
        ((True, UNK), (3, UNK)),
    ),
    DirectCase(
        ("not", ("is_kind", "bool")), 2, (),
        ((True, VIO), (3, SAT)),
    ),
    DirectCase(
        ("external", "missing"), None, (),
        ((5, UNK), (True, UNK)),
    ),
    DirectCase(
        ("external", "policy"), None,
        (("policy", SAT),),
        ((5, SAT), (True, SAT)),
    ),
)


def artifact_snapshot(deployment):
    return tuple(sorted(
        (
            node.value,
            version.value,
            artifact.artifact_id,
        )
        for (node, version), artifact in deployment.artifacts.items()
    ))


class DirectEvaluatorAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.adapter = import_module(
                "tests.constraint_functions_complete_candidate"
            )

        if not callable(
            getattr(cls.adapter, "prepare_semantic", None)
        ):
            raise AssertionError(
                "candidate must implement prepare_semantic"
            )

    def test_prepared_evaluators_return_actual_verdicts(self):
        self.assertGreaterEqual(len(CASES), 17)

        for index, case in enumerate(CASES):
            with self.subTest(case=index):
                with forbid_incumbent():
                    prepared = self.adapter.prepare_semantic(
                        case.expression,
                        case.budget,
                        case.externals,
                    )

                self.assertIsInstance(prepared, tuple)
                self.assertEqual(len(prepared), 3)

                executor, deployment, entry = prepared
                self.assertIsInstance(executor, RestrictedExecutor)
                self.assertIsInstance(
                    deployment, RestrictedDeployment
                )
                self.assertIsInstance(entry, EntityID)

                self.assertIn(entry, deployment._target.state.values)
                before = artifact_snapshot(deployment)
                source = deployment.source_state_id
                generation = deployment.compiler_generation

                # One immutable admitted implementation receives all
                # subjects. No subject-dependent preparation occurs.
                with candidate_execution_guard(
                    frozenset({entry})
                ) as opened:
                    for subject, expected in case.subjects:
                        previous = len(opened)

                        result = executor.run(
                            deployment, entry, subject
                        )

                        self.assertEqual(
                            result, expected,
                            f"case={index}, subject={subject!r}",
                        )
                        self.assertGreater(
                            len(opened), previous,
                            "the admitted evaluator did not execute",
                        )
                        self.assertEqual(
                            opened[-1][1], entry,
                        )

                self.assertEqual(
                    deployment.source_state_id, source
                )
                self.assertEqual(
                    deployment.compiler_generation, generation
                )
                self.assertEqual(
                    artifact_snapshot(deployment), before
                )


if __name__ == "__main__":
    unittest.main()
