"""Independent Task 32 admission and anti-fallback acceptance – GH-119.

These tests observe machine execution, admitted artifacts and runtime state.
Structural validity, compiler authority and restricted effect enforcement
are deliberately separate proof obligations.
"""

from __future__ import annotations

from contextlib import contextmanager
import unittest
from unittest import mock

from shear import (
    ActivationRejected,
    CellContentRejected,
    CellDeclaration,
    EntityID,
    External,
    IsKind,
    Relation,
    RelationConstraintRejected,
    Runtime,
    State,
    Value,
    canonicalize,
    transform_with_mapping,
)
from shear import bytecode, machine
from shear.hosted_bootstrap import AdmissionRejected
from shear.hosted_bootstrap.artifacts import ArtifactSet
from shear.hosted_bootstrap.generations import CompilerChain
from shear.hosted_bootstrap.restricted import (
    RestrictedExecutor,
    RestrictionPolicy,
)
from shear.hosted_bootstrap.validation import validate_chunk
from shear.lang import _definition_of, load
from tests.test_restricted_execution import (
    CALL_WRITE,
    CELL,
    DEAD_WRITE,
    DYNAMIC,
    PRED,
    PURE_POLICY,
    READ,
    READ_POLICY,
    RELATION,
    ROLE_PRED,
    WRITE,
    cell_state,
    evaluator_source,
    no_host_lowering,
    relation_state,
    snapshot,
)


def permissive_relation_state() -> State:
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
    """Immutable observations of admitted artifact bindings."""
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


