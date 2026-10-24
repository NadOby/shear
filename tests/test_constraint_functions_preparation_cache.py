"""Non-frozen regressions for GH-123 private evaluator preparation reuse."""

from __future__ import annotations

from collections import defaultdict
from contextlib import ExitStack
from time import perf_counter_ns, process_time_ns
import unittest
from unittest.mock import patch

from shear import machine
from shear.hosted_bootstrap import restricted
from shear.hosted_bootstrap.artifacts import Artifact
from shear.hosted_bootstrap.restricted import (
    AdmissionRejected,
    RestrictedExecutor,
)
from tests.constraint_function_acceptance import CandidateInput
from tests import constraint_functions_complete_candidate as candidate


class SemanticPreparationCacheTests(unittest.TestCase):
    def setUp(self):
        candidate._private_semantic_preparation.cache_clear()

    def tearDown(self):
        candidate._private_semantic_preparation.cache_clear()

    @staticmethod
    def evaluate(expression, budget=None, externals=(), subject=5):
        return candidate.semantic(
            CandidateInput(expression, subject, budget, externals)
        ).outcome

    def test_canonical_all_of_any_of_reuse(self):
        a = ("is_kind", "int")
        b = ("int_range", 0, 9)

        for operation in ("all_of", "any_of"):
            self.assertEqual(
                self.evaluate((operation, a, b), 3),
                "satisfied",
            )
            self.assertEqual(
                self.evaluate((operation, b, a, a), 3),
                "satisfied",
            )

        info = candidate._private_semantic_preparation.cache_info()
        self.assertEqual((info.misses, info.hits), (2, 2))

    def test_distinct_constraints_remain_separate(self):
        self.evaluate(("is_kind", "int"))
        self.evaluate(("is_kind", "bool"))

        self.assertEqual(
            candidate._private_semantic_preparation.cache_info().misses,
            2,
        )

    def test_budget_separation_and_validation(self):
        expression = ("is_kind", "int")

        self.assertEqual(self.evaluate(expression, 0), "unknown")
        self.assertEqual(self.evaluate(expression, 1), "satisfied")
        self.assertEqual(self.evaluate(expression, 1), "satisfied")

        with self.assertRaises(ValueError):
            self.evaluate(expression, True)

        info = candidate._private_semantic_preparation.cache_info()
        self.assertEqual((info.misses, info.hits), (2, 1))

    def test_external_registrations_fail_without_cache_reuse(self):
        self.evaluate(("is_kind", "int"))
        before = candidate._private_semantic_preparation.cache_info()

        with self.assertRaises(NotImplementedError):
            self.evaluate(
                ("is_kind", "int"),
                externals=(("registered", "satisfied"),),
            )

        self.assertEqual(
            candidate._private_semantic_preparation.cache_info(),
            before,
        )

    def test_public_preparation_interception(self):
        expression = ("is_kind", "int")
        self.evaluate(expression)

        prepared = candidate.prepare_semantic(expression, None, ())
        calls = []

        def spy(*args):
            calls.append(args)
            return prepared

        with patch.object(candidate, "prepare_semantic", new=spy):
            self.assertEqual(self.evaluate(expression), "satisfied")

        self.assertEqual(calls, [(expression, None, ())])

    def test_authenticated_runner_and_preflight_on_cache_hits(self):
        original_run = RestrictedExecutor.run
        original_preflight = restricted.preflight
        original_open = machine._open
        runs = []
        preflights = []
        openings = []

        def traced_run(executor, deployment, entry, *args, **kwargs):
            runs.append((executor, deployment, entry))
            return original_run(
                executor, deployment, entry, *args, **kwargs
            )

        def traced_preflight(state, artifacts, entry, policy):
            preflights.append(entry)
            return original_preflight(
                state, artifacts, entry, policy
            )

        def traced_open(activation, args, *rest, **kwargs):
            result = original_open(
                activation, args, *rest, **kwargs
            )
            if activation.entity == candidate.BOUND_ENTRY:
                openings.append(activation.entity)
            return result

        with (
            patch.object(RestrictedExecutor, "run", traced_run),
            patch.object(restricted, "preflight", traced_preflight),
            patch.object(machine, "_open", traced_open),
        ):
            self.assertEqual(
                self.evaluate(("is_kind", "int")), "satisfied"
            )
            self.assertEqual(
                self.evaluate(("is_kind", "int"), subject=True),
                "violated",
            )

        self.assertEqual(len(runs), 2)
        self.assertIs(runs[0][0], runs[1][0])
        self.assertIs(runs[0][1], runs[1][1])
        self.assertEqual(
            preflights, [candidate.BOUND_ENTRY] * 2
        )
        self.assertEqual(
            openings, [candidate.BOUND_ENTRY] * 2
        )
        self.assertEqual(
            candidate._private_semantic_preparation.cache_info().hits,
            1,
        )

    def test_invalidation_and_wrong_issuer(self):
        original_deploy = RestrictedExecutor.deploy
        admitted = []

        def observe(executor, source, **kwargs):
            deployment = original_deploy(executor, source, **kwargs)
            admitted.append((executor, deployment))
            return deployment

        expression = ("is_kind", "int")
        with patch.object(RestrictedExecutor, "deploy", observe):
            self.assertEqual(self.evaluate(expression), "satisfied")

        self.assertEqual(len(admitted), 1)
        issuer, deployment = admitted[0]

        with self.assertRaises(AdmissionRejected):
            RestrictedExecutor().run(
                deployment, candidate.BOUND_ENTRY, 5
            )

        issuer.invalidate(deployment)

        with patch.object(
            machine, "_open",
            side_effect=AssertionError("unauthorized VM entry"),
        ):
            with self.assertRaises(AdmissionRejected):
                self.evaluate(expression)

        self.assertEqual(len(admitted), 1)

    def test_artifact_substitution_is_rejected_on_hit(self):
        original_deploy = RestrictedExecutor.deploy
        admitted = []

        def observe(executor, source, **kwargs):
            deployment = original_deploy(executor, source, **kwargs)
            admitted.append(deployment)
            return deployment

        expression = ("is_kind", "int")
        with patch.object(RestrictedExecutor, "deploy", observe):
            self.evaluate(expression)

        deployment = admitted[0]
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
                    self.evaluate(expression)
        finally:
            store._artifacts[key] = authentic

        self.assertEqual(self.evaluate(expression), "satisfied")

    def test_failed_admission_is_not_cached(self):
        expression = ("is_kind", "int")

        with patch.object(
            RestrictedExecutor, "deploy",
            side_effect=AdmissionRejected("injected admission failure"),
        ):
            with self.assertRaisesRegex(
                AdmissionRejected, "injected admission failure"
            ):
                self.evaluate(expression)

        self.assertEqual(
            candidate._private_semantic_preparation.cache_info().currsize,
            0,
        )
        self.assertEqual(self.evaluate(expression), "satisfied")

    def test_authenticated_evaluator_cost_profile(self):
        """Measure warm execution stages without changing their behavior.

        Timings are diagnostic, not acceptance thresholds. Nested stage
        times overlap and must not be summed as independent costs.
        """
        expression = (
            "all_of",
            ("is_kind", "int"),
            ("int_range", 0, 10),
        )
        budget = 3
        repeats = 8

        # Populate the genuine private cache before instrumenting.
        self.assertEqual(
            self.evaluate(expression, budget), "satisfied"
        )
        normalized = candidate._constraint(expression)
        executor, deployment, entry = (
            candidate._private_semantic_preparation(
                normalized,
                budget,
                candidate._PRIVATE_COMPILER_GENERATION,
                (),
                candidate._PRIVATE_SEMANTIC_AUTHORITY,
            )
        )
        self.assertIsInstance(executor, RestrictedExecutor)
        self.assertEqual(entry, candidate.BOUND_ENTRY)
        artifact_count = len(deployment.artifacts)
        hits_before = (
            candidate._private_semantic_preparation.cache_info().hits
        )

        timings = defaultdict(list)
        verified = [0]

        def timed(name, original):
            def measured(*args, **kwargs):
                start_wall = perf_counter_ns()
                start_cpu = process_time_ns()
                try:
                    return original(*args, **kwargs)
                finally:
                    timings[name].append((
                        perf_counter_ns() - start_wall,
                        process_time_ns() - start_cpu,
                    ))
            return measured

        original_verify = Artifact.verify

        def counted_verify(artifact):
            verified[0] += 1
            return original_verify(artifact)

        targets = (
            ("normalize", candidate, "_constraint"),
            (
                "cache_lookup",
                candidate,
                "_private_semantic_preparation",
            ),
            (
                "authenticate",
                RestrictedExecutor,
                "_check_deployment",
            ),
            ("preflight", restricted, "preflight"),
            ("machine", machine, "run"),
            (
                "resolver",
                restricted._PinnedResolver,
                "for_version",
            ),
        )

        overall = []
        with ExitStack() as stack:
            for name, owner, attribute in targets:
                original = getattr(owner, attribute)
                stack.enter_context(
                    patch.object(
                        owner, attribute, timed(name, original)
                    )
                )
            stack.enter_context(
                patch.object(
                    Artifact, "verify", counted_verify
                )
            )

            for index in range(repeats):
                subject = 5 if index % 2 == 0 else True
                expected = (
                    "satisfied" if index % 2 == 0 else "violated"
                )
                start_wall = perf_counter_ns()
                start_cpu = process_time_ns()
                outcome = self.evaluate(
                    expression, budget, subject=subject
                )
                overall.append((
                    perf_counter_ns() - start_wall,
                    process_time_ns() - start_cpu,
                ))
                self.assertEqual(outcome, expected)

        self.assertEqual(
            candidate._private_semantic_preparation.cache_info().hits
            - hits_before,
            repeats,
        )
        for stage in (
            "normalize", "cache_lookup", "authenticate",
            "preflight", "machine",
        ):
            self.assertEqual(
                len(timings[stage]), repeats, stage
            )
        self.assertGreater(len(timings["resolver"]), 0)
        self.assertGreater(verified[0], 0)

        def measurements(samples):
            return (
                round(
                    sum(item[0] for item in samples)
                    / repeats / 1_000_000,
                    3,
                ),
                round(
                    sum(item[1] for item in samples)
                    / repeats / 1_000_000,
                    3,
                ),
            )

        print(
            "GH-123 EVALUATOR PROFILE "
            f"artifacts={artifact_count} "
            f"invocations={repeats} "
            f"verify_calls={verified[0]} "
            f"resolver_calls={len(timings['resolver'])} "
            "units=ms_per_invocation "
            "timings_are_inclusive",
            flush=True,
        )
        print(
            f"GH-123 PROFILE total_wall_cpu={measurements(overall)}",
            flush=True,
        )
        for name, _, _ in targets:
            print(
                f"GH-123 PROFILE {name}_wall_cpu="
                f"{measurements(timings[name])}",
                flush=True,
            )


if __name__ == "__main__":
    unittest.main()
