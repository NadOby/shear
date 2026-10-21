"""Generated public semantic-path acceptance for SHEAR GH-123.

Expected paths come from original semantic fixtures, not from
CanonicalNode serialization or candidate inspection.

This Plan-owned module remains outside ordinary CI discovery
until Execute.
"""

from importlib import import_module
import unittest

from shear import (
    AllOf,
    CellDeclaration,
    EntityID,
    IntRange,
    IsKind,
    Not,
    Relation,
)
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
)
from tests.constraint_functions_projection_adversarial import (
    canonical_bytes,
    generated,
    sampled_paths,
    semantic_paths,
)


class NestedRecordPathAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.candidate = import_module(
                "tests.constraint_functions_complete_candidate"
            )
        cls.entries = cls.candidate.EVALUATOR_ENTRIES

    def assert_path(self, value, path, expected):
        with candidate_execution_guard(self.entries) as opened:
            actual = self.candidate.select_projection(value, path)

        self.assertTrue(
            opened,
            f"path {path!r} bypassed admitted SHEAR execution",
        )
        self.assertEqual(
            canonical_bytes(actual),
            canonical_bytes(expected),
            f"incorrect semantic value at {path!r}",
        )

    def assert_nested_paths(self, record, prefix, original):
        paths = semantic_paths(original)
        self.assertGreater(len(paths), 1)

        for path, expected in sampled_paths(original, maximum=24):
            with self.subTest(prefix=prefix, path=path):
                self.assert_path(
                    record,
                    prefix + path,
                    expected,
                )

    def test_generated_cell_initial_structures(self):
        for seed in range(128):
            original = {
                "outer": [
                    generated(seed, depth=4),
                    (seed, {"inner": generated(seed + 1000, depth=3)}),
                ],
                "empty": [],
            }
            cell = CellDeclaration(IsKind("map"), original)

            with self.subTest(seed=seed):
                self.assert_nested_paths(
                    cell, ("initial",), original,
                )
                self.assert_nested_paths(
                    cell, (1, 1), original,
                )

    def test_generated_relation_payload_structures(self):
        roles = {
            "first": EntityID("first"),
            "second": (EntityID("second"),),
        }
        for seed in range(128):
            original = [
                {"left": generated(seed, depth=4)},
                (generated(seed + 2000, depth=4),),
            ]
            relation = Relation("nested", roles, original)

            with self.subTest(seed=seed):
                self.assert_nested_paths(
                    relation, ("payload",), original,
                )
                self.assert_nested_paths(
                    relation, (2, 1), original,
                )

    def test_nested_constraint_operands(self):
        inner = AllOf(
            IsKind("int"),
            IntRange(0, 100),
        )
        middle = Not(inner)
        outer = AllOf(
            IsKind("constraint"),
            middle,
        )

        for constraint in (inner, middle, outer):
            with self.subTest(constraint=repr(constraint)):
                paths = semantic_paths(constraint)
                self.assertGreater(len(paths), 2)

                for path, expected in paths:
                    self.assert_path(
                        constraint, path, expected,
                    )

    def test_mixed_record_and_collection_paths(self):
        payload = {
            "branch": [
                {"value": [1, 2, 3]},
                {"value": (True, False)},
            ],
        }
        relation = Relation(
            "mixed",
            {"root": EntityID("root")},
            payload,
        )
        cell = CellDeclaration(IsKind("relation"), relation)

        for prefix in (
            ("initial", "payload"),
            (1, 1, "payload"),
        ):
            self.assert_nested_paths(
                cell, prefix, payload,
            )


if __name__ == "__main__":
    unittest.main()
