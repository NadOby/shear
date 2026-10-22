"""Independent T5 inspection resource acceptance for SHEAR GH-123.

Candidate-dependent tests, outside ordinary CI discovery.
All measured invocations must enter authenticated admitted SHEAR code.
Cold and warm inspection costs are measured independently, with
interleaved matched controls and independent negative calibration.

Execute supplies prepare_resource_probe(canonical_value, operation),
which returns a reusable callable taking one argument. "control" is a
test-only, constant-work admitted invocation over the same prepared
canonical value. It is not a public SHEAR language operation.

Shallow inspection is measured without recursively consuming contents.
Explicitly requested full output is consumed inside measurement.
"""

from importlib import import_module
from random import Random
from statistics import median
from time import process_time_ns
import sys
import tracemalloc
import unittest

from shear import AllOf, EntityID, IntRange, OneOf, Relation, canonicalize
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
)
from tests.constraint_functions_projection_adversarial import canonical_bytes


SMALL = 128
LARGE = 8192
SAMPLES = 5
REPEATS = 8
WORK_RATIO_LIMIT = 8
ALLOCATION_GROWTH_LIMIT = 16 * 1024
OUTPUT_CPU_SLOPE_TOLERANCE = 3
ROLE_BYTES_PER_ITEM = 96


class WholeInvocationProfile:
    """Supplemental Python/C call provenance, not a native malloc meter."""

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
            raise AssertionError("exclusive profiling required")
        try:
            sys.setprofile(self.observe)
            return operation()
        finally:
            sys.setprofile(None)


def signed_delta(first, second):
    """Retain negative control differences as measurement evidence."""
    return first - second


