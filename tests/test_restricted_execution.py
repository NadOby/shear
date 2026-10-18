"""Task 32 Plan-owned acceptance – GH-119, docs/restricted_execution.md.

Provisional host-only implementation contract (not language syntax):

    executor = RestrictedExecutor()
    deployment = executor.deploy(loaded_state, compiler_generation=1)
    deployment.source_state_id, .compiler_generation, .artifacts
    executor.run(deployment, entry, *args, policy=RestrictionPolicy(...))
    executor.registry({name: (deployment, entry)}) -> registry
    registry.context -> EvaluationContext (stable reference)
    registry.replace(name, (deployment, entry))
    executor.invalidate(deployment)
    executor.trace() -> hosted TraceEvent sequence

RestrictionPolicy defaults to no authority for effectful operations. Its
allowed_effects is a frozen set of existing operation names (initially read,
write, activate, trial); unknown effects always fail closed. Tests must fail,
not skip, before this host-facing integration exists. No special evaluator VM,
Python predicate substitution, or host-lowering fallback is permitted.
"""

from __future__ import annotations

import unittest
from unittest import mock

from shear import (
    ActivationRejected, AllOf, CellContentRejected, CellDeclaration,
    ConstraintResult, EntityID, External, IsKind, Relation,
    RelationConstraintRejected, Runtime, State, Value, canonicalize,
    relation_of, transform_with_mapping,
)
from shear import bytecode, machine
from shear.examples._support import program
from shear.hosted_bootstrap import AdmissionRejected, HostedSession
from shear.hosted_bootstrap.restricted import RestrictedExecutor, RestrictionPolicy
from shear.lang import Function, LanguageError, links, load

CELL = EntityID("t32.cell")
SECOND = EntityID("t32.second")
RELATION = EntityID("t32.relation")
OWNER = EntityID("t32.owner")
OWNED = EntityID("t32.owned")
PRED = EntityID("t32.predicate")
NEGATIVE = EntityID("t32.negative")
ROLE_PRED = EntityID("t32.role_predicate")
OWNED_PRED = EntityID("t32.owned_predicate")
BAD_RESULT = EntityID("t32.bad_result")
RAISE = EntityID("t32.raise")
PURE = EntityID("t32.pure")
PURE_CALL = EntityID("t32.pure_call")
READ = EntityID("t32.read")
WRITE = EntityID("t32.write")
CALL_WRITE = EntityID("t32.call_write")
DEAD_WRITE = EntityID("t32.dead_write")
ACTIVATE = EntityID("t32.activate")
TRIAL = EntityID("t32.trial")
DYNAMIC = EntityID("t32.dynamic")
WRITER = EntityID("t32.target_writer")

SAT = ConstraintResult.SATISFIED
VIO = ConstraintResult.VIOLATED
UNK = ConstraintResult.UNKNOWN
PURE_POLICY = RestrictionPolicy(allowed_effects=frozenset())
READ_POLICY = RestrictionPolicy(allowed_effects=frozenset({"read"}))


