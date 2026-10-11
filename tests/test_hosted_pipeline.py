"""Plan-owned Task 30 bootstrap/admission acceptance; issue #66.

See docs/hosted_pipeline.md. The interface below is a provisional host-only
verification boundary, not a new SHEAR language capability:

    HostedSession(target_runtime).compiler_source_state
    .target_runtime
    .seed_manifest                   # roots, code_nodes, fixed_services,
                                     # compiler_source_state_id
    .rebuild_through(generation)     # GenerationReport sequence
    .compiler_artifacts(generation) # {(EntityID, VersionID): actual chunk}
    .invalidate_compiler_generation(generation)
    .attempt_seed_lower(node)        # diagnostic; fail closed if undeclared
    .prepare(compiler_generation=1)
    .produce(node), .admit(node, version, chunk, evidence)
    .run(entry, *args), .trace()
    .stage_edit(...)                  # used by the CLI's edit mode

GenerationReport: generation, producer_generation,
compiler_source_state_id, artifact_ids.

compiler_artifacts returns read-only bindings to the exact admitted chunk
objects consumed by the existing host machine. It must not return copies
or reconstructed equivalents.

The CLI main(argv) must use HostedSession.stage_edit for edit mode.
These tests deliberately fail before implementation; no ordinary host
fallback, fake events or test-only execution paths are permitted.
"""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from shear import EntityID, Runtime, VersionID, bytecode, relation_of
from shear import machine
from shear.examples._support import program
from shear import hosted_bootstrap
from shear.hosted_bootstrap import AdmissionRejected, HostedSession
from shear.lang import Function, LanguageError, links, load
from shear.operations import OPERATIONS
from shear.reconcile import reconcile
from shear.syntax import parse


TARGET = EntityID("gh66_target")
CALLER = EntityID("gh66_caller")
RAISER = EntityID("gh66_raiser")
CATCHER = EntityID("gh66_catcher")
SEED_ROOTS = frozenset({
    EntityID("lower"), EntityID("upper"), EntityID("evals"),
    EntityID("seq_code"), EntityID("compile_node"),
})


def fixture():
    """A target program with no compiler entities or compiler links."""
    return Runtime(load(program({
        TARGET: Function(("x",), ("add", ("arg", "x"), ("lit", 3))),
        CALLER: Function(("x",), ("call", "callee", ("arg", "x"))),
        EntityID("gh66_caller.links"): links(CALLER, callee=TARGET),
    })))


def body_node(state, function):
    return relation_of(state.values[function]).roles["body"]


def snapshot(state):
    return (
        state.id,
        tuple(sorted(
            (entity.value, value.version_id)
            for entity, value in state.values.items()
        )),
    )


def no_host_lowering(*args, **kwargs):
    raise AssertionError("Undeclared host lowering is forbidden")


def independent_seed_closure(state):
    """Traverse canonical definitions and links, not the seed builder."""
    pending = list(SEED_ROOTS)
    visited = set()
    expected = set()
    owners = {}

    while pending:
        function = pending.pop()
        if function in visited:
            continue
        visited.add(function)

        definition = relation_of(state.values[function])
        assert definition.kind == "definition", function

        for entity in state.owned_subtree(function):
            if entity == function:
                continue
            relation = relation_of(state.values[entity])
            assert relation is not None and relation.kind in OPERATIONS
            assert relation.kind != "invalid", entity
            key = (entity, state.values[entity].version_id)
            expected.add(key)
            owners[key] = function

        for role, target in definition.roles.items():
            if not role.startswith("link:"):
                continue
            targets = (target,) if isinstance(target, EntityID) else target
            for linked in targets:
                relation = relation_of(state.values[linked])
                if relation is not None and relation.kind == "definition":
                    pending.append(linked)

    return expected, owners


