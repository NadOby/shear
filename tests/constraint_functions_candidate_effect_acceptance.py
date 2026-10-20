"""Candidate-specific effect isolation for SHEAR #123.

Unlike the Task 32 generic security regressions, both probes
target the actual candidate-generated evaluator or its dispatch.

Plan-owned: outside ordinary discovery until Execute.
"""

from importlib import import_module
import unittest
from unittest.mock import patch

from shear import bytecode, machine
from shear.hosted_bootstrap import AdmissionRejected
from shear.hosted_bootstrap import restricted
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from shear.lang import Function, _definition_of, define
from tests.constraint_function_acceptance import CandidateInput
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
    no_host_lowering,
)


class CandidateEffectIsolationAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.adapter = import_module(
                "tests.constraint_functions_complete_candidate"
            )

        cls.entries = cls.adapter.EVALUATOR_ENTRIES
        for name in ("prepare_semantic", "semantic"):
            if not callable(getattr(cls.adapter, name, None)):
                raise AssertionError(f"candidate lacks {name}")

    def test_candidate_derived_dynamic_dispatch_fails_closed(self):
        with forbid_incumbent():
            executor, deployment, entry = (
                self.adapter.prepare_semantic(
                    ("is_kind", "int"), None, ()
                )
            )

        source = deployment._target.state
        definition = _definition_of(source.values[entry])
        self.assertEqual(len(definition.params), 1)

        # Replace the actual candidate entry's body, not an
        # unrelated Task 32 stock example.
        parameter = definition.params[0]
        hostile = define(source, {
            entry: Function(
                definition.params,
                ("apply", ("arg", parameter), ("lit", 5)),
            ),
        }).destination

        self.assertNotEqual(hostile.id, source.id)
        self.assertIn(entry, hostile.values)

        adversarial_executor = RestrictedExecutor()
        adversarial = adversarial_executor.deploy(
            hostile, compiler_generation=1,
        )

        before = tuple(
            (key, artifact.artifact_id)
            for key, artifact in adversarial.artifacts.items()
        )

        with (
            forbid_incumbent(),
            patch.object(
                machine, "_open",
                side_effect=AssertionError(
                    "unauthorized candidate code executed"
                ),
            ),
            patch.object(
                bytecode, "lower_value",
                side_effect=no_host_lowering,
            ),
            patch.object(
                bytecode, "chunk_of",
                side_effect=no_host_lowering,
            ),
        ):
            with self.assertRaises(AdmissionRejected):
                adversarial_executor.run(
                    adversarial, entry, 5,
                )

        self.assertEqual(
            tuple(
                (key, artifact.artifact_id)
                for key, artifact in adversarial.artifacts.items()
            ),
            before,
        )

        # Denying the modified candidate must not damage the
        # original authenticated evaluator.
        with candidate_execution_guard(
            frozenset({entry}),
        ) as opened:
            self.assertEqual(
                executor.run(deployment, entry, 5),
                "satisfied",
            )
        self.assertTrue(opened)

    def test_candidate_adapter_cannot_bypass_preflight_denial(self):
        actual_preflight = restricted.preflight
        rejected_entries = []

        def deny_candidate(state, artifacts, entry, policy):
            if entry in self.entries:
                rejected_entries.append(entry)
                raise AdmissionRejected(
                    "injected candidate preflight denial"
                )
            return actual_preflight(
                state, artifacts, entry, policy,
            )

        with (
            forbid_incumbent(),
            patch.object(
                restricted, "preflight",
                new=deny_candidate,
            ),
            patch.object(
                machine, "_open",
                side_effect=AssertionError(
                    "candidate bypassed rejected preflight"
                ),
            ),
            patch.object(
                bytecode, "lower_value",
                side_effect=no_host_lowering,
            ),
            patch.object(
                bytecode, "chunk_of",
                side_effect=no_host_lowering,
            ),
        ):
            with self.assertRaisesRegex(
                AdmissionRejected,
                "injected candidate preflight denial",
            ):
                self.adapter.semantic(
                    CandidateInput(
                        ("is_kind", "int"), 5, None, (),
                    )
                )

        self.assertTrue(
            rejected_entries,
            "candidate never reached restricted preflight",
        )


if __name__ == "__main__":
    unittest.main()