def runtime_snapshot(runtime):
    """Capture mutable version state as values, not live references."""
    return (
        runtime.active.id,
        tuple(
            (
                id(version),
                version.id,
                version.state.id,
                version.retired,
                tuple(sorted(
                    version.cells.items(),
                    key=lambda item: item[0].value,
                )),
                tuple(sorted(id(hold) for hold in version.holds)),
            )
            for version in runtime.versions
        ),
        tuple(id(change) for change in runtime._history),
    )


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

    def scalar_registry(self):
        return self.executor.registry({
            "policy": (self.deployment, PRED),
        })

    @contextmanager
    def observed_admitted_execution(self, entry):
        """Observe the actual selected machine chunk during admission."""
        opened = []
        original = machine._open

        def observe(activation, args, *rest, **kwargs):
            result = original(activation, args, *rest, **kwargs)
            if (
                activation.entity == entry
                and activation.hold.version.state.id == self.source.id
            ):
                chunk, _, node = result
                key = (node, self.source.values[node].version_id)
                self.assertIn(key, self.deployment.artifacts)
                artifact = self.deployment.artifacts[key]
                self.assertIs(chunk, artifact.chunk)
                self.assertEqual(artifact.state_id, self.source.id)
                self.assertEqual(artifact.entity, node)
                self.assertEqual(artifact.version, key[1])
                self.assertEqual(artifact.owner, entry)
                self.assertEqual(artifact.produced_by, 1)
                artifact.verify()
                opened.append((tuple(args), node, artifact))
            return result

        with (
            mock.patch.object(machine, "_open", side_effect=observe),
            mock.patch.object(
                bytecode, "lower_value", side_effect=no_host_lowering,
            ),
            mock.patch.object(
                bytecode, "chunk_of", side_effect=no_host_lowering,
            ),
        ):
            yield opened

        self.assertTrue(
            opened, "admission did not open an admitted evaluator",
        )

    def assert_machine_fault(self, entry, action):
        """Fault at the machine entry, not at the evaluator adapter."""
        seen = []
        original = machine._open

        def trap(activation, args, *rest, **kwargs):
            if (
                activation.entity == entry
                and activation.hold.version.state.id == self.source.id
            ):
                seen.append((activation.entity, tuple(args)))
                raise RuntimeError("injected evaluator-machine fault")
            return original(activation, args, *rest, **kwargs)

        with mock.patch.object(machine, "_open", side_effect=trap):
            with self.assertRaisesRegex(
                RuntimeError, "injected evaluator-machine fault",
            ):
                action()

        self.assertTrue(seen, "the evaluator machine was never entered")

    def test_relation_write_positive_negative_and_reference_atomicity(self):
        runtime = Runtime(relation_state(), self.registry.context)
        kept = runtime.keep(runtime.active.state.reference(CELL))
        try:
            before = runtime.active

            with self.observed_admitted_execution(ROLE_PRED) as opened:
                runtime.write(CELL, 3)

            self.assertEqual(
                opened[0][0],
                (canonicalize({"item": 3}),),
            )
            self.assertIs(runtime.active, before)

            original = runtime_snapshot(runtime)
            artifacts = artifact_snapshot(self.deployment)
            reference = kept.reference
            held_version = kept.version

            with self.observed_admitted_execution(ROLE_PRED) as rejected:
                with self.assertRaises(RelationConstraintRejected):
                    runtime.write(CELL, 4)

            self.assertEqual(
                rejected[0][0],
                (canonicalize({"item": 4}),),
            )
            self.assertEqual(runtime_snapshot(runtime), original)
            self.assertEqual(artifact_snapshot(self.deployment), artifacts)
            self.assertEqual(kept.reference, reference)
            self.assertIs(kept.version, held_version)
            self.assertFalse(kept.released)
        finally:
            kept.release()

    def test_initial_cell_admission_uses_selected_admitted_machine(self):
        registry = self.scalar_registry()
        accepted_source = cell_state(3)

        with self.observed_admitted_execution(PRED) as accepted_open:
            runtime = Runtime(accepted_source, registry.context)

        self.assertEqual(runtime.read(CELL), 3)
        self.assertEqual(accepted_open[0][0], (3,))
        self.assertEqual(runtime.active.state.id, accepted_source.id)

        rejected_source = cell_state(11)
        artifacts = artifact_snapshot(self.deployment)

        with self.observed_admitted_execution(PRED) as rejected_open:
            with self.assertRaises(CellContentRejected) as cm:
                Runtime(rejected_source, registry.context)

        self.assertEqual(rejected_open[0][0], (11,))
        self.assertEqual(cm.exception.cell, CELL)
        self.assertEqual(artifact_snapshot(self.deployment), artifacts)

        self.assert_machine_fault(
            PRED,
            lambda: Runtime(accepted_source, registry.context),
        )

    def test_initial_relation_admission_uses_selected_admitted_machine(self):
        accepted_source = relation_state(3)

        with self.observed_admitted_execution(ROLE_PRED) as accepted:
            runtime = Runtime(accepted_source, self.registry.context)

        self.assertEqual(
            accepted[0][0], (canonicalize({"item": 3}),),
        )
        self.assertEqual(runtime.active.state.id, accepted_source.id)

        with self.observed_admitted_execution(ROLE_PRED) as rejected:
            with self.assertRaises(RelationConstraintRejected):
                Runtime(relation_state(11), self.registry.context)

        self.assertEqual(
            rejected[0][0], (canonicalize({"item": 11}),),
        )

        self.assert_machine_fault(
            ROLE_PRED,
            lambda: Runtime(accepted_source, self.registry.context),
        )

    def test_staged_cell_activation_and_trial_machine_evidence(self):
        registry = self.scalar_registry()
        source = cell_state(0, IsKind("int"))
        candidate = transform_with_mapping(
            source,
            {CELL: CellDeclaration(External("policy"), 0)},
            {CELL: CELL},
        )

        for operation in ("activate", "trial"):
            with self.subTest(operation=operation):
                accepted = Runtime(source, registry.context)
                accepted.write(CELL, 3)
                old = runtime_snapshot(accepted)

                with self.observed_admitted_execution(PRED) as opened:
                    outcome = getattr(accepted, operation)(candidate)

                self.assertEqual(opened[0][0], (3,))
                self.assertEqual(
                    outcome.state.id if operation == "activate"
                    else outcome.active.state.id,
                    candidate.destination.id,
                )

                if operation == "trial":
                    self.assertEqual(runtime_snapshot(accepted), old)
                    self.assertEqual(outcome.read(CELL), 3)
                    outcome.end_trial()
                else:
                    self.assertEqual(accepted.read(CELL), 3)

                rejected = Runtime(source, registry.context)
                rejected.write(CELL, 11)
                before = runtime_snapshot(rejected)
                artifacts = artifact_snapshot(self.deployment)

                with self.observed_admitted_execution(PRED) as denied:
                    with self.assertRaises(ActivationRejected) as cm:
                        getattr(rejected, operation)(candidate)

                self.assertEqual(denied[0][0], (11,))
                self.assertEqual(cm.exception.cell, CELL)
                self.assertEqual(runtime_snapshot(rejected), before)
                self.assertEqual(
                    artifact_snapshot(self.deployment), artifacts,
                )

                self.assert_machine_fault(
                    PRED,
                    lambda: getattr(rejected, operation)(candidate),
                )
                self.assertEqual(runtime_snapshot(rejected), before)

    def test_staged_relation_activation_and_trial_machine_evidence(self):
        source = permissive_relation_state()
        candidate = narrowed_relation(source)

        for operation in ("activate", "trial"):
            with self.subTest(operation=operation):
                accepted = Runtime(source, self.registry.context)
                with self.observed_admitted_execution(ROLE_PRED) as opened:
                    result = getattr(accepted, operation)(candidate)

                self.assertEqual(
                    opened[0][0], (canonicalize({"item": 3}),),
                )
                if operation == "trial":
                    self.assertEqual(
                        result.active.state.id, candidate.destination.id,
                    )
                    result.end_trial()
                else:
                    self.assertEqual(
                        result.state.id, candidate.destination.id,
                    )

                rejected = Runtime(source, self.registry.context)
                rejected.write(CELL, 11)
                before = runtime_snapshot(rejected)
                artifacts = artifact_snapshot(self.deployment)

                with self.observed_admitted_execution(ROLE_PRED) as denied:
                    with self.assertRaises(ActivationRejected) as cm:
                        getattr(rejected, operation)(candidate)

                self.assertEqual(
                    denied[0][0], (canonicalize({"item": 11}),),
                )
                self.assertEqual(cm.exception.relation, RELATION)
                self.assertEqual(runtime_snapshot(rejected), before)
                self.assertEqual(
                    artifact_snapshot(self.deployment), artifacts,
                )

    def test_machine_fault_proves_genuine_relation_write_admission(self):
        runtime = Runtime(relation_state(), self.registry.context)
        before = runtime_snapshot(runtime)
        self.assert_machine_fault(
            ROLE_PRED,
            lambda: runtime.write(CELL, 3),
        )
        self.assertEqual(runtime_snapshot(runtime), before)

    def test_runtime_trace_identifies_target_and_write_operation(self):
        registry = self.scalar_registry()
        target = cell_state(3)
        runtime = Runtime(target, registry.context)
        before = len(self.executor.trace())

        with self.observed_admitted_execution(PRED) as opened:
            runtime.write(CELL, 4)

        events = self.executor.trace()[before:]
        artifact = opened[0][2]
        self.assertTrue(
            any(
                event.entity == PRED
                and event.artifact_id == artifact.artifact_id
                and event.compiler_generation == 1
                and event.target_state_id == target.id
                and (
                    getattr(event, "operation", None) == "write"
                    or "write" in event.detail.lower()
                )
                for event in events
            ),
            "missing target-state, operation and evaluator provenance",
        )
        self.assertEqual(runtime.read(CELL), 4)

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
                self.assertEqual(
                    artifact_snapshot(self.deployment), artifacts,
                )

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

    def test_existing_artifact_resolver_identity_guardrails(self):
        """D5 resolver check, separate from compiler-production authority."""
        root = _definition_of(self.source.values[READ]).body
        key = (root, self.source.values[root].version_id)
        artifact = self.deployment.artifacts[key]

        valid = ArtifactSet(self.source, lambda _: None)
        valid.admit(artifact)
        self.assertIs(
            valid.resolver()(self.source, root, READ), artifact.chunk,
        )

        different = self.source.with_changes({
            EntityID("t32.extra"): 5,
        })
        with self.assertRaises(AdmissionRejected):
            valid.resolver()(different, root, READ)
        with self.assertRaises(AdmissionRejected):
            valid.resolver()(self.source, PRED, READ)
        with self.assertRaises(AdmissionRejected):
            valid.resolver()(self.source, root, PRED)

        valid.invalidate()
        with self.assertRaises(AdmissionRejected):
            valid.resolver()(self.source, root, READ)

    def test_structurally_valid_emitted_write_is_rejected_by_policy(self):
        """Compiler-output adversary, not a malformed-chunk adversary.

        The source is an ordinary READ node with a legitimate cell link.
        The adversarial compiler output is structurally valid and correctly
        identified. It must be rejected because WRITE is not allowed by
        READ_POLICY, before the evaluator machine opens.
        """
        root = _definition_of(self.source.values[READ]).body
        emitted = (
            ("LIT", canonicalize(99)),
            ("WRITE", CELL),
            ("END",),
        )

        # Independently establish structural validity before injection.
        validate_chunk(self.source, root, READ, emitted)
        self.assertNotIn(
            "WRITE",
            {instruction[0] for instruction in
             self.deployment.artifacts[
                 (root, self.source.values[root].version_id)
             ].chunk},
        )

        original_compile = CompilerChain.compile
        produced = []

        def adversarial_compile(chain, descriptor, generation):
            identity = descriptor.value[1]
            if identity[0] == self.source.id and identity[1] == root:
                produced.append((identity, generation))
                return emitted
            return original_compile(chain, descriptor, generation)

        adversarial = RestrictedExecutor()
        with mock.patch.object(
            CompilerChain, "compile", new=adversarial_compile,
        ):
            deployment = adversarial.deploy(
                self.source, compiler_generation=1,
            )

        self.assertEqual(len(produced), 1)
        key = (root, self.source.values[root].version_id)
        self.assertIn(key, deployment.artifacts)
        artifact = deployment.artifacts[key]
        artifact.verify()
        self.assertEqual(artifact.chunk, emitted)
        self.assertEqual(artifact.produced_by, 1)

        with mock.patch.object(
            machine, "_open",
            side_effect=AssertionError(
                "policy was bypassed and machine execution began",
            ),
        ):
            with self.assertRaises(AdmissionRejected):
                adversarial.run(
                    deployment, READ, policy=READ_POLICY,
                )

    def test_unknown_emitted_opcode_is_structurally_rejected(self):
        """Unknown opcode is a separate structural failure discriminator."""
        root = _definition_of(self.source.values[READ]).body
        unknown = (("FUTURE_UNKNOWN_OPCODE",), ("END",))

        with self.assertRaises(AdmissionRejected):
            validate_chunk(self.source, root, READ, unknown)

        original_compile = CompilerChain.compile
        produced = []

        def adversarial_compile(chain, descriptor, generation):
            identity = descriptor.value[1]
            if identity[0] == self.source.id and identity[1] == root:
                produced.append(root)
                return unknown
            return original_compile(chain, descriptor, generation)

        with mock.patch.object(
            CompilerChain, "compile", new=adversarial_compile,
        ):
            with self.assertRaises(AdmissionRejected):
                RestrictedExecutor().deploy(
                    self.source, compiler_generation=1,
                )

        self.assertEqual(produced, [root])

    def test_malformed_link_target_fails_closed(self):
        malformed = self.source.with_changes({
            EntityID("t32.bad_links"): Relation("links", {
                "function": (CALL_WRITE,),
                "writer": WRITE,
            }),
        })
        self.assertEqual(load(malformed).id, malformed.id)
        with self.assertRaises(AdmissionRejected):
            self.executor.deploy(
                malformed, compiler_generation=1,
            )


if __name__ == "__main__":
    unittest.main()
