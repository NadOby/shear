"""Resource-efficiency acceptance for SHEAR GH-123 T5.

Plan-owned, candidate-dependent, outside ordinary discovery.
Resource counters are independently checked against observed
memory and CPU scaling. Source-path audit remains mandatory.
"""

from importlib import import_module
from statistics import median
from time import process_time_ns
import tracemalloc
import unittest

from shear import (
    AllOf,
    EntityID,
    IsKind,
    OneOf,
    Relation,
)
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
)
from tests.constraint_functions_projection_adversarial import (
    canonical_bytes,
)


class InspectionResourceAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.candidate = import_module(
                "tests.constraint_functions_complete_candidate"
            )
        cls.entries = cls.candidate.EVALUATOR_ENTRIES

        if not callable(
            getattr(cls.candidate, "resource_probe", None)
        ):
            raise AssertionError("candidate lacks resource_probe")

    def probe(self, value, operation, argument):
        """Return independently auditable per-operation measurements.

        The candidate resource_probe must return:
            (result, counters)

        counters must expose:
            inspected_items
            full_container_copies
            whole_container_sorts
            whole_container_serializations

        Counters cover the requested inspection operation only,
        excluding canonicalization, preparation and admission.
        They must come from instrumented generic implementation
        boundaries, not candidate-estimated complexity.
        """
        with candidate_execution_guard(self.entries) as opened:
            result, counters = self.candidate.resource_probe(
                value, operation, argument
            )
        self.assertTrue(opened)
        self.assertIsInstance(counters, dict)
        for key in (
            "inspected_items",
            "full_container_copies",
            "whole_container_sorts",
            "whole_container_serializations",
        ):
            self.assertIn(key, counters)
            self.assertIs(type(counters[key]), int)
            self.assertGreaterEqual(counters[key], 0)
        return result, counters

    def assert_shallow(self, counters, collection_size):
        self.assertLessEqual(
            counters["inspected_items"], 8,
        )
        for key in (
            "full_container_copies",
            "whole_container_sorts",
            "whole_container_serializations",
        ):
            self.assertEqual(
                counters[key], 0,
                f"{key} on {collection_size} elements",
            )

    def test_map_repeated_index_access(self):
        for size in (128, 1024, 4096):
            value = {
                f"key-{index:06d}": index
                for index in range(size)
            }
            ordered = sorted(
                value, key=canonical_bytes,
            )
            positions = (0, size // 2, size - 1)

            for _ in range(8):
                for index in positions:
                    result, counters = self.probe(
                        value, "item", index,
                    )
                    self.assertEqual(
                        canonical_bytes(result),
                        canonical_bytes(
                            (ordered[index], value[ordered[index]])
                        ),
                    )
                    self.assert_shallow(counters, size)

    def test_large_sequence_access(self):
        for size in (128, 1024, 4096):
            value = tuple(range(size))
            for index in (0, size // 2, size - 1):
                result, counters = self.probe(
                    value, "item", index,
                )
                self.assertEqual(result, value[index])
                self.assert_shallow(counters, size)

    def test_large_relation_roles(self):
        for size in (128, 1024):
            roles = {
                f"role-{index:06d}": EntityID(str(index))
                for index in range(size)
            }
            value = Relation("large", roles)
            for _ in range(8):
                result, counters = self.probe(
                    value, "field", "roles",
                )
                self.assertEqual(len(result), size)
                self.assert_shallow(counters, size)

    def test_large_constraint_operands(self):
        for size in (128, 1024):
            # Use semantically distinct constraints so canonical
            # deduplication cannot collapse the collection.
            value = OneOf(*range(size))
            for _ in range(8):
                result, counters = self.probe(
                    value, "field", "arguments",
                )
                self.assertEqual(len(result), 1)
                self.assert_shallow(counters, size)

    def test_inspection_scaling(self):
        observations = []

        for size in (128, 4096):
            value = tuple(range(size))

            # Preparation and first access are outside measurement.
            self.probe(value, "inspect", None)

            samples = []
            for _ in range(7):
                tracemalloc.start()
                start = process_time_ns()

                for _ in range(16):
                    result, counters = self.probe(
                        value, "inspect", None,
                    )
                    self.assert_shallow(counters, size)

                elapsed = process_time_ns() - start
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                samples.append((elapsed, peak))

            observations.append((
                median(sample[0] for sample in samples),
                median(sample[1] for sample in samples),
            ))

        small, large = observations

        # Deliberately generous limits to distinguish proportional
        # reconstruction from fixed execution overhead.
        self.assertLess(
            large[0], small[0] * 8,
            "inspection CPU work scales with container size",
        )
        self.assertLess(
            large[1], small[1] + 262144,
            "inspection allocates proportional container storage",
        )


if __name__ == "__main__":
    unittest.main()
