"""Frozen T9 candidate authority acceptance for SHEAR #123.

The actual candidate's prepare_semantic entry must execute through
Task 32. These tests inject authority failures into that deployment,
not just into Task 32's original example evaluator.

Existing Task 32 adversarial source, bytecode and lifecycle tests
remain mandatory and unchanged.

This module is not discovered by ordinary Plan-time CI.
"""

from dataclasses import replace
from importlib import import_module
import unittest
from unittest.mock import patch

from shear import ConstraintResult, StateID, bytecode, machine
from shear.hosted_bootstrap import AdmissionRejected
from shear.hosted_bootstrap.artifacts import artifact_id
from shear.hosted_bootstrap.restricted import (
    RestrictedDeployment,
    RestrictedExecutor,
    RestrictionPolicy,
)
from shear.hosted_bootstrap.validation import validate_chunk
from shear.lang import _definition_of
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
    no_host_lowering,
)
from tests.test_restricted_execution import (
    CALL_WRITE,
    DEAD_WRITE,
    DYNAMIC,
    NEGATIVE,
    PRED,
    READ,
    WRITE,
    evaluator_source,
)


SAT = "satisfied"
VIO = "violated"
PURE = RestrictionPolicy()


def reidentify(artifact, **changes):
    """Recompute the integrity hash without acquiring authority."""
    forged = replace(artifact, **changes)
    return replace(forged, artifact_id=artifact_id(
        forged.domain,
        forged.generation,
        forged.produced_by,
        forged.state_id,
        forged.entity,
        forged.version,
        forged.owner,
        forged.chunk,
        forged.reused_from,
    ))


def admitted_root(deployment, entry):
    state = deployment._target.state
    root = _definition_of(state.values[entry]).body
    key = (root, state.values[root].version_id)
    return key, deployment.artifacts[key]


class FrozenAuthorityAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.adapter = import_module(
                "tests.constraint_functions_complete_candidate"
            )

        if not callable(
            getattr(cls.adapter, "prepare_semantic", None)
        ):
            raise AssertionError("candidate lacks prepare_semantic")

    def prepared(self):
        with forbid_incumbent():
            executor, deployment, entry = (
                self.adapter.prepare_semantic(
                    ("is_kind", "int"), None, ()
                )
            )

        self.assertIsInstance(executor, RestrictedExecutor)
        self.assertIsInstance(deployment, RestrictedDeployment)

        with candidate_execution_guard(
            frozenset({entry}),
        ) as opened:
            self.assertEqual(
                executor.run(deployment, entry, 5),
                SAT,
            )

        self.assertTrue(opened)
        return executor, deployment, entry

    def assert_rejected_without_vm(self, action):
        with (
            patch.object(
                machine, "_open",
                side_effect=AssertionError(
                    "unauthorized machine execution"
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
            forbid_incumbent(),
        ):
            with self.assertRaises(AdmissionRejected):
                action()

    def test_wrong_issuer_and_invalidation(self):
        executor, deployment, entry = self.prepared()

        other = RestrictedExecutor()
        self.assert_rejected_without_vm(
            lambda: other.run(deployment, entry, 5)
        )

        executor.invalidate(deployment)
        self.assert_rejected_without_vm(
            lambda: executor.run(deployment, entry, 5)
        )

    def test_rehashed_candidate_artifact_cannot_replace_admission(self):
        executor, deployment, entry = self.prepared()
        key, authentic = admitted_root(deployment, entry)
        source = deployment._target.state
        substituted_chunk = (
            ("LIT", VIO),
            ("END",),
        )

        validate_chunk(
            source, key[0], entry, substituted_chunk,
        )

        mutations = (
            ("producer", {
                "produced_by": deployment.compiler_generation + 1,
            }),
            ("state", {
                "state_id": StateID("t123.forged"),
            }),
            ("valid_code_substitution", {
                "chunk": substituted_chunk,
            }),
        )

        store = deployment._artifact_set
        original_artifact = store._artifacts[key]
        original_chunk = store._chunks[key]

        for name, changes in mutations:
            with self.subTest(mutation=name):
                forged = reidentify(authentic, **changes)
                forged.verify()

                self.assertNotEqual(
                    forged.artifact_id,
                    authentic.artifact_id,
                )

                try:
                    store._artifacts[key] = forged
                    store._chunks[key] = forged.chunk

                    self.assert_rejected_without_vm(
                        lambda: executor.run(
                            deployment, entry, 5,
                        )
                    )
                finally:
                    store._artifacts[key] = original_artifact
                    store._chunks[key] = original_chunk

                with candidate_execution_guard(
                    frozenset({entry}),
                ) as opened:
                    self.assertEqual(
                        executor.run(deployment, entry, 5),
                        SAT,
                    )
                self.assertTrue(opened)

    def test_forbidden_effects_and_indirect_calls_fail_closed(self):
        executor, deployment, entry = self.prepared()

        adversarial = executor.deploy(
            evaluator_source(), compiler_generation=1,
        )

        attempts = (
            (READ, ()),
            (WRITE, (9,)),
            (CALL_WRITE, (9,)),
            (DEAD_WRITE, (9,)),
            (DYNAMIC, (PRED,)),
        )

        for forbidden_entry, args in attempts:
            with self.subTest(entry=forbidden_entry.value):
                self.assert_rejected_without_vm(
                    lambda: executor.run(
                        adversarial, forbidden_entry,
                        *args, policy=PURE,
                    )
                )

        with candidate_execution_guard(
            frozenset({entry}),
        ) as opened:
            self.assertEqual(
                executor.run(deployment, entry, 5),
                SAT,
            )
        self.assertTrue(opened)

    def test_replacement_pins_inflight_candidate_selection(self):
        executor, deployment, entry = self.prepared()
        alternative = executor.deploy(
            evaluator_source(), compiler_generation=1,
        )

        registry = executor.registry({
            "policy": (deployment, entry),
        })
        target_state = StateID("t123.target")
        opened = []
        original_open = machine._open

        def observe(activation, args, *rest, **kwargs):
            chunk, env, node = original_open(
                activation, args, *rest, **kwargs,
            )

            if (
                activation.entity == entry
                and activation.hold.version.state.id
                == deployment.source_state_id
            ):
                state = deployment._target.state
                key = (node, state.values[node].version_id)
                artifact = deployment.artifacts[key]

                self.assertIs(chunk, artifact.chunk)
                artifact.verify()
                opened.append((tuple(args), artifact.artifact_id))

                if len(opened) == 1:
                    registry.replace(
                        "policy", (alternative, NEGATIVE)
                    )

            return chunk, env, node

        evaluator = registry.context.externals["policy"]

        with (
            forbid_incumbent(),
            patch.object(machine, "_open", new=observe),
            patch.object(
                bytecode, "lower_value",
                side_effect=no_host_lowering,
            ),
            patch.object(
                bytecode, "chunk_of",
                side_effect=no_host_lowering,
            ),
        ):
            with registry.operation_scope(target_state, "write"):
                first = evaluator.evaluate(5)
                second = evaluator.evaluate(5)

            after = evaluator.evaluate(5)

        self.assertIs(first, ConstraintResult.SATISFIED)
        self.assertIs(second, ConstraintResult.SATISFIED)
        self.assertIs(after, ConstraintResult.VIOLATED)
        self.assertEqual(len(opened), 2)
        self.assertEqual(opened[0][0], (5,))
        self.assertEqual(opened[1][0], (5,))
        self.assertEqual(opened[0][1], opened[1][1])


if __name__ == "__main__":
    unittest.main()
