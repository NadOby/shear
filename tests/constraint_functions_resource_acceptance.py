"""Independent T5 inspection resource acceptance for SHEAR GH-123.

Plan-owned candidate-dependent tests; excluded from ordinary discovery.
The test owns every measurement window. No candidate-reported work or
allocation counters are accepted as evidence.

Execute supplies prepare_resource_probe(canonical_value, operation),
returning a reusable callable taking one argument. The test-only
"control" operation uses the same admitted invocation and canonical
argument path as the inspected operation, but returns a fixed value.
It must not inspect the subject; source audit verifies that contract.
Neither name adds a public SHEAR operation.

Shallow inspection and single-element access have constant-output
resource expectations. Explicitly requested whole-field results have
output-proportional resource allowances, not constant-work limits.
"""

from importlib import import_module
from statistics import median
from time import process_time_ns
import sys
import tracemalloc
import unittest

from shear import EntityID, OneOf, Relation, canonicalize
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
)
from tests.constraint_functions_projection_adversarial import canonical_bytes


SMALL = 128
LARGE = 8192
REPEATS = 8
SAMPLES = 5
WORK_RATIO_LIMIT = 8
ALLOCATION_GROWTH_LIMIT = 16 * 1024

# These limits apply only when the complete field is explicitly
# requested. They permit a bounded output representation, not an
# unbounded number of whole-container intermediate copies.
OUTPUT_CPU_SLOPE_TOLERANCE = 3
ROLE_BYTES_PER_ITEM = 96
OPERAND_BYTES_PER_ITEM = 24


class WholeInvocationProfile:
    """Observe all Python and C call boundaries, not nominated functions."""

    def __init__(self):
        self.python_calls = 0
        self.native_calls = 0
        self.modules = set()

    def observe(self, frame, event, arg):
        if event == "call":
            self.python_calls += 1
            module = frame.f_globals.get("__name__")
            if isinstance(module, str):
                self.modules.add(module)
        elif event == "c_call":
            self.native_calls += 1

    def run(self, operation):
        if sys.getprofile() is not None:
            raise AssertionError("resource profiling requires exclusive use")
        try:
            sys.setprofile(self.observe)
            return operation()
        finally:
            sys.setprofile(None)


class WholeInvocationMeasurement:
    """Measure complete prepared invocations without interior resets.

    The restricted guard is installed outside the measured interval.
    Results and authentication assertions are checked afterward.
    A matched constant-work admitted invocation measures the fixed
    machine/invocation overhead on the same canonical input.
    """

    def __init__(self, entries):
        self.entries = entries

    def run(self, prepared, argument):
        with candidate_execution_guard(self.entries) as opened:
            prepared(argument)

            cpu_samples = []
            for _ in range(SAMPLES):
                start = process_time_ns()
                for _ in range(REPEATS):
                    result = prepared(argument)
                elapsed = process_time_ns() - start
                cpu_samples.append(elapsed / REPEATS)

            peaks = []
            for _ in range(SAMPLES):
                tracemalloc.start()
                try:
                    baseline, _ = tracemalloc.get_traced_memory()
                    tracemalloc.reset_peak()
                    result = prepared(argument)
                    _, peak = tracemalloc.get_traced_memory()
                    peaks.append(max(0, peak - baseline))
                finally:
                    tracemalloc.stop()

            profile = WholeInvocationProfile()
            result = profile.run(lambda: prepared(argument))

        if not opened:
            raise AssertionError("no authenticated SHEAR evaluator entered")
        if not profile.python_calls or not profile.native_calls:
            raise AssertionError("incomplete whole-invocation call coverage")
        if not any(name.startswith("shear.") for name in profile.modules):
            raise AssertionError("no SHEAR implementation frames observed")

        return result, median(cpu_samples), median(peaks), profile