def evaluator_source() -> State:
    """All code is ordinary SHEAR; Python only constructs source."""
    return load(program({
        PRED: Function(("x",), (
            "if", ("lt", ("arg", "x"), ("lit", 0)),
            ("lit", "unknown"),
            ("if", ("lt", ("arg", "x"), ("lit", 10)),
             ("lit", "satisfied"), ("lit", "violated")),
        )),
        NEGATIVE: Function(("x",), ("lit", "violated")),
        ROLE_PRED: Function(("x",), (
            "if", ("eq", ("arg", "x"),
                   ("lit", canonicalize({"item": 3}))),
            ("lit", "satisfied"), ("lit", "violated"),
        )),
        OWNED_PRED: Function(("x",), (
            "if", ("eq", ("arg", "x"),
                   ("lit", canonicalize({
                       "whole": {"value": 1, "owned": {OWNED: 2}},
                   }))),
            ("lit", "satisfied"), ("lit", "violated"),
        )),
        BAD_RESULT: Function(("x",), ("lit", 17)),
        RAISE: Function(("x",), (
            "raise", ("lit", "evaluator_failure"), ("lit", "probe"),
        )),
        PURE: Function(("x",), (
            "mul", ("add", ("arg", "x"), ("lit", 3)), ("lit", 3),
        )),
        PURE_CALL: Function(("x",), (
            "call", "callee", ("arg", "x"),
        )),
        EntityID("t32.pure_call.links"): links(PURE_CALL, callee=PURE),
        CELL: CellDeclaration(IsKind("int"), 7),
        READ: Function((), ("read", "cell")),
        EntityID("t32.read.links"): links(READ, cell=CELL),
        WRITE: Function(("x",), ("write", "cell", ("arg", "x"))),
        EntityID("t32.write.links"): links(WRITE, cell=CELL),
        CALL_WRITE: Function(("x",), ("call", "writer", ("arg", "x"))),
        EntityID("t32.call.links"): links(CALL_WRITE, writer=WRITE),
        DEAD_WRITE: Function(("x",), (
            "if", ("lit", False),
            ("call", "writer", ("arg", "x")),
            ("lit", "satisfied"),
        )),
        EntityID("t32.dead.links"): links(DEAD_WRITE, writer=WRITE),
        ACTIVATE: Function(("x",), (
            "activate", "target", ("arg", "x"),
        )),
        EntityID("t32.activate.links"): links(ACTIVATE, target=PURE),
        TRIAL: Function(("x",), (
            "trial", ("call", "target", ("lit", 4)),
            "target", ("arg", "x"),
        )),
        EntityID("t32.trial.links"): links(TRIAL, target=PURE),
        DYNAMIC: Function(("f",), (
            "apply", ("arg", "f"), ("lit", 3),
        )),
    }))


def cell_state(initial: int = 3, constraint=None) -> State:
    return State.create({
        CELL: Value.create(
            CELL, CellDeclaration(constraint or External("policy"), initial)
        ),
    })


def relation_state(initial: int = 3) -> State:
    return State.create({
        CELL: Value.create(CELL, CellDeclaration(IsKind("int"), initial)),
        RELATION: Value.create(RELATION, Relation(
            "policy", {"item": CELL}, External("policy"),
        )),
    })