class CompilerBoundaryTests(unittest.TestCase):

    def test_compiler_free_target_does_not_acquire_compiler_code(self):
        target = fixture()
        target_before = snapshot(target.active.state)
        self.assertTrue(SEED_ROOTS.isdisjoint(target.active.state.values))

        session = HostedSession(target)
        compiler = session.compiler_source_state
        compiler_before = snapshot(compiler)

        self.assertNotEqual(compiler.id, target.active.state.id)
        self.assertTrue(SEED_ROOTS <= set(compiler.values))
        self.assertEqual(
            session.seed_manifest.compiler_source_state_id, compiler.id,
        )

        session.prepare(compiler_generation=1)
        self.assertEqual(session.run(CALLER, 4), 7)
        self.assertEqual(snapshot(target.active.state), target_before)
        self.assertEqual(snapshot(compiler), compiler_before)
        self.assertTrue(SEED_ROOTS.isdisjoint(target.active.state.values))

        executed = [
            e for e in session.trace()
            if e.kind == "execute" and e.route == "admitted-host"
        ]
        self.assertTrue(executed)
        self.assertTrue(all(
            e.target_state_id == target_before[0] for e in executed
        ))


class GenerationTests(unittest.TestCase):

    def test_three_generations_execute_their_predecessors(self):
        runtime = fixture()
        session = HostedSession(runtime)
        compiler = session.compiler_source_state
        target_before = snapshot(runtime.active.state)
        compiler_before = snapshot(compiler)

        reports = session.rebuild_through(1)

        self.assertEqual(
            [(r.generation, r.producer_generation) for r in reports],
            [(1, 0)],
        )

        # Observe the actual chunk returned to the machine when it opens
        # a compiler function. The artifact registry must return the
        # exact immutable chunk objects, not structural copies.
        #
        # G2 may consume only G1 compiler chunks; G3 may consume only G2.
        # Using G0 again, even with correctly relabelled trace records,
        # must not satisfy these assertions.
        original_open = machine._open

        for predecessor in (1, 2):
            with self.subTest(producer_generation=predecessor):
                admitted = session.compiler_artifacts(predecessor)
                observed = []

                def observe_open(activation, args, *other, **kwargs):
                    chunk, env, node = original_open(
                        activation, args, *other, **kwargs
                    )

                    if (
                        activation.hold.version.state.id
                        == compiler.id
                    ):
                        key = (
                            node,
                            compiler.values[node].version_id,
                        )
                        observed.append((key, chunk))

                    return chunk, env, node

                with mock.patch.object(
                    machine, "_open", side_effect=observe_open,
                ):
                    session.rebuild_through(predecessor + 1)

                self.assertTrue(
                    observed,
                    f"G{predecessor + 1} did not open compiler code",
                )

                for key, actual_chunk in observed:
                    with self.subTest(node=key[0]):
                        self.assertIn(key, admitted)
                        self.assertIs(
                            actual_chunk,
                            admitted[key],
                            "The machine did not consume the admitted "
                            f"G{predecessor} executable chunk",
                        )

                self.assertIn(
                    (
                        body_node(compiler, EntityID("compile_node")),
                        compiler.values[
                            body_node(compiler, EntityID("compile_node"))
                        ].version_id,
                    ),
                    {key for key, _ in observed},
                    "Successor production did not execute compile_node",
                )

        reports = session.rebuild_through(3)

        self.assertEqual(
            [(r.generation, r.producer_generation) for r in reports],
            [(1, 0), (2, 1), (3, 2)],
        )
        self.assertEqual(
            [r.compiler_source_state_id for r in reports],
            [compiler.id] * 3,
        )

        expected_nodes, _ = independent_seed_closure(compiler)
        prior_ids = set()

        for g, report in enumerate(reports, 1):
            with self.subTest(generation=g):
                actual = session.compiler_artifacts(g)
                self.assertEqual(set(actual), expected_nodes)

                ids = set(report.artifact_ids)
                self.assertTrue(ids)
                self.assertFalse(prior_ids & ids)
                prior_ids |= ids

                for (entity, _version), chunk in actual.items():
                    self.assertEqual(
                        chunk,
                        bytecode.lower(
                            relation_of(compiler.values[entity])
                        ),
                    )

        self.assertEqual(
            session.compiler_artifacts(1),
            session.compiler_artifacts(2),
        )
        self.assertEqual(
            session.compiler_artifacts(2),
            session.compiler_artifacts(3),
        )

        events = session.trace()

        for g in (1, 2, 3):
            self.assertTrue(any(
                event.kind == "produce"
                and event.route == "shear-compiler"
                and event.generation == g
                and event.compiler_generation == g - 1
                for event in events
            ), f"No compiler production observed for G{g}")

        session.prepare(compiler_generation=3)

        with (
            mock.patch.object(
                bytecode, "chunk_of", side_effect=no_host_lowering,
            ),
            mock.patch.object(
                bytecode, "lower_value", side_effect=no_host_lowering,
            ),
        ):
            self.assertEqual(session.run(CALLER, 4), 7)

        self.assertEqual(snapshot(runtime.active.state), target_before)
        self.assertEqual(snapshot(compiler), compiler_before)

    def test_a_missing_predecessor_blocks_a_successor(self):
        for predecessor in (1, 2):
            with self.subTest(missing_generation=predecessor):
                session = HostedSession(fixture())
                session.rebuild_through(predecessor)
                session.invalidate_compiler_generation(predecessor)

                with self.assertRaises(AdmissionRejected):
                    session.rebuild_through(predecessor + 1)

    def test_seed_is_the_exact_independently_derived_closure(self):
        session = HostedSession(fixture())
        compiler = session.compiler_source_state
        manifest = session.seed_manifest
        expected, owners = independent_seed_closure(compiler)

        self.assertEqual(manifest.compiler_source_state_id, compiler.id)
        self.assertEqual(set(manifest.roots), SEED_ROOTS)
        self.assertTrue(manifest.fixed_services)

        declared = {
            (entry.entity, entry.version) for entry in manifest.code_nodes
        }
        self.assertEqual(len(declared), len(manifest.code_nodes))
        self.assertEqual(declared, expected)

        for entry in manifest.code_nodes:
            self.assertEqual(
                owners[(entry.entity, entry.version)], entry.owner,
            )

        target = fixture()
        second = HostedSession(target)
        self.assertEqual(second.seed_manifest, manifest)

        foreign = body_node(target.active.state, TARGET)
        self.assertNotIn(foreign, compiler.values)

        with self.assertRaises(AdmissionRejected):
            second.attempt_seed_lower(foreign)

        # A real node in the compiler state, but outside the permitted
        # dependency closure, must also be rejected.
        unrelated = (
            set(compiler.values)
            - {entity for entity, _version in expected}
            - SEED_ROOTS
        )
        unrelated_code = [
            entity for entity in unrelated
            if (
                (relation := relation_of(compiler.values[entity]))
                is not None
                and relation.kind in OPERATIONS
            )
        ]

        if unrelated_code:
            with self.assertRaises(AdmissionRejected):
                session.attempt_seed_lower(unrelated_code[0])

        self.assertEqual(second.seed_manifest, manifest)

        session.rebuild_through(3)
        lower_events = [
            e for e in session.trace() if e.kind == "host-lower"
        ]
        self.assertTrue(lower_events)

        for event in lower_events:
            self.assertEqual(event.route, "declared-seed")
            self.assertIn(
                (event.entity, event.version), expected,
            )

        self.assertEqual(manifest, session.seed_manifest)

    def test_rebuild_does_not_define_or_activate_either_source(self):
        runtime = fixture()
        session = HostedSession(runtime)
        original = runtime.active.state
        compiler = session.compiler_source_state
        target_before = snapshot(original)
        compiler_before = snapshot(compiler)

        session.rebuild_through(3)

        self.assertIs(runtime.active.state, original)
        self.assertEqual(snapshot(runtime.active.state), target_before)
        self.assertEqual(snapshot(compiler), compiler_before)
        self.assertFalse(any(
            e.kind in {"define", "activate"} for e in session.trace()
        ))


