"""Task 32 Plan-owned lifecycle and authenticated provenance tests.

Independent adversarial witnesses for in-flight replacement, preparation
failure cleanup, and producer evidence. These tests require Task 32's
unimplemented restricted executor and intentionally fail collection in Plan.
"""

from __future__ import annotations

from dataclasses import replace
import unittest
from unittest import mock

from shear import (
    CellContentRejected, CellDeclaration, EntityID, External, Runtime,
    State, Value,
)
from shear import machine
from shear.examples._support import program
from shear.hosted_bootstrap import AdmissionRejected
from shear.hosted_bootstrap.artifacts import ArtifactSet, TARGET, artifact_id
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from shear.lang import Function, load
from tests.test_restricted_execution import CELL, PRED, PURE_POLICY, evaluator_source

SECOND = EntityID("t32.lifecycle.second")


def two_checks() -> State:
    return State.create({
        CELL: Value.create(CELL, CellDeclaration(External("policy"), 3)),
        SECOND: Value.create(
            SECOND, CellDeclaration(External("policy"), 3),
        ),
    })


def refusal_source() -> State:
    return load(program({
        PRED: Function(("x",), ("lit", "violated")),
    }))


def identified_change(artifact, **changes):
    """Preserve internal hash integrity; challenge trusted provenance."""
    forged = replace(artifact, **changes)
    return replace(forged, artifact_id=artifact_id(
        forged.domain, forged.generation, forged.produced_by,
        forged.state_id, forged.entity, forged.version,
        forged.owner, forged.chunk, forged.reused_from,
    ))


class LifecycleEvidence(unittest.TestCase):
    def setUp(self):
        self.executor = RestrictedExecutor()
        self.source = evaluator_source()
        self.first = self.executor.deploy(
            self.source, compiler_generation=1,
        )

    def test_inflight_replacement_pins_old_execution_and_holds(self):
        second = self.executor.deploy(
            refusal_source(), compiler_generation=1,
        )
        registry = self.executor.registry({
            "policy": (self.first, PRED),
        })
        state = two_checks()
        original_state_id = state.id
        opened = []
        original_open = machine._open

        def observe(activation, args, *rest, **kwargs):
            if activation.entity == PRED:
                version = activation.hold.version
                opened.append((version, activation.hold))
                self.assertIn(activation.hold, version.holds)
                self.assertFalse(activation.hold.released)
                if len(opened) == 1:
                    registry.replace("policy", (second, PRED))
            return original_open(activation, args, *rest, **kwargs)

        with mock.patch.object(machine, "_open", side_effect=observe):
            accepted = Runtime(state, registry.context)

        self.assertEqual(accepted.read(CELL), 3)
        self.assertEqual(accepted.read(SECOND), 3)
        self.assertEqual(state.id, original_state_id)
        self.assertEqual(len(opened), 2)
        self.assertTrue(all(hold.released for _, hold in opened))
        self.assertEqual(
            {version.state.id for version, _ in opened}, {self.source.id},
        )

        with self.assertRaises(CellContentRejected):
            Runtime(state, registry.context)
        self.assertEqual(accepted.read(CELL), 3)
        self.assertEqual(accepted.read(SECOND), 3)

        self.executor.invalidate(self.first)
        with self.assertRaises(AdmissionRejected):
            self.executor.run(self.first, PRED, 3, policy=PURE_POLICY)
        with self.assertRaises(CellContentRejected):
            Runtime(state, registry.context)

    def test_failed_preparation_does_not_leave_admitted_artifacts(self):
        observed = []
        real_admit = ArtifactSet.admit

        def fail_after_admission(artifact_set, artifact):
            real_admit(artifact_set, artifact)
            if artifact.domain == TARGET and artifact.state_id == self.source.id:
                observed.append(artifact_set)
                raise AdmissionRejected("injected preparation failure")

        with mock.patch.object(ArtifactSet, "admit", new=fail_after_admission):
            with self.assertRaisesRegex(
                AdmissionRejected, "injected preparation failure",
            ):
                self.executor.deploy(self.source, compiler_generation=1)

        self.assertTrue(observed, "failure was not injected after admission")
        for artifact_set in observed:
            self.assertFalse(artifact_set.valid)
            self.assertEqual(tuple(artifact_set.artifact_ids()), ())
        self.assertEqual(
            self.executor.run(self.first, PRED, 3, policy=PURE_POLICY),
            "satisfied",
        )

    def test_self_consistent_forged_producer_cannot_run(self):
        """An updated artifact hash does not create compiler authority."""
        from shear.lang import _definition_of

        root = _definition_of(self.source.values[PRED]).body
        observed = []
        real_admit = ArtifactSet.admit

        def forge_producer(artifact_set, artifact):
            if artifact.domain == TARGET and artifact.entity == root:
                observed.append(artifact.entity)
                artifact = identified_change(artifact, produced_by=0)
                artifact.verify()
            return real_admit(artifact_set, artifact)

        other_executor = RestrictedExecutor()
        with mock.patch.object(ArtifactSet, "admit", new=forge_producer):
            try:
                forged = other_executor.deploy(
                    self.source, compiler_generation=1,
                )
            except AdmissionRejected:
                self.assertEqual(observed, [root])
                return

        self.assertEqual(observed, [root])
        with self.assertRaises(AdmissionRejected):
            other_executor.run(forged, PRED, 3, policy=PURE_POLICY)


if __name__ == "__main__":
    unittest.main()
