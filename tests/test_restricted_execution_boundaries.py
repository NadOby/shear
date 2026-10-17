"""Independent Task 32 boundary and anti-fallback tests – GH-119.

These tests inspect actual machine execution, not implementation trace
claims. They complement test_restricted_execution.py and freeze the
relation staging, rollback, and effect-isolation requirements.
"""

from __future__ import annotations

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
from shear.hosted_bootstrap.restricted import (
    RestrictedExecutor,
    RestrictionPolicy,
)
from shear.lang import Function, load
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

        before = runtime.active
        runtime.write(CELL, 3)
        self.assertIs(runtime.active, before)

        original = snapshot(runtime)
        with self.assertRaises(RelationConstraintRejected):
            runtime.write(CELL, 4)

        self.assertEqual(snapshot(runtime), original)

    def test_staged_relation_accepts_and_rejects_activation(self):
        source = permissive_relation_state()
        candidate = narrowed_relation(source)

        accepted = Runtime(source, self.registry.context)
        accepted.activate(candidate)

        self.assertEqual(
            accepted.active.state.id,
            candidate.destination.id,
        )
        self.assertEqual(accepted.read(CELL), 3)

        rejected = Runtime(source, self.registry.context)
        rejected.write(CELL, 11)
        before = snapshot(rejected)

        with self.assertRaises(ActivationRejected) as cm:
            rejected.activate(candidate)

        self.assertEqual(cm.exception.relation, RELATION)
        self.assertEqual(snapshot(rejected), before)

    def test_staged_relation_accepts_and_rejects_trial(self):
        source = permissive_relation_state()
        candidate = narrowed_relation(source)

        accepted = Runtime(source, self.registry.context)
        before = snapshot(accepted)
        trial = accepted.trial(candidate)

        try:
            self.assertEqual(
                trial.active.state.id,
                candidate.destination.id,
            )
            self.assertEqual(trial.read(CELL), 3)
            self.assertEqual(snapshot(accepted), before)
        finally:
            trial.end_trial()

        rejected = Runtime(source, self.registry.context)
        rejected.write(CELL, 11)
        before = snapshot(rejected)

        with self.assertRaises(ActivationRejected) as cm:
            rejected.trial(candidate)

        self.assertEqual(cm.exception.relation, RELATION)
        self.assertEqual(snapshot(rejected), before)

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
                bytecode, "lower_value",
                side_effect=no_host_lowering,
            ),
            mock.patch.object(
                bytecode, "chunk_of",
                side_effect=no_host_lowering,
            ),
        ):
            runtime = Runtime(
                relation_state(), self.registry.context,
            )
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

        with mock.patch.object(
            machine, "_open", side_effect=trap,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "independent evaluator interception",
            ):
                Runtime(relation_state(), self.registry.context)

        self.assertEqual(intercepted, [ROLE_PRED])

    def test_machine_fault_proves_genuine_write_admission(self):
        runtime = Runtime(
            relation_state(), self.registry.context,
        )
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

        with mock.patch.object(
            machine, "_open", side_effect=trap,
        ):
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

    def test_denied_indirect_call_never_reaches_machine(self):
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

    def test_malformed_link_target_fails_closed(self):
        function = EntityID("t32.bad_link_function")
        linked = EntityID("t32.bad_linked")
        links_id = EntityID("t32.bad_link_relation")
        malformed = State.create({
            function: Value.create(
                function,
                Function(("x",), ("call", "target", ("arg", "x"))),
            ),
            linked: Value.create(
                linked, Function(("x",), ("lit", "satisfied")),
            ),
            links_id: Value.create(
                links_id,
                Relation("links", {
                    "function": function,
                    "target": (linked,),
                }),
            ),
        })

        with self.assertRaises((AdmissionRejected, ValueError)):
            self.executor.deploy(
                load(malformed), compiler_generation=1,
            )


if __name__ == "__main__":
    unittest.main()
