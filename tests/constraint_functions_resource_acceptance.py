"""Independent inspection-resource acceptance for SHEAR GH-123.

Plan-owned candidate tests, outside ordinary CI discovery.
Preparation and canonicalization precede measured access.
No resource counter supplied by the candidate is trusted.
"""

from importlib import import_module
import sys
import tracemalloc
import unittest

from shear import (
    EntityID,
    OneOf,
    Relation,
    canonicalize,
)
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
)
from tests.constraint_functions_projection_adversarial import (
    canonical_bytes,
)


SMALL = 128
LARGE = 4096
MAX_OPCODE_RATIO = 8
MAX_EXTRA_PEAK_BYTES = 12 * 1024


class BoundaryMeter:
    """Test-owned instrumentation of generic implementation frames."""

    def __init__(self, functions):
        self.codes = {function.__code__ for function in functions}
        if not self.codes:
            raise AssertionError("no generic inspection boundaries")
        self.opcodes = 0
        self.entries = 0
        self.peak_bytes = 0
        self.active = 0
        self.baseline = 0

    def trace(self, frame, event, arg):
        if event == "call":
            if frame.f_code not in self.codes:
                return None
            frame.f_trace_opcodes = True
            frame.f_trace_lines = False
            self.entries += 1
            if self.active == 0:
                self.baseline = tracemalloc.get_traced_memory()[0]
                tracemalloc.reset_peak()
            self.active += 1
            return self.trace

        if event == "opcode":
            self.opcodes += 1

        if event == "return":
            _, peak = tracemalloc.get_traced_memory()
            self.peak_bytes = max(
                self.peak_bytes,
                max(0, peak - self.baseline),
            )
            self.active -= 1

        return self.trace

    def run(self, operation):
        previous = sys.gettrace()
        if previous is not None:
            raise AssertionError(
                "resource acceptance requires exclusive tracing"
            )
        tracemalloc.start()
        try:
            sys.settrace(self.trace)
            try:
                result = operation()
            finally:
                sys.settrace(None)
        finally:
            tracemalloc.stop()

        if self.active:
            raise AssertionError("unbalanced inspection boundaries")
        if not self.entries or not self.opcodes:
            raise AssertionError(
                "no instrumented generic inspection executed"
            )
        return result


class InspectionResourceAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.candidate = import_module(
                "tests.constraint_functions_complete_candidate"
            )

        cls.entries = cls.candidate.EVALUATOR_ENTRIES

        if not callable(getattr(
            cls.candidate, "prepare_resource_probe", None
        )):
            raise AssertionError(
                "candidate lacks prepare_resource_probe"
            )

        cls.boundaries = getattr(
            cls.candidate, "INSPECTION_RESOURCE_BOUNDARIES", None
        )
        if not cls.boundaries:
            raise AssertionError(
                "generic inspection boundaries not registered"
            )

        for function in cls.boundaries:
            if not callable(function) or not hasattr(
                function, "__code__"
            ):
                raise AssertionError(
                    "resource boundary must be a Python function"
                )
            if not function.__module__.startswith("shear."):
                raise AssertionError(
                    "resource boundary must belong to SHEAR"
                )

    def prepare(self, value, operation):
        canonical = canonicalize(value)
        prepared = self.candidate.prepare_resource_probe(
            canonical, operation
        )
        if not callable(prepared):
            raise AssertionError("invalid prepared resource operation")
        return prepared

    def measure(self, prepared, argument):
        meter = BoundaryMeter(self.boundaries)

        def execute():
            with candidate_execution_guard(self.entries) as opened:
                result = prepared(argument)
            self.assertTrue(
                opened,
                "resource operation bypassed admitted SHEAR",
            )
            return result

        result = meter.run(execute)
        return result, meter

    def assert_access(self, prepared, argument, expected):
        result, meter = self.measure(prepared, argument)
        self.assertEqual(
            canonical_bytes(result),
            canonical_bytes(expected),
        )
        return meter

    def assert_scaling(self, small, large):
        self.assertLessEqual(
            large.opcodes,
            small.opcodes * MAX_OPCODE_RATIO,
            "inspection work scales with complete container size",
        )
        self.assertLessEqual(
            large.peak_bytes,
            small.peak_bytes + MAX_EXTRA_PEAK_BYTES,
            "inspection allocates proportional container storage",
        )

    def test_repeated_map_access(self):
        measurements = []

        for size in (SMALL, LARGE):
            value = {
                f"key-{index:06d}": index
                for index in range(size)
            }
            ordered = sorted(value, key=canonical_bytes)
            prepared = self.prepare(value, "item")
            meters = []

            for _ in range(8):
                for index in (0, size // 2, size - 1):
                    key = ordered[index]
                    meters.append(self.assert_access(
                        prepared,
                        index,
                        (key, value[key]),
                    ))

            measurements.append((
                max(m.opcodes for m in meters),
                max(m.peak_bytes for m in meters),
            ))

        small, large = measurements
        self.assertLessEqual(
            large[0], small[0] * MAX_OPCODE_RATIO,
        )
        self.assertLessEqual(
            large[1], small[1] + MAX_EXTRA_PEAK_BYTES,
        )

    def test_sequence_index_scaling(self):
        meters = []

        for size in (SMALL, LARGE):
            value = tuple(range(size))
            prepared = self.prepare(value, "item")
            meters.append(self.assert_access(
                prepared, size // 2, value[size // 2],
            ))

        self.assert_scaling(*meters)

    def test_relation_role_contents_and_order(self):
        for size in (SMALL, LARGE):
            roles = {
                f"role-{index:06d}": EntityID(str(index))
                for index in range(size)
            }
            relation = Relation("large", roles)
            expected = tuple(sorted(roles.items()))
            prepared = self.prepare(relation, "roles")

            for _ in range(4):
                self.assert_access(
                    prepared, None, expected,
                )

    def test_constraint_operand_contents(self):
        for size in (SMALL, LARGE):
            constraint = OneOf(*range(size))
            expected = (constraint.values,)
            prepared = self.prepare(
                constraint, "arguments",
            )

            for _ in range(4):
                self.assert_access(
                    prepared, None, expected,
                )

    def test_shallow_inspect_scaling(self):
        meters = []

        for size in (SMALL, LARGE):
            value = tuple(range(size))
            prepared = self.prepare(value, "inspect")
            meters.append(self.assert_access(
                prepared, None, ("tuple", canonicalize(value)),
            ))

        self.assert_scaling(*meters)


if __name__ == "__main__":
    unittest.main()
