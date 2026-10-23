"""Acceptance tests for the task-23 diagnostic (issue #60).

The Plan owns this contract. Execute implements tests.content_baseline.
Timing runs only through manually dispatched CI, never these tests.

Plan amendment after independent Review: the measurement runner's
correctness guards are exercised with fake runtimes, without benchmarking.
"""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from shear.lang import Function
from shear.examples import self_hosting, vm
from tests import content_baseline, content_baseline_measure
from tests.mutation_catalog import SURVIVORS, SURVIVOR_SOURCE_BLOBS


ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    "shear/canonical.py",
    "shear/values.py",
    "shear/relations.py",
}
CONVERTERS = {"canonicalize", "canonical_serialize", "relation_of"}


def direct_calls() -> set[tuple[str, int, int, str]]:
    """Independently locate selected conversion calls in production."""
    found = set()

    for path in (ROOT / "shear").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT).as_posix()

        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue

            callee = node.func
            name = (
                callee.id if isinstance(callee, ast.Name)
                else callee.attr if isinstance(callee, ast.Attribute)
                else None
            )

            if name in CONVERTERS:
                found.add((relative, node.lineno, node.col_offset, name))

    return found


def sample_measurement() -> dict:
    """Schema fixture, not a claim that these numbers were measured."""
    output = (("END",),)

    return {
        "workload": "lower(lower)",
        "revision": "a" * 40,
        "ci_run_url": "https://github.com/NadOby/shear/actions/runs/1",
        "hardware": {
            "python": "3.12",
            "os": "Linux",
            "cpu": "fixture CPU",
            "cores": 2,
        },
        "routes": {
            "native": {
                "seconds": [1.0, 1.1, 1.2],
                "peak_traced_bytes": 1024,
                "output": output,
            },
            "shear_vm": {
                "seconds": [4.0, 4.1, 4.2],
                "peak_traced_bytes": 2048,
                "output": output,
            },
        },
        "sizes": {
            "compiler_chunk_bytes": 100,
            "derived_chunk_count": 2,
            "derived_chunk_bytes": 200,
            "state_content_bytes": 300,
            "image_exclusions": ["host runtime machinery"],
        },
        "edit": {
            "phase_seconds": {
                "define": 0.1,
                "lower": 0.2,
                "activate": 0.3,
            },
            "total_seconds": 0.6,
            "affected_nodes": 1,
            "affected_chunks": 1,
            "before": 1,
            "after": 2,
        },
    }


class ContentBaselineTests(unittest.TestCase):
    def test_inventory_is_deterministic_and_serializable(self) -> None:
        first = content_baseline.collect_inventory()
        second = content_baseline.collect_inventory()

        self.assertEqual(
            json.dumps(first, sort_keys=True),
            json.dumps(second, sort_keys=True),
        )
        self.assertNotIn("timings", first)
        self.assertTrue(first["conversion_sites"])

    def test_conversion_sites_are_source_grounded(self) -> None:
        sites = content_baseline.collect_inventory()["conversion_sites"]
        observed = set()

        for site in sites:
            with self.subTest(site=site):
                key = (
                    site["path"], site["line"],
                    site["column"], site["callee"],
                )
                self.assertNotIn(key, observed)
                observed.add(key)

                self.assertTrue((ROOT / site["path"]).is_file())
                self.assertTrue(site["function"])
                self.assertTrue(site["source_representation"])
                self.assertTrue(site["destination_representation"])
                self.assertIn(
                    site["kind"],
                    {"direct", "recursive", "preserving"},
                )
                self.assertIn(
                    site["necessity"],
                    {"semantic", "implementation"},
                )
                self.assertIn(
                    site["retention"],
                    {"retained", "reconstructed", "neither"},
                )
                self.assertIn("overlap", site)

        expected = direct_calls()
        self.assertTrue(expected)
        self.assertFalse(expected - observed)

    def test_representations_and_boundaries_are_classified(self) -> None:
        report = content_baseline.collect_inventory()

        findings = {
            entry["subject"]: entry
            for entry in report["representations"]
        }
        self.assertTrue({
            "Value.content",
            "Relation.roles",
            "Relation.payload",
            "relation_of cache",
        } <= findings.keys())

        for finding in findings.values():
            self.assertTrue(finding["classification"])
            self.assertTrue(finding["evidence"])

        boundaries = report["boundaries"]
        self.assertTrue(boundaries)

        for boundary in boundaries:
            self.assertTrue(boundary["function"])
            self.assertTrue(boundary["source_representation"])
            self.assertTrue(boundary["destination_representation"])
            self.assertIn("host_service", boundary)

        self.assertTrue({
            "shear/examples/self_hosting.py",
            "shear/examples/vm_bootstrap.py",
        } <= {entry["path"] for entry in boundaries})

    def test_survivors_match_the_reviewed_catalog(self) -> None:
        report = content_baseline.collect_inventory()

        expected = {
            key: value
            for key, value in SURVIVORS.items()
            if key[0] in TARGETS
        }
        actual = {}

        for entry in report["survivors"]:
            key = (
                entry["target"],
                entry["kind"],
                entry["source"],
                entry["occurrence"],
            )
            self.assertNotIn(key, actual)
            actual[key] = (
                entry["classification"],
                entry["reason"],
            )

        self.assertEqual(actual, expected)
        self.assertEqual(
            report["source_pins"],
            {
                target: SURVIVOR_SOURCE_BLOBS.get(target)
                for target in TARGETS
            },
        )
        self.assertIn("mutation_test_gaps", report)

    def test_measurement_schema_rejects_incomplete_evidence(self) -> None:
        valid = sample_measurement()
        content_baseline.validate_measurement(valid)

        missing = copy.deepcopy(valid)
        del missing["sizes"]["state_content_bytes"]

        with self.assertRaises(ValueError):
            content_baseline.validate_measurement(missing)

        insufficient = copy.deepcopy(valid)
        insufficient["routes"]["native"]["seconds"] = [1.0]

        with self.assertRaises(ValueError):
            content_baseline.validate_measurement(insufficient)

        disagreeing = copy.deepcopy(valid)
        disagreeing["routes"]["shear_vm"]["output"] = (("LIT", 1),)

        with self.assertRaises(ValueError):
            content_baseline.validate_measurement(disagreeing)


