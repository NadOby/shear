"""Independent Task 32 boundary and anti-fallback tests – GH-119.

Inspect actual machine execution and existing admitted-artifact machinery.
These Plan-owned tests are intentionally red before restricted execution exists.
"""

from __future__ import annotations

from dataclasses import replace
import unittest
from unittest import mock

from shear import (
    ActivationRejected,
    CellDeclaration,
    EntityID,
    External,
    IsKind,
    Relation,
    RelationConstraintRejected,
    Runtime,
    State,
    Value,
    transform_with_mapping,
)
from shear import bytecode, machine
from shear.hosted_bootstrap import AdmissionRejected
from shear.hosted_bootstrap.artifacts import (
    ArtifactSet,
    artifact_id,
)
from shear.hosted_bootstrap.restricted import (
    RestrictedExecutor,
    RestrictionPolicy,
)
from shear.lang import load
from tests.test_restricted_execution import (
    CALL_WRITE,
    CELL,
    DEAD_WRITE,
    DYNAMIC,
    PRED,
    PURE,
    PURE_POLICY,
    READ,
    READ_POLICY,
    RELATION,
    ROLE_PRED,
    WRITE,
    evaluator_source,
    no_host_lowering,
    relation_state,
    snapshot,
)


def permissive_relation_state() -> State:
    """The original relation accepts any canonical role map."""
    return State.create({
        CELL: Value.create(
            CELL, CellDeclaration(IsKind("int"), 3),
        ),
        RELATION: Value.create(
            RELATION,
            Relation("policy", {"item": CELL}, IsKind("map")),
        ),
    })


def narrowed_relation(source):
    """Introduce an External requirement without changing the cell."""
    return transform_with_mapping(
        source,
        {
            RELATION: Relation(
                "policy", {"item": CELL}, External("policy"),
            ),
        },
        {CELL: CELL},
    )


def artifact_snapshot(deployment):
    """Record authoritative admitted bindings, not implementation traces."""
    return (
        deployment.source_state_id,
        deployment.compiler_generation,
        tuple(sorted(
            (
                node.value,
                version.value,
                artifact.artifact_id,
                artifact.state_id,
                artifact.entity,
                artifact.version,
                artifact.owner,
                artifact.generation,
                artifact.produced_by,
                artifact.chunk,
                artifact.reused_from,
            )
            for (node, version), artifact in deployment.artifacts.items()
        )),
    )


def changed_chunk(artifact, chunk):
    """Create a self-consistently identified but untrusted compiler output."""
    changed = replace(artifact, chunk=chunk)
    return replace(changed, artifact_id=artifact_id(
        changed.domain,
        changed.generation,
        changed.produced_by,
        changed.state_id,
        changed.entity,
        changed.version,
        changed.owner,
        changed.chunk,
        changed.reused_from,
    ))


