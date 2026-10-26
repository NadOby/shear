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
        candidate._private_registered_preparation.cache_clear()

    def tearDown(self):
        candidate._private_semantic_preparation.cache_clear()
        candidate._private_registered_preparation.cache_clear()

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
                self.evaluate((operation, a, b), 3), "satisfied"
            )
            self.assertEqual(
                self.evaluate((operation, b, a, a), 3), "satisfied"
            )

        info = candidate._private_semantic_preparation.cache_info()
        self.assertEqual((info.misses, info.hits), (1, 3))

    def test_distinct_constraints_share_code_but_not_verdicts(self):
        self.assertEqual(
            self.evaluate(("is_kind", "int")), "satisfied"
        )
        self.assertEqual(
            self.evaluate(("is_kind", "bool")), "violated"
        )

        info = candidate._private_semantic_preparation.cache_info()
        self.assertEqual((info.misses, info.hits), (1, 1))
        self.assertEqual(info.currsize, 1)

    def test_budget_is_a_runtime_operand_and_validation_precedes_cache(self):
        expression = ("is_kind", "int")

        self.assertEqual(self.evaluate(expression, 0), "unknown")
        self.assertEqual(self.evaluate(expression, 1), "satisfied")
        self.assertEqual(self.evaluate(expression, 1), "satisfied")

        before = candidate._private_semantic_preparation.cache_info()
        self.assertEqual((before.misses, before.hits), (1, 2))

        with self.assertRaises(ValueError):
            self.evaluate(expression, True)

        self.assertEqual(
            candidate._private_semantic_preparation.cache_info(),
            before,
        )

    def test_external_registrations_use_distinct_authorized_deployments(self):
        expression = ("external", "registered")
        satisfied = (("registered", "satisfied"),)
        violated = (("registered", "violated"),)

        self.assertEqual(
            self.evaluate(("is_kind", "int")), "satisfied"
        )
        ordinary_before = (
            candidate._private_semantic_preparation.cache_info()
        )

        self.assertEqual(
            self.evaluate(expression, externals=satisfied),
            "satisfied",
        )
        self.assertEqual(
            self.evaluate(expression, externals=satisfied),
            "satisfied",
        )
        self.assertEqual(
            self.evaluate(("not", expression), externals=satisfied),
            "violated",
        )
        self.assertEqual(
            self.evaluate(expression, externals=violated),
            "violated",
        )
        self.assertEqual(
            self.evaluate(expression, externals=()),
            "unknown",
        )

        # The common generic deployment cache also owns the empty
        # registration entry used by ordinary semantic evaluation.
        registered = candidate._private_registered_preparation.cache_info()
        self.assertEqual((registered.misses, registered.hits), (3, 2))
        self.assertEqual(registered.currsize, 3)

        ordinary = candidate._private_semantic_preparation.cache_info()
        self.assertEqual(ordinary.misses, ordinary_before.misses)
        self.assertEqual(ordinary.hits, ordinary_before.hits + 1)

        with self.assertRaises(ValueError):
            self.evaluate(
                expression,
                externals=(("registered", "invalid"),),
            )

        self.assertEqual(
            candidate._private_registered_preparation.cache_info(),
            registered,
        )

    def test_registered_external_cache_retains_admission_authority(self):
        expression = ("external", "policy")
        registrations = (("policy", "satisfied"),)

        self.assertEqual(
            self.evaluate(expression, externals=registrations),
            "satisfied",
        )

        executor, deployment, entry = (
            candidate._private_registered_preparation(
                candidate._constraint(expression),
                None,
                registrations,
                candidate._PRIVATE_COMPILER_GENERATION,
                candidate._PRIVATE_SEMANTIC_AUTHORITY,
            )
        )

        with self.assertRaises(AdmissionRejected):
            RestrictedExecutor().run(deployment, entry, 5)

        with self.assertRaises(ValueError):
            candidate._private_registered_preparation(
                candidate._constraint(expression),
                None,
                registrations,
                candidate._PRIVATE_COMPILER_GENERATION,
                object(),
            )

        executor.invalidate(deployment)

        with patch.object(
            machine, "_open",
            side_effect=AssertionError("unauthorized VM entry"),
        ):
            with self.assertRaises(AdmissionRejected):
                self.evaluate(expression, externals=registrations)

        self.assertEqual(
            candidate._private_registered_preparation.cache_info().misses,
            2,
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

    def test_actual_semantic_path_binds_all_nine_forms_to_admitted_vm(self):
        """Bind normal execution, not the monkeypatched public preparation.

        The frozen binding suite intentionally intercepts prepare_semantic,
        selecting a separate bound evaluator. This non-frozen discriminator
        inspects the unmodified production-like semantic() branch instead.
        """
        from shear import canonical_serialize, canonicalize
        from tests.constraint_functions_complete_acceptance import (
            candidate_execution_guard,
        )

        witnesses = (
            (("is_kind", "int"), 5, None, (), "satisfied"),
            (("int_range", 0, 10), 5, None, (), "satisfied"),
            (("length", 2, 2), (5, 6), None, (), "satisfied"),
            (("one_of", (5, 6)), 5, None, (), "satisfied"),
            (("all_of", ("is_kind", "int"),
              ("int_range", 0, 10)), 5, None, (), "satisfied"),
            (("any_of", ("is_kind", "bool"),
              ("int_range", 0, 10)), 5, None, (), "satisfied"),
            (("not", ("is_kind", "bool")), 5, None, (), "satisfied"),
            (("role", "x", ("is_kind", "int")),
             {"x": 5}, None, (), "satisfied"),
            (("external", "missing"), 5, None, (), "unknown"),
            (("external", "policy"), 5, None,
             (("policy", "violated"),), "violated"),
            (("not", ("is_kind", "bool")), 5, 1, (), "unknown"),
        )
        native_run = RestrictedExecutor.run
        native_ordinary = candidate._private_semantic_preparation
        native_registered = candidate._private_registered_preparation

        def identity(value):
            return canonical_serialize(canonicalize(value))

        for expression, subject, budget, registrations, expected in witnesses:
            with self.subTest(expression=expression, budget=budget,
                              registrations=registrations):
                # Do not patch prepare_semantic: that would replace the
                # evaluator under test before reaching these discriminators.
                self.assertIs(
                    candidate.prepare_semantic,
                    candidate._ORIGINAL_PREPARE_SEMANTIC,
                )
                preparations = []
                invocations = []

                def ordinary_spy(*args):
                    preparations.append(("ordinary", args))
                    return native_ordinary(*args)

                def registered_spy(*args):
                    preparations.append(("registered", args))
                    return native_registered(*args)

                def run_spy(executor, deployment, entry, *args, **kwargs):
                    if entry == candidate.REGISTERED_ENTRY:
                        invocations.append((executor, deployment, args))
                    return native_run(
                        executor, deployment, entry, *args, **kwargs,
                    )

                with (
                    patch.object(candidate, "_private_semantic_preparation",
                                 ordinary_spy),
                    patch.object(candidate, "_private_registered_preparation",
                                 registered_spy),
                    patch.object(RestrictedExecutor, "run", run_spy),
                    candidate_execution_guard(
                        frozenset({candidate.REGISTERED_ENTRY})
                    ) as opened,
                ):
                    result = candidate.semantic(CandidateInput(
                        expression, subject, budget, registrations,
                    ))

                self.assertEqual(result.outcome, expected)
                self.assertEqual(result.incumbent_calls, 0)
                self.assertTrue(opened, "normal path bypassed admitted code")
                self.assertEqual(
                    opened[-1][1], candidate.REGISTERED_ENTRY,
                )
                self.assertEqual(len(preparations), 1)
                self.assertEqual(len(invocations), 1)
                kind, prepared = preparations[0]
                self.assertEqual(
                    kind, "registered" if registrations else "ordinary",
                )
                self.assertEqual(identity(prepared[0]), identity(
                    candidate._constraint(expression)
                ))
                self.assertEqual(prepared[1], budget)
                self.assertIs(
                    prepared[-1], candidate._PRIVATE_SEMANTIC_AUTHORITY,
                )
                if registrations:
                    self.assertEqual(prepared[2], registrations)
                    self.assertEqual(
                        prepared[3], candidate._PRIVATE_COMPILER_GENERATION,
                    )
                else:
                    self.assertEqual(
                        prepared[2], candidate._PRIVATE_COMPILER_GENERATION,
                    )
                    self.assertEqual(prepared[3], ())

                executor, deployment, arguments = invocations[0]
                self.assertIsInstance(executor, RestrictedExecutor)
                self.assertIsNotNone(deployment.source_state_id)
                self.assertEqual(len(arguments), 4)
                self.assertEqual(identity(arguments[0]), identity(subject))
                self.assertEqual(identity(arguments[1]), identity(
                    candidate._constraint(expression)
                ))
                self.assertEqual(arguments[2], budget)
                self.assertEqual(arguments[3], registrations)

                alternative = (
                    "violated" if expected == "satisfied" else "satisfied"
                )
                with candidate_execution_guard(
                    frozenset({candidate.REGISTERED_ENTRY}),
                    forced=alternative,
                ) as forced_opened:
                    forced_result = candidate.semantic(CandidateInput(
                        expression, subject, budget, registrations,
                    ))
                self.assertTrue(forced_opened)
                self.assertEqual(forced_result.outcome, alternative)

    def test_broken_normal_preparation_cannot_pass_as_public_binding(self):
        """A failure in the real private preparation must escape unchanged."""
        sentinel = RuntimeError("normal preparation disabled")
        with patch.object(
            candidate, "_private_semantic_preparation",
            side_effect=sentinel,
        ):
            with self.assertRaises(RuntimeError) as observed:
                self.evaluate(("is_kind", "int"))
        self.assertIs(observed.exception, sentinel)

    def test_authenticated_runner_and_preflight_on_cache_hits(self):
        original_run = RestrictedExecutor.run
        original_preflight = restricted.preflight
        original_open = machine._open
        runs = []
        preflights = []
        openings = []

        def traced_run(executor, deployment, entry, *args, **kwargs):
            runs.append((executor, deployment, entry, args))
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
            if activation.entity == candidate.REGISTERED_ENTRY:
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
                self.evaluate(("is_kind", "bool")), "violated"
            )
            self.assertEqual(
                self.evaluate(("is_kind", "int"), budget=0),
                "unknown",
            )
            self.assertEqual(
                self.evaluate(
                    ("is_kind", "int"), budget=1, subject=True
                ),
                "violated",
            )

        self.assertEqual(len(runs), 4)
        self.assertTrue(all(
            run[0] is runs[0][0] and run[1] is runs[0][1]
            for run in runs
        ))
        self.assertEqual(
            [run[2] for run in runs],
            [candidate.REGISTERED_ENTRY] * 4,
        )
        self.assertEqual(
            [run[3][0] for run in runs],
            [5, 5, 5, True],
        )
        self.assertEqual(
            [run[3][1] for run in runs],
            [
                candidate._constraint(("is_kind", "int")),
                candidate._constraint(("is_kind", "bool")),
                candidate._constraint(("is_kind", "int")),
                candidate._constraint(("is_kind", "int")),
            ],
        )
        self.assertEqual(
            [run[3][2] for run in runs],
            [None, None, 0, 1],
        )
        self.assertEqual(
            [run[3][3] for run in runs],
            [()] * 4,
        )
        self.assertEqual(
            preflights, [candidate.REGISTERED_ENTRY] * 4,
        )
        self.assertEqual(
            openings, [candidate.REGISTERED_ENTRY] * 4,
        )
        info = candidate._private_semantic_preparation.cache_info()
        self.assertEqual((info.misses, info.hits), (1, 3))

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
                deployment, candidate.REGISTERED_ENTRY,
                5, candidate._constraint(expression), None, (),
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
        self.assertEqual(entry, candidate.REGISTERED_ENTRY)
        artifact_count = len(deployment.artifacts)
        hits_before = (
            candidate._private_semantic_preparation.cache_info().hits
        )

        timings = defaultdict(list)
        verified = [0]
        normalization_depth = [0]

        def timed(name, original):
            def measured(*args, **kwargs):
                if name == "normalize":
                    normalization_depth[0] += 1
                    outermost = normalization_depth[0] == 1
                else:
                    outermost = True

                if outermost:
                    start_wall = perf_counter_ns()
                    start_cpu = process_time_ns()

                try:
                    return original(*args, **kwargs)
                finally:
                    if name == "normalize":
                        normalization_depth[0] -= 1
                    if outermost:
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