class BootstrapMeasurementGuardTests(unittest.TestCase):
    """Exercise the diagnostic's real route checks without actual execution.

    Construction, program execution, timing and memory tracing are mocked.
    Assertions must be performed by _compiler_routes itself. In particular,
    the host fallback probe must reject a retained source lowering request.
    """

    def probe(
        self,
        *,
        retained_matches: bool = True,
        wrapper_valid: bool = True,
        generation: int = 1,
        output_matches: bool = True,
        host_fallback: bool = False,
    ):
        source = ("add", ("arg", "e"), ("lit", 1))
        original = Function(("e",), source)
        retained = (
            original if retained_matches
            else Function(("e",), ("lit", 7))
        )
        installed = Function(
            ("e",),
            (
                ("call", "vm", ("arg", "e"))
                if wrapper_valid else ("lit", 0)
            ),
        )
        initial_state = object()
        swapped_state = object()
        instances = []
        executions = []

        class FakeRuntime:
            def __init__(self, state):
                self.active = SimpleNamespace(state=state)
                instances.append(self)

        def fake_function_at(state, entity):
            if state is initial_state and entity == self_hosting.LOWER:
                return original
            if state is swapped_state:
                if entity == vm.source_name("lower"):
                    return retained
                if entity == self_hosting.LOWER:
                    return installed
            raise AssertionError("unexpected function_at request")

        def fake_run(runtime, entry, *args, **kwargs):
            if entry == vm.SWAP_ALL:
                if runtime is not instances[1]:
                    raise AssertionError("bootstrap installed on wrong route")
                if kwargs != {"may_activate": True}:
                    raise AssertionError("bootstrap lacks activation capability")
                runtime.active.state = swapped_state
                return True

            if entry == vm.GENERATION:
                if runtime is not instances[1]:
                    raise AssertionError("generation read on wrong route")
                return (generation, ())

            if entry == self_hosting.LOWER:
                if args != (source,) or kwargs:
                    raise AssertionError("compiler workload is not lower(lower)")

                if runtime is instances[0]:
                    executions.append("native")
                    return (("END",),)

                if runtime is instances[1]:
                    executions.append("shear_vm")

                    if host_fallback:
                        content_baseline_measure.bytecode.chunk_of(
                            swapped_state,
                            vm.source_name("lower"),
                        )

                    return (
                        (("END",),) if output_matches
                        else (("LIT", 7), ("END",))
                    )

            raise AssertionError("unexpected runtime execution")

        # An outer chunk_of mock makes a simulated fallback harmless if
        # the diagnostic omits its internal rejection guard. In that case
        # the negative test fails instead of raising an unrelated error.
        with (
            mock.patch.object(
                content_baseline_measure.vm,
                "bootstrap_entities",
                return_value={},
            ),
            mock.patch.object(
                content_baseline_measure,
                "program",
                return_value=object(),
            ),
            mock.patch.object(
                content_baseline_measure,
                "load",
                return_value=initial_state,
            ),
            mock.patch.object(
                content_baseline_measure,
                "Runtime",
                side_effect=FakeRuntime,
            ),
            mock.patch.object(
                content_baseline_measure,
                "function_at",
                side_effect=fake_function_at,
            ),
            mock.patch.object(
                content_baseline_measure,
                "run",
                side_effect=fake_run,
            ),
            mock.patch.object(
                content_baseline_measure,
                "_timings",
                return_value=[0.1, 0.2, 0.3],
            ),
            mock.patch.object(
                content_baseline_measure,
                "_peak",
                return_value=1024,
            ),
            mock.patch.object(
                content_baseline_measure.bytecode,
                "chunk_of",
                return_value=(("END",),),
            ),
        ):
            result = content_baseline_measure._compiler_routes()

        return result, executions

    def test_both_routes_compile_the_same_lower_source(self) -> None:
        (routes, _, (_, evidence)), executions = self.probe()

        self.assertEqual(executions, ["native", "shear_vm"])
        self.assertEqual(
            routes["native"]["output"],
            routes["shear_vm"]["output"],
        )
        self.assertEqual(evidence["generation"], 1)
        self.assertTrue(evidence["structural_output_equal"])
        self.assertFalse(evidence["retained_source_host_fallback"])

    def test_retained_source_mismatch_is_rejected(self) -> None:
        with self.assertRaises(AssertionError):
            self.probe(retained_matches=False)

    def test_non_vm_compiler_wrapper_is_rejected(self) -> None:
        with self.assertRaises(AssertionError):
            self.probe(wrapper_valid=False)

    def test_wrong_compiler_generation_is_rejected(self) -> None:
        with self.assertRaises(AssertionError):
            self.probe(generation=2)

    def test_different_compiler_outputs_are_rejected(self) -> None:
        with self.assertRaises(AssertionError):
            self.probe(output_matches=False)

    def test_host_lowering_of_retained_source_is_rejected(self) -> None:
        with self.assertRaises(AssertionError):
            self.probe(host_fallback=True)


if __name__ == "__main__":
    unittest.main()
