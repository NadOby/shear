"""Candidate adapter-to-machine binding acceptance for SHEAR #123.

Execute supplies prepare_semantic(expression, budget, externals) and
semantic(CandidateInput). The harness prepares a subject-independent
admitted evaluator, then forces semantic() to use that exact preparation.

This proves concrete binding for fixed witnesses, not universal absence
of hidden Python fallback. Independent source-path audit is mandatory.
Not discovered by ordinary Plan-time CI.
"""

from contextlib import ExitStack
from importlib import import_module
import unittest
from unittest.mock import patch

from shear import bytecode, canonicalize, canonical_serialize, machine
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from tests.constraint_function_acceptance import (
    CandidateInput,
    Observation,
    ROUTES,
)
from tests.constraint_functions_complete_acceptance import (
    forbid_incumbent,
    no_host_lowering,
)

SAT = "satisfied"
VIO = "violated"

# Freeze both semantic expression and the subject independently.
# Each pair must be run against exactly the same admitted deployment.
WITNESSES = (
    (("is_kind", "int"), 5, SAT),
    (("is_kind", "int"), True, VIO),
    (("int_range", 0, 10), 7, SAT),
    (("int_range", 0, 10), 11, VIO),
    (("length", 2, 2), "e\u0301", SAT),
    (("one_of", (1, "a")), "a", SAT),
    (("one_of", (1, "a")), True, VIO),
    (("not", ("is_kind", "int")), "x", SAT),
    (("role", "x", ("is_kind", "int")), {"x": 5}, SAT),
    (("all_of", ("is_kind", "int"),
      ("int_range", 0, 10)), 5, SAT),
    (("any_of", ("is_kind", "bool"),
      ("int_range", 0, 10)), "x", VIO),
)


def canonical_bytes(value):
    return canonical_serialize(canonicalize(value))


class CandidateBindingAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.adapter = import_module(
                "tests.constraint_functions_complete_candidate"
            )
        for name in ("prepare_semantic", "semantic"):
            if not callable(getattr(cls.adapter, name, None)):
                raise AssertionError(f"candidate lacks {name}")

    def evaluate_bound(self, expression, subject, expected, forced=None):
        # Preparation is outside the measured evaluation interval.
        # No subject or expected result is given to prepare_semantic.
        with forbid_incumbent():
            executor, deployment, entry = self.adapter.prepare_semantic(
                expression, None, ()
            )
        self.assertIsInstance(executor, RestrictedExecutor)
        prepared = (executor, deployment, entry)
        expected_arg = canonical_bytes(subject)
        native_restricted = RestrictedExecutor.run
        native_machine_run = machine.run
        native_open = machine._open
        prepared_calls = []
        restricted_calls = []
        machine_calls = []
        opened = []
        active = []

        def prepared_spy(*args, **kwargs):
            self.assertEqual(args, (expression, None, ()))
            self.assertEqual(kwargs, {})
            prepared_calls.append(args)
            return prepared

        def open_spy(activation, args, *rest, **kwargs):
            chunk, env, node = native_open(
                activation, args, *rest, **kwargs
            )
            self.assertTrue(active, "unrestricted VM entry")
            self.assertEqual(
                activation.hold.version.state.id,
                deployment.source_state_id,
            )
            state = deployment._target.state
            key = (node, state.values[node].version_id)
            artifact = deployment.artifacts.get(key)
            self.assertIsNotNone(artifact)
            self.assertIs(chunk, artifact.chunk)
            self.assertEqual(artifact.entity, node)
            self.assertEqual(artifact.version, key[1])
            self.assertEqual(artifact.owner, activation.entity)
            self.assertEqual(artifact.state_id, state.id)
            self.assertEqual(
                artifact.produced_by, deployment.compiler_generation
            )
            artifact.verify()
            if activation.entity == entry:
                opened.append((node, artifact.artifact_id))
            return chunk, env, node

        def machine_spy(runtime, selected, *args, **kwargs):
            self.assertTrue(active, "machine.run outside restricted runner")
            self.assertIs(runtime, deployment._target.runtime)
            self.assertEqual(selected, entry)
            self.assertEqual(len(args), 1)
            self.assertEqual(canonical_bytes(args[0]), expected_arg)
            self.assertIsNotNone(kwargs.get("resolver"))
            self.assertIs(kwargs.get("may_activate"), False)
            machine_calls.append((selected, args))
            return native_machine_run(runtime, selected, *args, **kwargs)

        def restricted_spy(self_executor, selected_deployment,
                           selected_entry, *args, **kwargs):
            self.assertIs(self_executor, executor)
            self.assertIs(selected_deployment, deployment)
            self.assertEqual(selected_entry, entry)
            self.assertEqual(len(args), 1)
            self.assertEqual(canonical_bytes(args[0]), expected_arg)
            restricted_calls.append((selected_entry, args))
            active.append(True)
            try:
                outcome = native_restricted(
                    self_executor, selected_deployment,
                    selected_entry, *args, **kwargs
                )
                self.assertEqual(outcome, expected)
                if forced is not None:
                    return forced
                return outcome
            finally:
                active.pop()

        case = CandidateInput(expression, subject, None, ())
        with ExitStack() as stack:
            stack.enter_context(forbid_incumbent())
            stack.enter_context(patch.object(
                self.adapter, "prepare_semantic", new=prepared_spy
            ))
            stack.enter_context(patch.object(
                RestrictedExecutor, "run", new=restricted_spy
            ))
            stack.enter_context(patch.object(
                machine, "run", new=machine_spy
            ))
            stack.enter_context(patch.object(
                machine, "_open", new=open_spy
            ))
            stack.enter_context(patch.object(
                bytecode, "chunk_of", side_effect=no_host_lowering
            ))
            stack.enter_context(patch.object(
                bytecode, "lower_value", side_effect=no_host_lowering
            ))
            observed = self.adapter.semantic(case)

        self.assertEqual(len(prepared_calls), 1)
        self.assertEqual(len(restricted_calls), 1)
        self.assertEqual(len(machine_calls), 1)
        self.assertTrue(opened, "selected admitted evaluator was not opened")
        self.assertIsInstance(observed, Observation)
        self.assertIn(observed.route, ROUTES)
        self.assertEqual(observed.incumbent_calls, 0)
        return observed.outcome

    def test_selected_expression_and_subject_control_result(self):
        for expression, subject, expected in WITNESSES:
            with self.subTest(expression=expression, subject=repr(subject)):
                self.assertEqual(
                    self.evaluate_bound(expression, subject, expected),
                    expected,
                )

    def test_valid_verdict_perturbation_reaches_observation(self):
        for expression, subject, expected in WITNESSES:
            with self.subTest(expression=expression, subject=repr(subject)):
                alternative = VIO if expected == SAT else SAT
                self.assertEqual(
                    self.evaluate_bound(
                        expression, subject, expected, forced=alternative,
                    ),
                    alternative,
                )


if __name__ == "__main__":
    unittest.main()
