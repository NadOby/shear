"""Non-frozen regression and performance evidence for GH-123 P0-B."""

from __future__ import annotations

from statistics import median
from time import perf_counter, process_time
import unittest
from unittest.mock import patch

from shear import (
    AllOf, CellDeclaration, EntityID, IsKind, Relation,
    canonicalize, canonical_serialize, machine,
)
from shear.examples._support import program
from shear.examples.constraint_evaluator import EQUAL_ITEMS, VALUE_EQUAL
from shear.hosted_bootstrap import restricted
from shear.hosted_bootstrap.restricted import (
    AdmissionRejected,
    RestrictedExecutor,
)
from shear.lang import LanguageError, load, links
from tests import constraint_functions_complete_candidate as candidate


ENTRIES = (
    candidate.PROJECT_INSPECT,
    candidate.PROJECT_EQUAL,
    candidate.PROJECT_SELECT,
    candidate.PROJECT_LENGTH,
    candidate.PROJECT_SLICE,
)

# Map paths are positional and canonical-key ordered. Named components
# belong to semantic records, not ordinary mappings.
NESTED_VALUE = {
    "z": (0, False),
    "a": {"nested": [5, 7]},
}
NESTED_PATH = (0, 1, 0, 1, 1)
NESTED_RESULT = 7


def canonical_bytes(value):
    return canonical_serialize(canonicalize(value))