class AdmissionTests(unittest.TestCase):

    def setUp(self):
        self.runtime = fixture()
        self.state = self.runtime.active.state
        self.node = body_node(self.state, TARGET)
        self.version = self.state.values[self.node].version_id

        self.session = HostedSession(self.runtime)
        self.session.prepare(compiler_generation=1)

    def test_genuine_compiler_output_matches_independent_oracle(self):
        chunk, evidence = self.session.produce(self.node)

        self.assertIsNotNone(evidence)
        self.assertEqual(
            chunk,
            bytecode.lower(relation_of(self.state.values[self.node])),
        )
        self.assertIsNotNone(
            self.session.admit(self.node, self.version, chunk, evidence)
        )

    def test_forged_evidence_is_rejected(self):
        chunk, _ = self.session.produce(self.node)

        for fake in (
            object(),
            ("shear-compiler", TARGET.value),
            ("admitted", self.node.value),
        ):
            with self.subTest(evidence=type(fake).__name__):
                with self.assertRaises(AdmissionRejected):
                    self.session.admit(
                        self.node, self.version, chunk, fake,
                    )

    def test_evidence_cannot_authorize_another_version(self):
        chunk, evidence = self.session.produce(self.node)

        with self.assertRaises(AdmissionRejected):
            self.session.admit(
                self.node,
                VersionID("incorrect-version"),
                chunk,
                evidence,
            )

    def test_evidence_cannot_authorize_modified_chunk(self):
        chunk, evidence = self.session.produce(self.node)
        altered = list(chunk)

        index = next(
            i for i, instruction in enumerate(altered)
            if instruction[0] == "EVAL"
        )
        altered[index] = (
            "EVAL", body_node(self.state, CALLER),
        )

        self.assertNotEqual(tuple(altered), chunk)

        with self.assertRaises(AdmissionRejected):
            self.session.admit(
                self.node, self.version, tuple(altered), evidence,
            )

    def test_linked_callee_is_admitted(self):
        self.assertEqual(self.session.run(CALLER, 5), 8)

        executed = [
            e for e in self.session.trace()
            if e.kind == "execute" and e.route == "admitted-host"
        ]

        self.assertTrue(executed)
        self.assertIn(
            self.node, {e.entity for e in executed},
        )
        self.assertTrue(all(
            e.artifact_id and e.version is not None
            for e in executed
        ))