def snapshot(runtime: Runtime):
    """Freeze mutable version, cell, hold and retirement observations."""
    return (
        id(runtime.active),
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


def no_host_lowering(*args, **kwargs):
    raise AssertionError("host lowering during restricted execution")


class RestrictedAcceptance(unittest.TestCase):
    def setUp(self):
        self.source = evaluator_source()
        self.executor = RestrictedExecutor()
        self.deployment = self.executor.deploy(
            self.source, compiler_generation=1,
        )

    def registry(self, entry=PRED):
        return self.executor.registry({"policy": (self.deployment, entry)})

    def test_generic_use_is_not_a_constraint_adapter(self):
        self.assertEqual(
            self.executor.run(self.deployment, PURE, 4, policy=PURE_POLICY),
            21,
        )
        self.assertEqual(
            self.executor.run(self.deployment, READ, policy=READ_POLICY),
            7,
        )
        with self.assertRaises(AdmissionRejected):
            self.executor.run(self.deployment, READ, policy=PURE_POLICY)

    def test_permitted_transitive_call_uses_existing_machine(self):
        opened = []
        real_open = machine._open

        def observe(activation, args, *rest, **kwargs):
            chunk, env, node = real_open(activation, args, *rest, **kwargs)
            if activation.hold.version.state.id == self.source.id:
                opened.append((activation.entity, node, chunk))
            return chunk, env, node

        with mock.patch.object(machine, "_open", side_effect=observe):
            result = self.executor.run(
                self.deployment, PURE_CALL, 4, policy=PURE_POLICY,
            )
        self.assertEqual(result, 21)
        self.assertIn(PURE_CALL, {entry for entry, _, _ in opened})
        self.assertIn(PURE, {entry for entry, _, _ in opened})
        for _, node, chunk in opened:
            key = (node, self.source.values[node].version_id)
            self.assertIs(chunk, self.deployment.artifacts[key].chunk)

    def test_real_predicate_and_independent_admitted_chunks(self):
        artifacts = self.deployment.artifacts
        self.assertEqual(self.deployment.source_state_id, self.source.id)
        self.assertEqual(self.deployment.compiler_generation, 1)
        self.assertTrue(artifacts)

        opened = []
        original = machine._open

        def spy(activation, args, *rest, **kwargs):
            chunk, env, node = original(activation, args, *rest, **kwargs)
            if activation.hold.version.state.id == self.source.id:
                opened.append((node, chunk))
            return chunk, env, node

        with (
            mock.patch.object(machine, "_open", side_effect=spy),
            mock.patch.object(bytecode, "lower_value", side_effect=no_host_lowering),
            mock.patch.object(bytecode, "chunk_of", side_effect=no_host_lowering),
        ):
            for value, expected in ((3, "satisfied"), (11, "violated"),
                                    (-2, "unknown")):
                self.assertEqual(
                    self.executor.run(
                        self.deployment, PRED, value, policy=PURE_POLICY
                    ), expected,
                )

        self.assertTrue(opened, "no actual evaluator machine execution")
        for node, chunk in opened:
            key = (node, self.source.values[node].version_id)
            self.assertIn(key, artifacts)
            self.assertIs(chunk, artifacts[key].chunk)
            self.assertEqual(artifacts[key].produced_by, 1)

    def test_initial_cell_and_relation_admission(self):
        scalar = self.registry()
        good = Runtime(cell_state(), scalar.context)
        self.assertEqual(good.read(CELL), 3)
        with self.assertRaises(CellContentRejected) as cm:
            Runtime(cell_state(11), scalar.context)
        self.assertIs(cm.exception.result, VIO)
        with self.assertRaises(CellContentRejected) as cm:
            Runtime(cell_state(-2), scalar.context)
        self.assertIs(cm.exception.result, UNK)

        roles = self.registry(ROLE_PRED)
        seen = []
        real_open = machine._open

        def observe(activation, args, *other, **kw):
            if activation.entity == ROLE_PRED:
                seen.append(tuple(args))
            return real_open(activation, args, *other, **kw)

        with mock.patch.object(machine, "_open", side_effect=observe):
            Runtime(relation_state(), roles.context)
        self.assertIn((canonicalize({"item": 3}),), seen)
        with self.assertRaises(RelationConstraintRejected) as cm:
            Runtime(relation_state(11), roles.context)
        self.assertIs(cm.exception.result, VIO)

    def test_owned_subtree_subject_is_preserved(self):
        values = {
            OWNER: Value.create(OWNER, 1),
            OWNED: Value.create(OWNED, 2),
            RELATION: Value.create(RELATION, Relation(
                "policy", {"whole": OWNER}, External("policy"),
            )),
        }
        state = State.create(values, {OWNER: (OWNED,)})
        runtime = Runtime(state, self.registry(OWNED_PRED).context)
        self.assertEqual(runtime.active.state.id, state.id)

    def test_writes_accept_reject_and_preserve_state(self):
        scalar = Runtime(cell_state(), self.registry().context)
        scalar.write(CELL, 4)
        before = snapshot(scalar)
        with self.assertRaises(CellContentRejected) as cm:
            scalar.write(CELL, 12)
        self.assertIs(cm.exception.result, VIO)
        self.assertEqual(snapshot(scalar), before)

        roles = Runtime(relation_state(), self.registry(ROLE_PRED).context)
        before = snapshot(roles)
        with self.assertRaises(RelationConstraintRejected) as cm:
            roles.write(CELL, 11)
        self.assertIs(cm.exception.result, VIO)
        self.assertEqual(snapshot(roles), before)

    def test_activation_and_trial_check_staged_cells(self):
        for transition in ("activate", "trial"):
            with self.subTest(transition=transition):
                source = cell_state(0, IsKind("int"))
                runtime = Runtime(source, self.registry().context)
                runtime.write(CELL, 3)
                accepted = transform_with_mapping(
                    source, {CELL: CellDeclaration(External("policy"), 0)},
                    {CELL: CELL},
                )
                original = snapshot(runtime)
                outcome = getattr(runtime, transition)(accepted)
                if transition == "activate":
                    self.assertIs(outcome, runtime.active)
                    self.assertEqual(runtime.read(CELL), 3)
                else:
                    self.assertEqual(outcome.read(CELL), 3)
                    self.assertEqual(snapshot(runtime), original)
                    outcome.end_trial()

                rejected_runtime = Runtime(source, self.registry().context)
                rejected_runtime.write(CELL, 12)
                before = snapshot(rejected_runtime)
                with self.assertRaises(ActivationRejected) as cm:
                    getattr(rejected_runtime, transition)(accepted)
                self.assertIs(cm.exception.result, VIO)
                self.assertEqual(snapshot(rejected_runtime), before)

    def test_missing_malformed_budget_and_strong_kleene(self):
        self.assertIs(External("absent").evaluate(3), UNK)
        context = self.registry().context
        self.assertIs(External("policy").evaluate(3, context), SAT)
        self.assertIs(External("policy").evaluate(12, context), VIO)
        self.assertIs(External("policy").evaluate(-1, context), UNK)
        self.assertIs(
            AllOf(External("policy"), External("absent"))
            .evaluate(12, context), VIO,
        )
        self.assertIs(
            AllOf(External("policy"), External("absent"))
            .evaluate(3, context), UNK,
        )
        exhausted = self.executor.registry({
            "policy": (self.deployment, PRED),
        }, budget=0)
        self.assertIs(External("policy").evaluate(3, exhausted.context), UNK)

        # Raw ordinary computation can return 17. Only the named External
        # result adapter must reject it as an invalid constraint verdict.
        self.assertEqual(
            self.executor.run(
                self.deployment, BAD_RESULT, 3, policy=PURE_POLICY,
            ),
            17,
        )
        with self.assertRaises(TypeError) as cm:
            External("policy").evaluate(
                3, self.registry(BAD_RESULT).context,
            )
        self.assertIn("result", str(cm.exception).lower())

    def test_restriction_preflight_and_transitive_calls(self):
        for entry, arguments in (
            (WRITE, (8,)), (CALL_WRITE, (8,)),
            (DEAD_WRITE, (8,)), (ACTIVATE, (8,)),
            (TRIAL, (8,)), (DYNAMIC, (PRED,)),
        ):
            with self.subTest(entry=entry.value):
                before = tuple(self.executor.trace())
                opened = []
                real_open = machine._open

                def spy(activation, args, *rest, **kwargs):
                    if activation.hold.version.state.id == self.source.id:
                        opened.append(activation.entity)
                    return real_open(activation, args, *rest, **kwargs)

                with mock.patch.object(machine, "_open", side_effect=spy):
                    with self.assertRaises(AdmissionRejected):
                        self.executor.run(
                            self.deployment, entry, *arguments,
                            policy=PURE_POLICY,
                        )
                self.assertEqual(opened, [], "code ran before rejection")
                additional = self.executor.trace()[len(before):]
                self.assertFalse(any(e.kind == "execute" for e in additional))

    def test_wrong_arity_preserves_language_boundary(self):
        with self.assertRaises(LanguageError) as cm:
            self.executor.run(self.deployment, PRED, policy=PURE_POLICY)

        error = cm.exception.error
        self.assertEqual(error[:2], ("language", "arity"))
        self.assertEqual(
            dict(error[2]),
            {"expected": 1, "function": PRED, "got": 0},
        )
        self.assertEqual(error[3][0], PRED)

    def test_replacement_is_not_retroactive_revalidation(self):
        state = State.create({
            CELL: Value.create(CELL, CellDeclaration(External("policy"), 3)),
            SECOND: Value.create(
                SECOND, CellDeclaration(External("policy"), 3),
            ),
        })
        registry = self.registry()
        first = Runtime(state, registry.context)
        before = (state.id, tuple(
            (entity, value.version_id) for entity, value in state.values.items()
        ))
        replaced = False
        real_open = machine._open

        def replace_during_first_call(activation, args, *rest, **kwargs):
            nonlocal replaced
            if activation.entity == PRED and not replaced:
                replaced = True
                registry.replace("policy", (self.deployment, NEGATIVE))
            return real_open(activation, args, *rest, **kwargs)

        registry.replace("policy", (self.deployment, PRED))
        with mock.patch.object(
            machine, "_open", side_effect=replace_during_first_call,
        ):
            another = Runtime(state, registry.context)
        self.assertTrue(replaced)
        self.assertEqual(another.read(CELL), 3)
        self.assertEqual(another.read(SECOND), 3)
        self.assertEqual((state.id, tuple(
            (entity, value.version_id) for entity, value in state.values.items()
        )), before)
        self.assertEqual(first.read(CELL), 3)
        self.assertEqual(another.read(SECOND), 3)

        with self.assertRaises(CellContentRejected) as cm:
            first.write(CELL, 3)
        self.assertIs(cm.exception.result, VIO)
        self.assertEqual(first.read(CELL), 3)

    def test_malformed_function_roles_are_not_normalized_away(self):
        loaded = self.source
        malformed_links = loaded.with_changes({
            EntityID("t32.malformed.links"): Relation("links", {
                "function": (CALL_WRITE,),
                "writer": WRITE,
            }),
        })
        self.assertEqual(load(malformed_links).id, malformed_links.id)
        with self.assertRaises(AdmissionRejected):
            self.executor.deploy(malformed_links, compiler_generation=1)

        definition = relation_of(loaded.values[CALL_WRITE])
        self.assertEqual(definition.kind, "definition")
        malformed_definition = loaded.with_changes({
            CALL_WRITE: Relation(
                definition.kind,
                {**definition.roles, "link:writer": (WRITE,)},
                definition.payload,
            ),
        })
        self.assertEqual(
            relation_of(malformed_definition.values[CALL_WRITE]).roles[
                "link:writer"
            ],
            (WRITE,),
        )
        self.assertEqual(load(malformed_definition).id, malformed_definition.id)
        with self.assertRaises(AdmissionRejected):
            self.executor.deploy(
                malformed_definition, compiler_generation=1,
            )

    def test_invalidated_deployment_fails_closed(self):
        missing = EntityID("t32.nonexistent")
        with self.assertRaises(AdmissionRejected):
            self.executor.run(self.deployment, missing, 3)
        self.executor.invalidate(self.deployment)
        with self.assertRaises(AdmissionRejected):
            self.executor.run(self.deployment, PRED, 3)

    def test_host_failure_cannot_be_caught_by_target_program(self):
        registry = self.registry()
        target_state = load(program({
            CELL: CellDeclaration(External("policy"), 3),
            WRITER: Function((), (
                "catch", ("write", "cell", ("lit", 4)),
            )),
            EntityID("t32.target.links"): links(WRITER, cell=CELL),
        }))
        target = Runtime(target_state, registry.context)
        session = HostedSession(target)
        session.prepare(compiler_generation=1)
        registry.replace("policy", (self.deployment, RAISE))
        before = snapshot(target)

        opened = []
        real_open = machine._open

        def observe(activation, args, *rest, **kwargs):
            chunk, env, node = real_open(
                activation, args, *rest, **kwargs,
            )
            if (
                activation.entity == RAISE
                and activation.hold.version.state.id == self.source.id
            ):
                key = (node, self.source.values[node].version_id)
                artifact = self.deployment.artifacts[key]
                self.assertIs(chunk, artifact.chunk)
                self.assertEqual(artifact.produced_by, 1)
                opened.append((node, artifact.artifact_id))
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
            with self.assertRaises(LanguageError) as cm:
                session.run(WRITER)

        self.assertEqual(len(opened), 1)
        self.assertEqual(
            cm.exception.error[:3],
            ("program", "evaluator_failure", "probe"),
        )
        self.assertEqual(cm.exception.error[3], (RAISE, opened[0][0]))
        self.assertEqual(snapshot(target), before)


if __name__ == "__main__":
    unittest.main()
