"""Task 32 Plan-owned lifecycle and authenticated authority tests.

Adversarial records retain valid content hashes and are tested at the
original authenticated lookup key. Rejection must not be explained merely
by checksum failure or a missing dictionary key.
"""

from __future__ import annotations

from dataclasses import replace
import unittest
from unittest import mock

from shear import (
    CellContentRejected, CellDeclaration, EntityID, External, Runtime,
    State, StateID, Value, VersionID,
)
from shear import machine
from shear.examples._support import program
from shear.hosted_bootstrap import AdmissionRejected
from shear.hosted_bootstrap.artifacts import ArtifactSet, TARGET, artifact_id
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from shear.hosted_bootstrap.validation import validate_chunk
from shear.lang import Function, _definition_of, load
from tests.test_restricted_execution import (
    CELL, PRED, PURE, PURE_POLICY, evaluator_source,
)

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
    """Rehash changed authority fields; checksum rejection is insufficient."""
    forged = replace(artifact, **changes)
    forged = replace(forged, artifact_id=artifact_id(
        forged.domain, forged.generation, forged.produced_by,
        forged.state_id, forged.entity, forged.version,
        forged.owner, forged.chunk, forged.reused_from,
    ))
    forged.verify()
    return forged


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

    def test_replacement_and_explicit_invalidation_preserve_new_authority(self):
        second = self.executor.deploy(
            refusal_source(), compiler_generation=1,
        )
        registry = self.executor.registry({
            "policy": (self.first, PRED),
        })
        before = two_checks().id
        registry.replace("policy", (second, PRED))
        with self.assertRaises(CellContentRejected):
            Runtime(two_checks(), registry.context)
        self.assertEqual(two_checks().id, before)

        self.executor.invalidate(self.first)
        with self.assertRaises(AdmissionRejected):
            self.executor.run(self.first, PRED, 3, policy=PURE_POLICY)
        self.assertEqual(
            self.executor.run(second, PRED, 3, policy=PURE_POLICY),
            "violated",
        )
        # In-flight retention is covered above; D5 covers version retirement.

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

    def test_rehashed_forgery_cannot_gain_restricted_execution_authority(self):
        """A forged record at the *original* key must never execute.

        Distinguish authentication from lookup failure: the replacement is
        stored under the genuine node/version key. Also accept an immutable
        deployment that demonstrably kept the authentic record instead.
        """
        root = _definition_of(self.source.values[PRED]).body
        key = (root, self.source.values[root].version_id)
        valid_replacement = (("LIT", "violated"), ("END",))
        validate_chunk(self.source, root, PRED, valid_replacement)
        original = self.first.artifacts[key]
        unrelated = next(
            item.artifact_id for item in self.first.artifacts.values()
            if item.entity != root
        )
        self.assertNotEqual(unrelated, original.artifact_id)
        variations = (
            ("source state", {"state_id": StateID("t32.forced-state")}),
            ("code node", {"entity": PURE}),
            ("node version", {"version": VersionID("t32.forced-version")}),
            ("code owner", {"owner": PURE}),
            ("compiler producer", {"produced_by": 2}),
            ("wrong real reuse parent", {"reused_from": unrelated}),
            ("substituted valid chunk", {"chunk": valid_replacement}),
        )
        real_admit = ArtifactSet.admit

        for name, changes in variations:
            with self.subTest(name=name):
                injected = []

                def substitute(artifact_set, artifact):
                    real_admit(artifact_set, artifact)
                    if (
                        artifact.domain == TARGET
                        and artifact.state_id == self.source.id
                        and artifact.entity == root
                    ):
                        forged = identified_change(artifact, **changes)
                        # Deliberately retain the original lookup key; using
                        # ArtifactSet.admit(forged) could trivially miss it.
                        authentic_key = (artifact.entity, artifact.version)
                        self.assertEqual(authentic_key, key)
                        artifact_set._artifacts[authentic_key] = forged
                        artifact_set._chunks[authentic_key] = forged.chunk
                        injected.append((artifact, forged))

                other = RestrictedExecutor()
                with mock.patch.object(ArtifactSet, "admit", new=substitute):
                    try:
                        deployment = other.deploy(
                            self.source, compiler_generation=1,
                        )
                    except AdmissionRejected:
                        self.assertEqual(len(injected), 1)
                        continue

                self.assertEqual(len(injected), 1, "forgery not injected")
                authentic, forged = injected[0]
                self.assertEqual(authentic.artifact_id, original.artifact_id)
                self.assertNotEqual(authentic.artifact_id, forged.artifact_id)
                forged.verify()

                actual = deployment.artifacts[key]
                if actual is authentic:
                    # A detached immutable deployment snapshot is also safe,
                    # provided execution actually uses its original chunk.
                    opened = []
                    old_open = machine._open

                    def observe(activation, args, *rest, **kwargs):
                        result = old_open(activation, args, *rest, **kwargs)
                        if activation.entity == PRED:
                            opened.append(result[0])
                        return result

                    with mock.patch.object(machine, "_open", side_effect=observe):
                        try:
                            answer = other.run(
                                deployment, PRED, 3, policy=PURE_POLICY,
                            )
                        except AdmissionRejected:
                            self.assertEqual(opened, [])
                        else:
                            self.assertEqual(answer, "satisfied")
                            self.assertTrue(opened)
                            self.assertIs(opened[0], authentic.chunk)
                else:
                    self.assertIs(actual, forged)
                    with self.assertRaises(AdmissionRejected):
                        other.run(deployment, PRED, 3, policy=PURE_POLICY)


if __name__ == "__main__":
    unittest.main()