class ErrorOperatorTests(unittest.TestCase):

    def test_catch_raise_and_unmatched_filter(self):
        runtime = Runtime(load(program({
            RAISER: Function(
                ("x",),
                ("raise", ("lit", "own_error"), ("arg", "x")),
            ),
            CATCHER: Function(
                ("x",),
                (
                    "catch",
                    ("call", "raiser", ("arg", "x")),
                    ("own_error",),
                ),
            ),
            EntityID("gh66_catcher.links"): links(
                CATCHER, raiser=RAISER,
            ),
        })))

        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
        raised_node = body_node(runtime.active.state, RAISER)

        expected = (
            "failed",
            ("program", "own_error", 7, (RAISER, raised_node)),
        )

        self.assertEqual(session.run(CATCHER, 7), expected)

        with self.assertRaises(LanguageError) as caught:
            session.run(RAISER, 7)

        self.assertEqual(caught.exception.error, expected[1])


class CommandTests(unittest.TestCase):

    def command(self, source_text, edited_text=None, in_process=False):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "original.txt"
            source.write_text(source_text, encoding="utf-8")

            args = [
                "--source-file", str(source),
                "--entry", "answer",
                "--args-json", "[40]",
            ]

            if edited_text is not None:
                edited = Path(directory) / "edited.txt"
                edited.write_text(edited_text, encoding="utf-8")
                args.extend([
                    "--edited-source-file", str(edited),
                    "--edit-mode", "prepare",
                ])

            if in_process:
                output = StringIO()
                with redirect_stdout(output):
                    status = hosted_bootstrap.main(args)
                self.assertEqual(status, 0)
                return json.loads(output.getvalue())

            result = subprocess.run(
                [sys.executable, "-m", "shear.hosted_bootstrap", *args],
                capture_output=True,
                text=True,
                timeout=120,
            )

        self.assertEqual(
            result.returncode,
            0,
            result.stdout + result.stderr,
        )
        return json.loads(result.stdout)

    def test_compiler_free_source_text_to_admitted_execution(self):
        output = self.command("fn answer(x):\n    x + 2\n")
        self.assertEqual(output["result"], 42)
        self.assertEqual(output["route"], "admitted-host")
        self.assertTrue(output["executed_artifacts"])

    def test_reconciliation_stages_candidate_without_activation(self):
        original = "fn answer(x):\n    x + 1\n"
        edited = "fn answer(x):\n    x + 2\n"

        base = load(parse(original))
        candidate = reconcile(base, edited).destination
        entry = EntityID("answer")
        old_body = body_node(base, entry)
        new_body = body_node(candidate, entry)

        observed_sessions = []
        real_stage = HostedSession.stage_edit

        def observed_stage(session, *args, **kwargs):
            original_state = session.target_runtime.active.state
            observed_sessions.append((session, original_state))

            result = real_stage(session, *args, **kwargs)

            self.assertIs(
                session.target_runtime.active.state,
                original_state,
                "Candidate preparation changed the original active state",
            )
            return result

        # Exercise the in-process API actually used by the CLI.
        # Reporting the original active_state_id is not sufficient:
        # any attempt to activate must fail the independent guard.
        with (
            mock.patch.object(
                HostedSession, "stage_edit", observed_stage,
            ),
            mock.patch.object(
                Runtime,
                "activate",
                side_effect=AssertionError(
                    "Edit preparation must not activate a candidate"
                ),
            ) as activation_guard,
        ):
            output = self.command(
                original, edited, in_process=True,
            )

        self.assertEqual(activation_guard.call_count, 0)
        self.assertEqual(len(observed_sessions), 1)

        session, original_state = observed_sessions[0]
        self.assertEqual(original_state.id, base.id)
        self.assertIs(
            session.target_runtime.active.state, original_state,
        )

        self.assertEqual(output["result"], 41)
        self.assertEqual(output["candidate_result"], 42)
        self.assertEqual(output["route"], "admitted-host")
        self.assertEqual(output["base_state_id"], base.id.value)
        self.assertEqual(
            output["candidate_state_id"], candidate.id.value,
        )
        self.assertEqual(output["active_state_id"], base.id.value)
        self.assertNotEqual(base.id, candidate.id)
        self.assertIn(entry, base.values)
        self.assertIn(entry, candidate.values)

        continuity = output["continuity"][entry.value]
        self.assertEqual(continuity["entity"], entry.value)
        self.assertEqual(
            continuity["original_body"], old_body.value,
        )
        self.assertEqual(
            continuity["candidate_body"], new_body.value,
        )
        self.assertEqual(
            continuity["original_version"],
            base.values[old_body].version_id.value,
        )
        self.assertEqual(
            continuity["candidate_version"],
            candidate.values[new_body].version_id.value,
        )

        self.assertTrue(output["executed_artifacts"])
        seen_states = {
            event["target_state_id"]
            for event in output["executed_artifacts"]
            if event["route"] == "admitted-host"
        }
        self.assertEqual(
            seen_states, {base.id.value, candidate.id.value},
        )


if __name__ == "__main__":
    unittest.main()