class ProjectionClosureTests(unittest.TestCase):
    def setUp(self):
        candidate._projection_deployment.cache_clear()

    def tearDown(self):
        candidate._projection_deployment.cache_clear()

    def test_exact_static_dependency_closures(self):
        entities = candidate._projection_entities()

        expected = {
            candidate.PROJECT_INSPECT: {
                candidate.PROJECT_INSPECT,
            },
            candidate.PROJECT_EQUAL: {
                candidate.PROJECT_EQUAL,
                VALUE_EQUAL,
                EQUAL_ITEMS,
                EntityID(f"{candidate.PROJECT_EQUAL.value}.links"),
                EntityID(f"{VALUE_EQUAL.value}.links"),
                EntityID(f"{EQUAL_ITEMS.value}.links"),
            },
            candidate.PROJECT_SELECT: {
                candidate.PROJECT_SELECT,
                EntityID(f"{candidate.PROJECT_SELECT.value}.links"),
            },
            candidate.PROJECT_LENGTH: {
                candidate.PROJECT_LENGTH,
            },
            candidate.PROJECT_SLICE: {
                candidate.PROJECT_SLICE,
            },
        }

        for entry, required in expected.items():
            with self.subTest(entry=entry.value):
                closure = candidate._projection_static_closure(
                    entities, entry
                )
                self.assertEqual(set(closure), required)
                self.assertEqual(
                    set(closure).intersection(ENTRIES),
                    {entry},
                )

    def test_missing_and_duplicate_links_fail_closed(self):
        entities = candidate._projection_entities()

        missing = dict(entities)
        del missing[VALUE_EQUAL]
        with self.assertRaises(ValueError):
            candidate._projection_static_closure(
                missing, candidate.PROJECT_EQUAL
            )

        duplicate = dict(entities)
        duplicate[EntityID("test.duplicate.links")] = links(
            candidate.PROJECT_EQUAL,
            another=VALUE_EQUAL,
        )
        with self.assertRaises(ValueError):
            candidate._projection_static_closure(
                duplicate, candidate.PROJECT_EQUAL
            )

        with self.assertRaises(ValueError):
            candidate._projection_static_closure(
                entities, EntityID("test.missing.function")
            )

    def test_independent_authenticated_deployments(self):
        deployments = {}

        for entry in ENTRIES:
            executor, deployment = candidate._projection_deployment(entry)
            executor._check_deployment(deployment)

            self.assertIn(entry, deployment._target.state.values)
            self.assertTrue(deployment.artifacts)

            for artifact in deployment.artifacts.values():
                artifact.verify()
                self.assertEqual(
                    artifact.state_id, deployment.source_state_id
                )
                self.assertEqual(
                    artifact.produced_by,
                    deployment.compiler_generation,
                )

            deployments[entry] = deployment

        self.assertEqual(
            len({d.source_state_id for d in deployments.values()}),
            len(ENTRIES),
        )

        for entry in ENTRIES:
            self.assertIs(
                deployments[entry],
                candidate._projection_deployment(entry)[1],
            )

        self.assertEqual(
            candidate._projection_deployment.cache_info().misses,
            len(ENTRIES),
        )

    def test_public_operations_remain_vm_backed(self):
        inspected = candidate.inspect_projection([1, True])
        self.assertEqual(inspected[:2], ("list", 2))
        self.assertEqual(
            canonical_bytes(inspected[2]),
            canonical_bytes([1, True]),
        )

        self.assertTrue(
            candidate.equal_projection([1, True], [1, True])
        )
        self.assertFalse(
            candidate.equal_projection([1, True], [1, 1])
        )

        # Restore nested paths rather than weakening to tuple indexing.
        self.assertEqual(
            candidate.select_projection(NESTED_VALUE, NESTED_PATH),
            NESTED_RESULT,
        )
        cell = CellDeclaration(IsKind("map"), NESTED_VALUE)
        self.assertEqual(
            candidate.select_projection(
                cell, ("initial",) + NESTED_PATH,
            ),
            NESTED_RESULT,
        )
        relation = Relation(
            "example", {"root": EntityID("root")},
            {"a": [10, 20]},
        )
        self.assertEqual(
            candidate.select_projection(
                relation, ("payload", 0, 1, 1),
            ),
            20,
        )
        self.assertEqual(
            candidate.select_projection(
                AllOf(IsKind("int")),
                ("arguments", 0, 0, "form"),
            ),
            "is_kind",
        )
        with self.assertRaises(LanguageError):
            candidate.select_projection(NESTED_VALUE, ("a",))
        with self.assertRaises(LanguageError):
            candidate.select_projection(cell, ("not_a_field",))

        self.assertEqual(
            candidate.sequence_projection([1, 2, 3], "len"),
            3,
        )
        self.assertEqual(
            canonical_bytes(
                candidate.sequence_projection(
                    [1, 2, 3], "slice", 1, 3
                )
            ),
            canonical_bytes([2, 3]),
        )

    def test_cache_hits_preserve_preflight_and_machine_entry(self):
        original_run = RestrictedExecutor.run
        original_preflight = restricted.preflight
        original_open = machine._open
        runs = []
        preflights = []
        openings = []

        def observe_run(executor, deployment, entry, *args, **kwargs):
            runs.append((executor, deployment, entry))
            return original_run(
                executor, deployment, entry, *args, **kwargs
            )

        def observe_preflight(state, artifacts, entry, policy):
            preflights.append(entry)
            return original_preflight(
                state, artifacts, entry, policy
            )

        def observe_open(activation, args, *rest, **kwargs):
            result = original_open(
                activation, args, *rest, **kwargs
            )
            if activation.entity == candidate.PROJECT_SELECT:
                openings.append(activation.entity)
            return result

        with (
            patch.object(RestrictedExecutor, "run", observe_run),
            patch.object(restricted, "preflight", observe_preflight),
            patch.object(machine, "_open", observe_open),
        ):
            for _ in range(2):
                before = len(openings)
                self.assertEqual(
                    candidate.select_projection(
                        NESTED_VALUE, NESTED_PATH,
                    ),
                    NESTED_RESULT,
                )
                self.assertGreater(len(openings), before)

        self.assertEqual(len(runs), 2)
        self.assertIs(runs[0][0], runs[1][0])
        self.assertIs(runs[0][1], runs[1][1])
        self.assertEqual(
            preflights, [candidate.PROJECT_SELECT] * 2
        )
        self.assertEqual(
            candidate._projection_deployment.cache_info().hits, 1
        )

    def test_invalidation_and_wrong_issuer(self):
        executor, deployment = candidate._projection_deployment(
            candidate.PROJECT_SELECT
        )

        self.assertEqual(
            executor.run(
                deployment, candidate.PROJECT_SELECT,
                NESTED_VALUE, NESTED_PATH, 0
            ),
            NESTED_RESULT,
        )

        with self.assertRaises(AdmissionRejected):
            RestrictedExecutor().run(
                deployment, candidate.PROJECT_SELECT,
                NESTED_VALUE, NESTED_PATH, 0
            )

        executor.invalidate(deployment)

        with patch.object(
            machine, "_open",
            side_effect=AssertionError("unauthorized VM entry"),
        ):
            with self.assertRaises(AdmissionRejected):
                candidate.select_projection(NESTED_VALUE, NESTED_PATH)

        self.assertIs(
            candidate._projection_deployment(
                candidate.PROJECT_SELECT
            )[1],
            deployment,
        )

    def test_artifact_substitution_is_rejected(self):
        executor, deployment = candidate._projection_deployment(
            candidate.PROJECT_SELECT
        )
        store = deployment._artifact_set
        key = next(iter(store._artifacts))
        authentic = store._artifacts[key]

        try:
            store._artifacts[key] = object()

            with patch.object(
                machine, "_open",
                side_effect=AssertionError("unauthorized VM entry"),
            ):
                with self.assertRaises(AdmissionRejected):
                    candidate.select_projection(NESTED_VALUE, NESTED_PATH)
        finally:
            store._artifacts[key] = authentic

        self.assertEqual(
            candidate.select_projection(NESTED_VALUE, NESTED_PATH),
            NESTED_RESULT,
        )

    def test_preflight_denial_is_not_bypassed(self):
        self.assertEqual(
            candidate.select_projection(NESTED_VALUE, NESTED_PATH),
            NESTED_RESULT,
        )

        with (
            patch.object(
                restricted, "preflight",
                side_effect=AdmissionRejected(
                    "injected projection preflight denial"
                ),
            ),
            patch.object(
                machine, "_open",
                side_effect=AssertionError("unauthorized VM entry"),
            ),
        ):
            with self.assertRaisesRegex(
                AdmissionRejected, "injected projection preflight denial"
            ):
                candidate.select_projection(NESTED_VALUE, NESTED_PATH)

    def test_artifact_counts_and_warm_selection_latency(self):
        # Same admitted SHEAR selection function, different deployments.
        full_executor = RestrictedExecutor()
        full_deployment = full_executor.deploy(
            load(program(candidate._projection_entities()))
        )
        full_count = len(full_deployment.artifacts)

        counts = {}
        for entry in ENTRIES:
            executor, deployment = candidate._projection_deployment(entry)
            counts[entry.value] = len(deployment.artifacts)
            self.assertLess(len(deployment.artifacts), full_count)
            executor._check_deployment(deployment)

        value = (1, 2, 3)
        path = (1,)
        minimal_executor, minimal_deployment = (
            candidate._projection_deployment(candidate.PROJECT_SELECT)
        )

        def measure(executor, deployment):
            wall = []
            cpu = []

            for _ in range(5):
                start_wall = perf_counter()
                start_cpu = process_time()
                result = executor.run(
                    deployment, candidate.PROJECT_SELECT,
                    value, path, 0
                )
                cpu.append(process_time() - start_cpu)
                wall.append(perf_counter() - start_wall)
                self.assertEqual(result, 2)

            return median(wall), median(cpu)

        # Warm-ups are excluded from timing.
        for executor, deployment in (
            (full_executor, full_deployment),
            (minimal_executor, minimal_deployment),
        ):
            self.assertEqual(
                executor.run(
                    deployment, candidate.PROJECT_SELECT,
                    value, path, 0
                ),
                2,
            )

        full_wall, full_cpu = measure(
            full_executor, full_deployment
        )
        minimal_wall, minimal_cpu = measure(
            minimal_executor, minimal_deployment
        )

        print(
            "GH-123 PROJECTION METRICS "
            f"full_artifacts={full_count} "
            f"minimal_artifacts={counts} "
            f"full_wall_ms={full_wall * 1000:.3f} "
            f"minimal_wall_ms={minimal_wall * 1000:.3f} "
            f"full_cpu_ms={full_cpu * 1000:.3f} "
            f"minimal_cpu_ms={minimal_cpu * 1000:.3f}",
            flush=True,
        )


if __name__ == "__main__":
    unittest.main()