class IndependentBoundaries(unittest.TestCase):
    def setUp(self):
        self.source = evaluator_source()
        self.executor = RestrictedExecutor()
        self.deployment = self.executor.deploy(
            self.source, compiler_generation=1,
        )
        self.registry = self.executor.registry({
            "policy": (self.deployment, ROLE_PRED),
        })

    def test_relation_write_positive_and_negative(self):
        runtime = Runtime(relation_state(), self.registry.context)
        kept = runtime.keep(runtime.active.state.reference(CELL))
        try:
            before = runtime.active
            runtime.write(CELL, 3)
            self.assertIs(runtime.active, before)

            original = snapshot(runtime)
            artifacts = artifact_snapshot(self.deployment)
            with self.assertRaises(RelationConstraintRejected):
                runtime.write(CELL, 4)

            self.assertEqual(snapshot(runtime), original)
            self.assertEqual(artifact_snapshot(self.deployment), artifacts)
            self.assertFalse(kept.released)
        finally:
            kept.release()

    def test_staged_relation_accepts_and_rejects_activation(self):
        source = permissive_relation_state()
        candidate = narrowed_relation(source)

        accepted = Runtime(source, self.registry.context)
        accepted.activate(candidate)
        self.assertEqual(accepted.active.state.id, candidate.destination.id)
        self.assertEqual(accepted.read(CELL), 3)

        rejected = Runtime(source, self.registry.context)
        rejected.write(CELL, 11)
        before = snapshot(rejected)
        artifacts = artifact_snapshot(self.deployment)
        with self.assertRaises(ActivationRejected) as cm:
            rejected.activate(candidate)

        self.assertEqual(cm.exception.relation, RELATION)
        self.assertEqual(snapshot(rejected), before)
        self.assertEqual(artifact_snapshot(self.deployment), artifacts)

    def test_staged_relation_accepts_and_rejects_trial(self):
        source = permissive_relation_state()
        candidate = narrowed_relation(source)

        accepted = Runtime(source, self.registry.context)
        before = snapshot(accepted)
        trial = accepted.trial(candidate)
        try:
            self.assertEqual(trial.active.state.id, candidate.destination.id)
            self.assertEqual(trial.read(CELL), 3)
            self.assertEqual(snapshot(accepted), before)
        finally:
            trial.end_trial()

        rejected = Runtime(source, self.registry.context)
        rejected.write(CELL, 11)
        before = snapshot(rejected)
        artifacts = artifact_snapshot(self.deployment)
        with self.assertRaises(ActivationRejected) as cm:
            rejected.trial(candidate)

        self.assertEqual(cm.exception.relation, RELATION)
        self.assertEqual(snapshot(rejected), before)
        self.assertEqual(artifact_snapshot(self.deployment), artifacts)

    def test_admission_uses_actual_admitted_evaluator_chunks(self):
        opened = []
        original = machine._open

        def observe(activation, args, *rest, **kwargs):
            chunk, env, node = original(
                activation, args, *rest, **kwargs,
            )
            if activation.hold.version.state.id == self.source.id:
                opened.append((node, chunk))
            return chunk, env, node

        with (
            mock.patch.object(machine, "_open", side_effect=observe),
            mock.patch.object(
                bytecode, "lower_value", side_effect=no_host_lowering,
            ),
            mock.patch.object(
                bytecode, "chunk_of", side_effect=no_host_lowering,
            ),
        ):
            runtime = Runtime(relation_state(), self.registry.context)
            runtime.write(CELL, 3)

        self.assertTrue(opened)
        for node, chunk in opened:
            key = (node, self.source.values[node].version_id)
            self.assertIn(key, self.deployment.artifacts)
            artifact = self.deployment.artifacts[key]
            self.assertIs(chunk, artifact.chunk)
            self.assertEqual(artifact.state_id, self.source.id)
            self.assertEqual(artifact.produced_by, 1)

    def test_machine_fault_proves_genuine_initial_admission(self):
        original = machine._open
        intercepted = []

        def trap(activation, args, *rest, **kwargs):
            if (
                activation.entity == ROLE_PRED
                and activation.hold.version.state.id == self.source.id
            ):
                intercepted.append(activation.entity)
                raise RuntimeError("independent evaluator interception")
            return original(activation, args, *rest, **kwargs)

        with mock.patch.object(machine, "_open", side_effect=trap):
            with self.assertRaisesRegex(
                RuntimeError, "independent evaluator interception",
            ):
                Runtime(relation_state(), self.registry.context)
        self.assertEqual(intercepted, [ROLE_PRED])

    def test_machine_fault_proves_genuine_write_admission(self):
        runtime = Runtime(relation_state(), self.registry.context)
        before = snapshot(runtime)
        original = machine._open
        intercepted = []

        def trap(activation, args, *rest, **kwargs):
            if (
                activation.entity == ROLE_PRED
                and activation.hold.version.state.id == self.source.id
            ):
                intercepted.append(activation.entity)
                raise RuntimeError("independent write interception")
            return original(activation, args, *rest, **kwargs)

        with mock.patch.object(machine, "_open", side_effect=trap):
            with self.assertRaisesRegex(
                RuntimeError, "independent write interception",
            ):
                runtime.write(CELL, 3)
        self.assertEqual(intercepted, [ROLE_PRED])
        self.assertEqual(snapshot(runtime), before)

    def test_denied_effects_cannot_modify_evaluator_cells(self):
        self.assertEqual(
            self.executor.run(
                self.deployment, READ, policy=READ_POLICY,
            ),
            7,
        )
        for entry in (WRITE, CALL_WRITE, DEAD_WRITE):
            with self.subTest(entry=entry.value):
                artifacts = artifact_snapshot(self.deployment)
                with self.assertRaises(AdmissionRejected):
                    self.executor.run(
                        self.deployment, entry, 9,
                        policy=PURE_POLICY,
                    )
                self.assertEqual(
                    self.executor.run(
                        self.deployment, READ, policy=READ_POLICY,
                    ),
                    7,
                )
                self.assertEqual(artifact_snapshot(self.deployment), artifacts)

    def test_denied_indirect_call_never_reaches_machine(self):
        before = artifact_snapshot(self.deployment)
        with mock.patch.object(
            machine, "_open",
            side_effect=AssertionError(
                "restricted call reached execution",
            ),
        ):
            with self.assertRaises(AdmissionRejected):
                self.executor.run(
                    self.deployment, DYNAMIC, PRED,
                    policy=PURE_POLICY,
                )
        self.assertEqual(artifact_snapshot(self.deployment), before)

    def test_existing_artifact_resolver_rejects_provenance_mismatch(self):
        """Independent existing-machine oracle – no Task 32 trace trust."""
        root = PURE
        from shear.lang import _definition_of
        node = _definition_of(self.source.values[root]).body
        artifact = self.deployment.artifacts[
            (node, self.source.values[node].version_id)
        ]
        valid = ArtifactSet(self.source, lambda _: None)
        valid.admit(artifact)
        self.assertIs(
            valid.resolver()(self.source, node, root), artifact.chunk,
        )

        mismatches = (
            ("wrong source", "state_id", relation_state().id),
            ("wrong node", "entity", PRED),
            ("wrong version", "version", self.source.values[PRED].version_id),
            ("wrong owner", "owner", PRED),
            ("wrong producer", "produced_by", 0),
            ("wrong compiler generation", "generation", 999),
            ("wrong dependency", "reused_from", "unverified-parent"),
            ("tampered chunk", "chunk", (("LIT", "tampered"),)),
        )
        for name, field, value in mismatches:
            with self.subTest(name=name):
                forged = replace(artifact, **{field: value})
                candidate = ArtifactSet(self.source, lambda _: None)
                candidate.admit(forged)
                with self.assertRaises(AdmissionRejected):
                    candidate.resolver()(self.source, node, root)

        different = self.source.with_changes({
            EntityID("t32.extra"): 5,
        })
        with self.assertRaises(AdmissionRejected):
            valid.resolver()(different, node, root)
        with self.assertRaises(AdmissionRejected):
            valid.resolver()(self.source, PRED, root)
        with self.assertRaises(AdmissionRejected):
            valid.resolver()(self.source, node, PRED)
        valid.invalidate()
        with self.assertRaises(AdmissionRejected):
            valid.resolver()(self.source, node, root)

    def test_admitted_emitted_effects_are_checked_independently(self):
        """A signed executable chunk cannot bypass source-graph preflight."""
        from shear.lang import _definition_of
        root = _definition_of(self.source.values[PURE]).body
        real_admit = ArtifactSet.admit
        for instruction in (("WRITE", CELL), ("FUTURE_UNKNOWN_OPCODE",)):
            with self.subTest(instruction=instruction):
                emitted = []

                def adversarial_admit(artifacts, artifact):
                    if artifact.entity == root:
                        emitted.append(artifact.entity)
                        artifact = changed_chunk(artifact, (instruction,))
                    return real_admit(artifacts, artifact)

                adversarial_executor = RestrictedExecutor()
                with mock.patch.object(
                    ArtifactSet, "admit", new=adversarial_admit,
                ):
                    try:
                        deployment = adversarial_executor.deploy(
                            self.source, compiler_generation=1,
                        )
                    except AdmissionRejected:
                        self.assertEqual(emitted, [root])
                        continue

                self.assertEqual(emitted, [root])
                with mock.patch.object(
                    machine, "_open",
                    side_effect=AssertionError("forbidden chunk executed"),
                ):
                    with self.assertRaises(AdmissionRejected):
                        adversarial_executor.run(
                            deployment, PURE, 4, policy=PURE_POLICY,
                        )

    def test_malformed_link_target_fails_closed(self):
        """A post-load malformed role survives normalization unchanged."""
        malformed = self.source.with_changes({
            EntityID("t32.bad_links"): Relation("links", {
                "function": (CALL_WRITE,),
                "writer": WRITE,
            }),
        })
        self.assertEqual(load(malformed).id, malformed.id)
        with self.assertRaises(AdmissionRejected):
            self.executor.deploy(malformed, compiler_generation=1)


if __name__ == "__main__":
    unittest.main()