class WholeInvocationMeasurement:
    """Measure first use and paired warm calls, guarding every invocation.

    Input canonicalization, deployment and adapter preparation occur
    before this boundary. No candidate call occurs before the first
    measured invocation. Time and Python-traced allocation are sampled
    over complete calls, never reset at candidate-nominated frames.
    """

    def __init__(self, entries):
        self.entries = entries

    def run(self, inspected, control, argument, *, materialize=False):
        if materialize:
            operation = inspected

            def inspected(arg):
                result = operation(arg)
                canonical_bytes(result)
                return result

        if sys.getprofile() is not None or sys.gettrace() is not None:
            raise AssertionError("resource measurements need exclusive hooks")

        cpu_pairs = []
        allocation_pairs = []
        results = []

        with candidate_execution_guard(self.entries) as opened:

            def invoke(prepared, *, allocation):
                before = len(opened)
                if allocation:
                    tracemalloc.start()
                    baseline, _ = tracemalloc.get_traced_memory()
                    tracemalloc.reset_peak()
                try:
                    started = process_time_ns()
                    value = prepared(argument)
                    elapsed = process_time_ns() - started
                    if allocation:
                        _, peak = tracemalloc.get_traced_memory()
                        size = max(0, peak - baseline)
                    else:
                        size = None
                finally:
                    if allocation:
                        tracemalloc.stop()

                if len(opened) <= before:
                    raise AssertionError(
                        "measured invocation did not enter authenticated "
                        "admitted evaluator code"
                    )
                return value, elapsed, size

            # No unmeasured warm-up. Both first calls are recorded.
            first_value, first_cpu, first_peak = invoke(
                inspected, allocation=True
            )
            _, first_control_cpu, first_control_peak = invoke(
                control, allocation=True
            )
            results.append(first_value)

            # Interleave calls; alternate order to limit drift bias.
            for index in range(SAMPLES * REPEATS):
                if index % 2:
                    _, control_cpu, _ = invoke(
                        control, allocation=False
                    )
                    value, inspection_cpu, _ = invoke(
                        inspected, allocation=False
                    )
                else:
                    value, inspection_cpu, _ = invoke(
                        inspected, allocation=False
                    )
                    _, control_cpu, _ = invoke(
                        control, allocation=False
                    )
                results.append(value)
                cpu_pairs.append((inspection_cpu, control_cpu))

            for index in range(SAMPLES):
                if index % 2:
                    _, _, control_peak = invoke(control, allocation=True)
                    value, _, inspection_peak = invoke(
                        inspected, allocation=True
                    )
                else:
                    value, _, inspection_peak = invoke(
                        inspected, allocation=True
                    )
                    _, _, control_peak = invoke(control, allocation=True)
                results.append(value)
                allocation_pairs.append((inspection_peak, control_peak))

            profile = WholeInvocationProfile()
            before = len(opened)
            result = profile.run(lambda: inspected(argument))
            if len(opened) <= before:
                raise AssertionError("profiled invocation lacked VM entry")
            results.append(result)

        if not profile.python_calls or not profile.native_calls:
            raise AssertionError("whole-invocation profile lacks call evidence")
        if not any(name.startswith("shear.") for name in profile.modules):
            raise AssertionError("profile lacks SHEAR execution frames")

        control_times = [pair[1] for pair in cpu_pairs]
        center = median(control_times)
        noise = median(abs(value - center) for value in control_times)
        return {
            "result": result,
            "results": results,
            "cold_cpu": signed_delta(first_cpu, first_control_cpu),
            "cold_peak": signed_delta(first_peak, first_control_peak),
            "warm_cpu": median(
                signed_delta(a, b) for a, b in cpu_pairs
            ),
            "warm_peak": median(
                signed_delta(a, b) for a, b in allocation_pairs
            ),
            "control_cpu": center,
            "cpu_noise": noise,
            "python_calls": profile.python_calls,
            "native_calls": profile.native_calls,
            "inspected": inspected,
            "control": control,
            "argument": argument,
        }


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
        inspected = self.candidate.prepare_resource_probe(canonical, operation)
        control = self.candidate.prepare_resource_probe(canonical, "control")
        if not callable(inspected) or not callable(control):
            raise AssertionError("resource probe did not prepare callables")
        return inspected, control

    def observation_prepared(
        self, inspected, control, argument, expected, *, materialize=False
    ):
        meter = WholeInvocationMeasurement(self.entries)
        row = meter.run(
            inspected, control, argument, materialize=materialize
        )
        reference = canonical_bytes(expected)
        for result in row.pop("results"):
            self.assertEqual(
                canonical_bytes(result), reference,
                "measured invocation returned incorrect semantic content",
            )
        return row

    def observation(
        self, value, operation, argument, expected, *, materialize=False
    ):
        inspected, control = self.prepare(value, operation)
        return self.observation_prepared(
            inspected, control, argument, expected,
            materialize=materialize,
        )

    def assert_scaling(self, small, large, *, label):
        """Constant-output access must scale neither cold nor warm."""
        for phase in ("cold", "warm"):
            cpu_key = f"{phase}_cpu"
            peak_key = f"{phase}_peak"
            noise_floor = 5 * max(
                small["cpu_noise"], large["cpu_noise"]
            )
            cpu_limit = max(
                max(0, small[cpu_key]) * WORK_RATIO_LIMIT,
                noise_floor,
                small["control_cpu"] * 0.05,
            )
            self.assertLessEqual(
                large[cpu_key], cpu_limit,
                f"{label}: {phase} inspection CPU scales with input",
            )
            self.assertLessEqual(
                large[peak_key],
                max(0, small[peak_key]) + ALLOCATION_GROWTH_LIMIT,
                f"{label}: {phase} inspection allocates a full copy",
            )

        self.assert_calibrated(small, large, label=label)

    def assert_calibrated(self, small, large, *, label):
        """Challenge the same measurement path with a known bad operation."""
        meter = WholeInvocationMeasurement(self.entries)
        copy_growth = []
        sort_growth = []

        for row, count in ((small, SMALL), (large, LARGE)):

            def copied(argument, row=row, count=count):
                temporary = [None] * count
                result = row["inspected"](argument)
                if len(temporary) != count:
                    raise AssertionError("synthetic copy not executed")
                return result

            copy_row = meter.run(
                copied, row["control"], row["argument"]
            )
            copy_growth.append(copy_row["cold_peak"])

            shuffled = list(range(count))
            Random(0x1234).shuffle(shuffled)

            def sorted_call(argument, row=row, shuffled=shuffled):
                ordered = sorted(shuffled)
                result = row["inspected"](argument)
                if len(ordered) != len(shuffled):
                    raise AssertionError("synthetic sort not executed")
                return result

            sort_row = meter.run(
                sorted_call, row["control"], row["argument"]
            )
            sort_growth.append(sort_row["warm_cpu"])

        self.assertGreater(
            copy_growth[1] - copy_growth[0],
            ALLOCATION_GROWTH_LIMIT,
            f"{label}: instrument cannot detect full Python copying",
        )
        cpu_limit = max(
            max(0, small["warm_cpu"]) * WORK_RATIO_LIMIT,
            5 * max(small["cpu_noise"], large["cpu_noise"]),
            small["control_cpu"] * 0.05,
        )
        self.assertGreater(
            sort_growth[1], cpu_limit,
            f"{label}: instrument cannot detect repeated shuffled sort",
        )

    def assert_output_scaling(self, small, large, *, label, bytes_per_item):
        """Permit O(output-size) materialization, not repeated O(n log n)."""
        ratio = LARGE / SMALL
        for phase in ("cold", "warm"):
            cpu_key = f"{phase}_cpu"
            peak_key = f"{phase}_peak"
            cpu_baseline = max(
                small[cpu_key],
                small["control_cpu"] * 0.1,
                1,
            )
            self.assertLessEqual(
                large[cpu_key],
                cpu_baseline * ratio * OUTPUT_CPU_SLOPE_TOLERANCE,
                f"{label}: {phase} CPU exceeds output-size bound",
            )
            self.assertLessEqual(
                large[peak_key],
                max(0, small[peak_key])
                + ALLOCATION_GROWTH_LIMIT
                + (LARGE - SMALL) * bytes_per_item,
                f"{label}: {phase} allocation exceeds output bound",
            )

    def test_repeated_canonical_map_index(self):
        rows = []
        for size in (SMALL, LARGE):
            value = {f"key-{i:06d}": i for i in range(size)}
            ordered = sorted(value, key=canonical_bytes)
            inspected, control = self.prepare(value, "item")
            samples = []
            for index in (0, size // 2, size - 1):
                samples.append(self.observation_prepared(
                    inspected, control, index,
                    (ordered[index], value[ordered[index]]),
                ))

            # Preserve the most expensive cold and warm readings
            # independently, including the very first invocation.
            summary = dict(samples[0])
            for key in (
                "cold_cpu", "warm_cpu", "cold_peak", "warm_peak",
                "cpu_noise",
            ):
                summary[key] = max(sample[key] for sample in samples)
            rows.append(summary)

        self.assert_scaling(*rows, label="map item")

    def test_large_sequence_index(self):
        rows = []
        for size in (SMALL, LARGE):
            value = tuple(range(size))
            rows.append(self.observation(
                value, "item", size // 2, value[size // 2]
            ))
        self.assert_scaling(*rows, label="tuple item")

    def test_relation_role_contents_order_and_scaling(self):
        rows = []
        for size in (SMALL, LARGE):
            roles = {
                f"role-{i:06d}": EntityID(str(i)) for i in range(size)
            }
            value = Relation("large", roles)
            expected = tuple(sorted(roles.items()))
            rows.append(self.observation(
                value, "roles", None, expected, materialize=True
            ))
        self.assert_output_scaling(
            *rows, label="relation roles", bytes_per_item=ROLE_BYTES_PER_ITEM
        )

    def test_constraint_operands_contents_and_scaling(self):
        shallow = []
        composite = []
        for size in (SMALL, LARGE):
            value = OneOf(*range(size))
            shallow.append(self.observation(
                value, "arguments", None, (value.values,)
            ))
            children = AllOf(*(IntRange(i, i) for i in range(size)))
            composite.append(self.observation(
                children, "arguments", None, (children.parts,)
            ))
        self.assert_scaling(*shallow, label="one_of shallow arguments")
        self.assert_scaling(
            *composite, label="all_of shallow arguments"
        )

    def test_shallow_inspection_scaling(self):
        rows = []
        for size in (SMALL, LARGE):
            value = tuple(range(size))
            rows.append(self.observation(
                value, "inspect", None, ("tuple", canonicalize(value))
            ))
        self.assert_scaling(*rows, label="shallow inspect")


if __name__ == "__main__":
    unittest.main()