def overhead_adjusted(measured, control):
    """Subtract matched invocation overhead; never invent negative cost."""
    return max(0, measured - control)


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
            raise AssertionError("candidate lacks prepare_resource_probe")

    def prepare(self, value, operation):
        canonical = canonicalize(value)
        inspected = self.candidate.prepare_resource_probe(
            canonical, operation
        )
        control = self.candidate.prepare_resource_probe(
            canonical, "control"
        )
        if not callable(inspected) or not callable(control):
            raise AssertionError("resource probe did not prepare callables")
        return inspected, control

    def observation_prepared(self, inspected, control, argument, expected):
        meter = WholeInvocationMeasurement(self.entries)

        result, cpu, peak, profile = meter.run(inspected, argument)
        self.assertEqual(
            canonical_bytes(result), canonical_bytes(expected),
            "resource observation has incorrect semantic content",
        )

        _, control_cpu, control_peak, control_profile = meter.run(
            control, argument
        )

        return {
            "cpu": overhead_adjusted(cpu, control_cpu),
            "peak": overhead_adjusted(peak, control_peak),
            "cpu_total": cpu,
            "control_cpu": control_cpu,
            "python_calls": profile.python_calls,
            "native_calls": profile.native_calls,
            "control_python_calls": control_profile.python_calls,
            "control_native_calls": control_profile.native_calls,
            "inspected": inspected,
            "control": control,
            "argument": argument,
        }

    def observation(self, value, operation, argument, expected):
        inspected, control = self.prepare(value, operation)
        return self.observation_prepared(
            inspected, control, argument, expected
        )

    def assert_scaling(self, small, large, *, label):
        """Constant-output operations must avoid container-sized work."""
        cpu_ceiling = max(
            small["cpu"] * WORK_RATIO_LIMIT,
            small["control_cpu"] * 0.05,
        )
        memory_ceiling = small["peak"] + ALLOCATION_GROWTH_LIMIT

        probe = WholeInvocationMeasurement(self.entries)
        synthetics = []

        for row, count in ((small, SMALL), (large, LARGE)):
            def copied(argument, row=row, count=count):
                temporary = [None] * count
                result = row["inspected"](argument)
                if len(temporary) != count:
                    raise AssertionError("synthetic copy did not execute")
                return result

            _, _, copy_peak, _ = probe.run(
                copied, row["argument"]
            )
            synthetics.append(copy_peak)

        self.assertGreater(
            synthetics[1] - synthetics[0],
            ALLOCATION_GROWTH_LIMIT,
            f"{label}: instrumentation cannot detect full copying",
        )

        cpu_negative = []
        for row, count in ((small, SMALL), (large, LARGE)):
            def sorted_call(argument, row=row, count=count):
                ordered = sorted(range(count, 0, -1))
                result = row["inspected"](argument)
                if len(ordered) != count:
                    raise AssertionError("synthetic sort did not execute")
                return result

            _, sort_cpu, _, _ = probe.run(
                sorted_call, row["argument"]
            )
            cpu_negative.append(sort_cpu)

        self.assertGreater(
            overhead_adjusted(
                cpu_negative[1], large["control_cpu"]
            ),
            cpu_ceiling,
            f"{label}: timing cannot detect a native whole-container sort",
        )
        self.assertLessEqual(
            large["cpu"], cpu_ceiling,
            f"{label}: inspection work scales with container size",
        )
        self.assertLessEqual(
            large["peak"], memory_ceiling,
            f"{label}: avoidable full-container allocation",
        )

    def assert_output_scaling(
        self, small, large, *, label, bytes_per_item
    ):
        """Permit bounded materialization of explicitly requested output.

        The complete field contains O(n) semantic values. Comparing it
        against constant-work shallow inspection would reject legitimate
        representations that must construct the requested output.

        This bound constrains growth to output-proportional work and
        storage. Avoidable repeated sorting and extra copies still
        require independent source-path auditing.
        """
        self.assertGreater(bytes_per_item, 0)

        size_ratio = LARGE / SMALL
        baseline_cpu = max(
            small["cpu"],
            small["control_cpu"] * 0.1,
            1,
        )
        cpu_ceiling = (
            baseline_cpu
            * size_ratio
            * OUTPUT_CPU_SLOPE_TOLERANCE
        )

        allocation_ceiling = (
            small["peak"]
            + ALLOCATION_GROWTH_LIMIT
            + (LARGE - SMALL) * bytes_per_item
        )

        self.assertLessEqual(
            large["cpu"],
            cpu_ceiling,
            f"{label}: cost exceeds output-proportional bound",
        )
        self.assertLessEqual(
            large["peak"],
            allocation_ceiling,
            f"{label}: allocation exceeds output materialization bound",
        )

    def test_repeated_canonical_map_index(self):
        rows = []

        for size in (SMALL, LARGE):
            value = {
                f"key-{i:06d}": i for i in range(size)
            }
            ordered = sorted(value, key=canonical_bytes)

            inspected, control = self.prepare(value, "item")
            observed = []

            for _ in range(3):
                for index in (0, size // 2, size - 1):
                    observed.append(self.observation_prepared(
                        inspected, control, index,
                        (ordered[index], value[ordered[index]]),
                    ))

            rows.append(
                max(observed, key=lambda row: row["cpu"])
            )

        self.assert_scaling(
            *rows, label="repeated map item"
        )

    def test_large_sequence_index(self):
        rows = []

        for size in (SMALL, LARGE):
            value = tuple(range(size))
            rows.append(self.observation(
                value, "item", size // 2, value[size // 2],
            ))

        self.assert_scaling(*rows, label="tuple item")

    def test_relation_role_contents_order_and_scaling(self):
        rows = []

        for size in (SMALL, LARGE):
            roles = {
                f"role-{i:06d}": EntityID(str(i))
                for i in range(size)
            }
            value = Relation("large", roles)
            expected = tuple(sorted(roles.items()))

            rows.append(self.observation(
                value, "roles", None, expected,
            ))

        self.assert_output_scaling(
            *rows,
            label="relation roles",
            bytes_per_item=ROLE_BYTES_PER_ITEM,
        )

    def test_constraint_operands_contents_and_scaling(self):
        rows = []

        for size in (SMALL, LARGE):
            value = OneOf(*range(size))
            rows.append(self.observation(
                value, "arguments", None, (value.values,),
            ))

        self.assert_output_scaling(
            *rows,
            label="constraint operands",
            bytes_per_item=OPERAND_BYTES_PER_ITEM,
        )

    def test_shallow_inspection_scaling(self):
        rows = []

        for size in (SMALL, LARGE):
            value = tuple(range(size))
            rows.append(self.observation(
                value, "inspect", None,
                ("tuple", canonicalize(value)),
            ))

        self.assert_scaling(*rows, label="shallow inspect")


if __name__ == "__main__":
    unittest.main()
