"""Execute-owned tests of the hosted-bootstrap implementation.

The Plan-owned acceptance tests (test_hosted_*.py) fix the public contract.
These check the parts behind it that a wrong implementation could still
satisfy: that the SHEAR compiler agrees with host lowering node by node,
that admission refuses every kind of bad evidence, that the seed manifest is
the seed of the source, and that the machine's per-run resolver hook is
scoped to the run.

See docs/hosted_pipeline.md and issue #66.
"""

from __future__ import annotations

import contextlib
import dataclasses
import io
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from shear import EntityID, Runtime, bytecode, machine
from shear.canonical import canonicalize
from shear.examples import EXAMPLES
from shear.examples._support import program
from shear.hosted_bootstrap import AdmissionRejected, HostedSession
from shear.hosted_bootstrap import seed
from shear.hosted_bootstrap.command import _jsonable
from shear.hosted_bootstrap.descriptors import (
    SUPPORTED_KINDS,
    _plain,
    decode_chunk,
    describe,
)
from shear.hosted_bootstrap.errors import UnsupportedOperation
from shear.hosted_bootstrap.trace import HOST_LOWER
from shear.hosted_bootstrap.validation import validate_chunk
from shear.lang import (
    NODE_KINDS,
    Function,
    LanguageError,
    _definition_of,
    define,
    links,
    load,
)
from shear.lang import run as reference_run
from shear.relations import relation_of


F = EntityID("hb_f")
G = EntityID("hb_g")
H = EntityID("hb_h")


def small_runtime():
    return Runtime(load(program({
        F: Function(("n",), ("call", "g", ("arg", "n"))),
        EntityID("hb_f.links"): links(F, g=G),
        G: Function(("n",), ("add", ("arg", "n"), ("lit", 1))),
        H: Function(("n",), ("add", ("arg", "n"), ("lit", 2))),
    })))


def body(state, function):
    return relation_of(state.values[function]).roles["body"]


def code_nodes(state):
    for owner in sorted(state.values, key=lambda e: e.value):
        if _definition_of(state.values[owner]) is None:
            continue

        for node in sorted(
            state.owned_subtree(owner) - {owner},
            key=lambda e: e.value,
        ):
            yield node


class CompilerAgreesWithHostLowering(unittest.TestCase):
    """The independent oracle: ``bytecode.lower`` on the same node."""

    def test_every_supported_corpus_node(self):
        compared = 0

        for example in EXAMPLES:
            with self.subTest(example=example.name):
                runtime = Runtime(load(example.program), example.context)
                state = runtime.active.state
                session = HostedSession(runtime)
                session.prepare(compiler_generation=1)

                for node in code_nodes(state):
                    relation = relation_of(state.values[node])

                    if relation.kind not in SUPPORTED_KINDS:
                        with self.assertRaises(UnsupportedOperation):
                            session.produce(node)

                        continue

                    chunk, _ = session.produce(node)
                    self.assertEqual(
                        chunk, bytecode.lower(relation),
                        (example.name, node.value, relation.kind),
                    )
                    compared += 1

        self.assertGreater(compared, 1000)

    def test_later_generations_produce_the_same_chunks(self):
        session = HostedSession(small_runtime())
        reports = session.rebuild_through(3)

        self.assertEqual([r.generation for r in reports], [1, 2, 3])
        first = session.compiler_artifacts(1)

        for generation in (2, 3):
            later = session.compiler_artifacts(generation)
            self.assertEqual(set(later), set(first))

            for key in first:
                self.assertEqual(later[key], first[key], (generation, key))


class AdmissionRefusesBadEvidence(unittest.TestCase):

    def setUp(self):
        self.runtime = small_runtime()
        self.session = HostedSession(self.runtime)
        self.session.prepare(compiler_generation=1)
        self.state = self.runtime.active.state
        self.node = body(self.state, G)
        self.version = self.state.values[self.node].version_id
        self.chunk, self.evidence = self.session.produce(self.node)

    def rejected(self, **changes):
        arguments = dict(
            node=self.node, version=self.version,
            chunk=self.chunk, evidence=self.evidence,
        )
        arguments.update(changes)

        with self.assertRaises(AdmissionRejected):
            self.session.admit(**arguments)

    def test_the_honest_triple_is_admitted(self):
        artifact = self.session.admit(
            self.node, self.version, self.chunk, self.evidence,
        )

        self.assertEqual(artifact.chunk, self.chunk)
        self.assertEqual(artifact.entity, self.node)

    def test_foreign_or_fabricated_evidence(self):
        for evidence in (object(), None, 0, [], "evidence"):
            with self.subTest(evidence=evidence):
                self.rejected(evidence=evidence)

    def test_evidence_of_another_node(self):
        other = body(self.state, F)
        _, other_evidence = self.session.produce(other)

        self.rejected(evidence=other_evidence)

    def test_node_or_version_not_the_one_produced(self):
        self.rejected(node=body(self.state, F))
        self.rejected(node=EntityID("hb_missing"))
        self.rejected(version=self.state.values[body(self.state, F)].version_id)

    def test_chunk_not_the_compilers_result(self):
        self.rejected(chunk=(("LIT", 999), ("END",)))
        self.rejected(chunk=list(self.chunk))
        self.rejected(chunk=self.chunk[:-1])

    def test_malformed_chunks_with_matching_production(self):
        """Structural validation stands on its own: even a chunk that is
        what the compiler 'returned' must be well formed for the node."""

        for chunk in (
            (),
            (("END",), ("LIT", 1)),
            (("NOPE", 1), ("END",)),
            (("LIT",), ("END",)),
            ("LIT", ("END",)),
            ((), ("END",)),
        ):
            with self.subTest(chunk=chunk):
                with self.assertRaises(AdmissionRejected):
                    validate_chunk(self.state, self.node, G, chunk)

    def test_call_target_must_be_linked(self):
        caller = body(self.state, F)
        owner = F
        good = self.session.produce(caller)[0]
        calls = [i for i in good if i[0] == "CALL"]

        self.assertTrue(calls)
        forged = tuple(
            ("CALL", H, *i[2:]) if i[0] == "CALL" else i for i in good
        )

        with self.assertRaises(AdmissionRejected):
            validate_chunk(self.state, caller, owner, forged)

    def test_a_node_with_no_artifact_cannot_run(self):
        runtime = small_runtime()
        session = HostedSession(runtime)

        with self.assertRaises(AdmissionRejected):
            session.run(F, 1)

    def test_state_change_forces_preparation(self):
        runtime = small_runtime()
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
        self.assertEqual(session.run(G, 1), 2)
        runtime.activate(define(runtime.active.state, {
            G: Function(("n",), ("add", ("arg", "n"), ("lit", 7))),
        }))

        with self.assertRaises(AdmissionRejected):
            session.run(G, 1)

        session.prepare(compiler_generation=1)
        self.assertEqual(session.run(G, 1), 8)


class DescriptorBoundary(unittest.TestCase):

    def test_non_code_entities_are_not_described(self):
        runtime = small_runtime()
        state = runtime.active.state

        for entity in (F, EntityID("hb_missing"), EntityID("hb_f.links")):
            with self.subTest(entity=entity):
                with self.assertRaises(AdmissionRejected):
                    describe(state, entity, F)

    def test_unsupported_operations_are_named_not_lowered(self):
        self.assertEqual(
            set(NODE_KINDS) - SUPPORTED_KINDS,
            {"activate", "function", "quote", "trial", "unquote"},
        )

    def test_results_that_are_not_chunks_are_refused(self):
        for result in (5, "chunk", None, (("LIT", 1), 5), ((1, 2),), ((),)):
            with self.subTest(result=result):
                with self.assertRaises(AdmissionRejected):
                    decode_chunk(canonicalize(result))

    def test_a_literal_stays_canonical_and_identities_become_plain(self):
        chunk = decode_chunk(canonicalize((
            ("LIT", (1, 2)),
            ("REF", EntityID("x")),
            ("END",),
        )))

        self.assertEqual(chunk[0], ("LIT", canonicalize((1, 2))))
        self.assertEqual(chunk[1], ("REF", EntityID("x")))
        self.assertEqual(chunk[2], ("END",))


class SeedIsExactlyTheDeclaredNodes(unittest.TestCase):

    def test_checked_in_manifest_is_the_seed_of_the_source(self):
        source = seed.compiler_source_state()

        self.assertEqual(seed.load_manifest(), seed.derive(source))
        self.assertEqual(seed.verified_manifest(), seed.derive(source))

    def test_a_manifest_that_differs_is_refused(self):
        data = json.loads(seed.MANIFEST_PATH.read_text(encoding="utf-8"))
        damaged = dict(data, code_nodes=data["code_nodes"][1:])

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(damaged), encoding="utf-8")

            self.assertNotEqual(
                seed.load_manifest(path),
                seed.derive(seed.compiler_source_state()),
            )

            path.write_text("{not json", encoding="utf-8")

            with self.assertRaises(AdmissionRejected):
                seed.load_manifest(path)

            path.write_text(
                json.dumps(dict(data, schema_version=99)), encoding="utf-8",
            )

            with self.assertRaises(AdmissionRejected):
                seed.load_manifest(path)

    def test_every_undeclared_compiler_code_node_is_refused(self):
        """Unconditional: the protected test skips this when no such node
        exists, so assert that some do."""

        session = HostedSession(small_runtime())
        source = session.compiler_source_state
        declared = {n.entity for n in session.seed_manifest.code_nodes}
        undeclared = [
            entity for entity, value in source.values.items()
            if entity not in declared
            and (r := relation_of(value)) is not None
            and r.kind in NODE_KINDS
        ]

        self.assertTrue(undeclared)

        for entity in undeclared:
            with self.subTest(entity=entity.value):
                with self.assertRaises(AdmissionRejected):
                    session.attempt_seed_lower(entity)

    def test_the_documented_command_checks_the_manifest(self):
        done = subprocess.run(
            [sys.executable, "-m", "shear.hosted_bootstrap.seed_cli"],
            capture_output=True, text=True, cwd=seed.MANIFEST_PATH.parents[2],
        )

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("the seed manifest is current", done.stdout)

    def test_write_regenerates_exactly_the_checked_in_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"

            with (
                mock.patch.object(seed, "MANIFEST_PATH", path),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(seed.main(["--write"]), 0)

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                seed.MANIFEST_PATH.read_text(encoding="utf-8"),
            )

    def test_a_stale_manifest_is_reported_with_status_one(self):
        damaged = seed.derive(seed.compiler_source_state())
        damaged = dataclasses.replace(damaged, code_nodes=damaged.code_nodes[1:])

        with (
            mock.patch.object(seed, "load_manifest", return_value=damaged),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(seed.main([]), 1)

    def test_importing_the_module_runs_no_command(self):
        done = subprocess.run(
            [sys.executable, "-c", "import shear.hosted_bootstrap.seed"],
            capture_output=True, text=True, cwd=seed.MANIFEST_PATH.parents[2],
        )

        self.assertEqual((done.returncode, done.stdout), (0, ""), done.stderr)

    def test_the_command_refuses_unknown_arguments(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(seed.main(["--nope"]), 2)

    def test_only_declared_nodes_lower_on_the_host(self):
        session = HostedSession(small_runtime())
        declared = session.seed_manifest.code_nodes[0].entity

        self.assertEqual(
            session.attempt_seed_lower(declared)[-1], ("END",),
        )

        undeclared = body(session.target_runtime.active.state, G)

        with self.assertRaises(AdmissionRejected):
            session.attempt_seed_lower(undeclared)

        host = [e for e in session.trace() if e.kind == "host-lower"]
        self.assertTrue(host)
        self.assertTrue(all(e.route == "declared-seed" for e in host))


class AdmissionChecksTheStack(unittest.TestCase):
    """A chunk that is well formed instruction by instruction can still be
    unsound as a whole (docs/hosted_pipeline.md section 6, item 4)."""

    def setUp(self):
        self.runtime = Runtime(load(program({
            F: Function((), ("add", ("lit", 1), ("lit", 2))),
            G: Function((), ("seq", ("lit", 1), ("lit", 2))),
            H: Function(("n",), ("arg", "n")),
        })))
        self.state = self.runtime.active.state
        session = HostedSession(self.runtime)
        session.prepare(compiler_generation=1)
        self.session = session

    def chunk(self, function):
        node = body(self.state, function)

        return node, self.session.produce(node)[0]

    def check(self, function, chunk):
        node = body(self.state, function)

        validate_chunk(self.state, node, function, chunk)

    def rejects(self, function, chunk):
        with self.assertRaises(AdmissionRejected):
            self.check(function, chunk)

    def test_the_compilers_own_chunks_are_sound(self):
        for function in (F, G, H):
            self.check(function, self.chunk(function)[1])

    def test_stack_underflow(self):
        self.rejects(F, (("ADD",), ("END",)))

        _, add = self.chunk(F)
        evals = [i for i in add if i[0] == "EVAL"]
        self.rejects(F, (evals[0], ("ADD",), ("END",)))
        self.rejects(F, (("POP",), ("END",)))

    def test_a_chunk_must_end_with_exactly_one_value(self):
        _, add = self.chunk(F)
        evals = [i for i in add if i[0] == "EVAL"]

        self.rejects(F, (("END",),))
        self.rejects(F, (*evals, ("END",)))
        self.rejects(F, (*evals, ("ADD",), ("POP",), ("END",)))

    def test_end_must_be_last_and_nothing_follows_a_handover(self):
        _, seq = self.chunk(G)
        goto = next(i for i in seq if i[0] == "GOTO")
        head = seq[:seq.index(goto)]

        self.check(G, seq)
        self.rejects(G, (*head, goto, ("LIT", 1), ("END",)))
        self.rejects(G, (("END",), *seq))
        self.rejects(G, (*head, ("END",), goto, ("END",)))

    def test_a_handover_leaves_the_stack_empty(self):
        _, seq = self.chunk(G)
        goto = next(i for i in seq if i[0] == "GOTO")

        self.rejects(G, (("LIT", 1), goto, ("END",)))
        self.rejects(G, tuple(i for i in seq if i[0] != "POP"))

    def test_nothing_follows_a_raise(self):
        raised = (("RAISE", "invalid"), ("LIT", 1), ("END",))

        self.rejects(F, raised)

    def test_operands_must_have_their_type(self):
        node, arg = self.chunk(H)

        self.check(H, arg)
        self.rejects(H, (("ARG", 5), ("END",)))
        self.rejects(H, (("ARG",), ("END",)))
        self.rejects(H, (("ARG", "n", "extra"), ("END",)))


class OperationWitnesses(unittest.TestCase):
    """``applyv`` and ``linksof`` are not in the protected corpus subset
    (docs/hosted_pipeline.md section 2). Each runs here on admitted
    artifacts with host lowering forbidden, and agrees with ordinary host
    execution on an independent runtime."""

    MAKE = EntityID("hb_make")
    CALL_V = EntityID("hb_call_v")
    VIA_REF = EntityID("hb_via_ref")
    LINKS = EntityID("hb_links")

    def entities(self):
        return {
            self.MAKE: Function(
                ("n",),
                (
                    "closure",
                    ("x",),
                    ("n",),
                    ("add", ("arg", "n"), ("arg", "x")),
                ),
            ),
            self.CALL_V: Function(
                ("f", "args"), ("applyv", ("arg", "f"), ("arg", "args")),
            ),
            self.VIA_REF: Function(
                (),
                (
                    "applyv",
                    ("ref", "target"),
                    ("tuple", ("lit", 2), ("lit", 3)),
                ),
            ),
            EntityID("hb_via_ref.links"): links(self.VIA_REF, target=G),
            G: Function(
                ("a", "b"), ("mul", ("arg", "a"), ("arg", "b")),
            ),
            self.LINKS: Function((), ("linksof", "callee")),
            EntityID("hb_links.links"): links(self.LINKS, callee=F),
            F: Function(("n",), ("call", "g", ("arg", "n"))),
            EntityID("hb_f.links"): links(F, g=H),
            H: Function(("n",), ("add", ("arg", "n"), ("lit", 1))),
        }

    def admitted(self, entry, *args):
        state = load(program(self.entities()))
        runtime = Runtime(state)
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)

        def forbidden(*a, **k):
            raise AssertionError("host lowering reached")

        with (
            mock.patch.object(bytecode, "chunk_of", side_effect=forbidden),
            mock.patch.object(bytecode, "lower_value", side_effect=forbidden),
        ):
            result = session.run(entry, *args)

        oracle = reference_run(Runtime(load(program(self.entities()))), entry, *args)

        return state, session, result, oracle

    def executed(self, session, state, function, kind):
        nodes = {
            e for e in state.owned_subtree(function)
            if (r := relation_of(state.values[e])) is not None
            and r.kind == kind
        }
        events = {
            e.entity for e in session.trace()
            if e.kind == "execute" and e.route == "admitted-host"
        }

        self.assertTrue(nodes)
        self.assertTrue(nodes <= events, (kind, nodes - events))

    def test_applyv_on_a_reference_to_a_linked_function(self):
        state, session, result, oracle = self.admitted(self.VIA_REF)

        self.assertEqual(result, 6)
        self.assertEqual(result, oracle)
        self.executed(session, state, self.VIA_REF, "applyv")

    def test_applyv_on_a_closure_returned_by_an_admitted_run(self):
        state = load(program(self.entities()))
        runtime = Runtime(state)
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
        adder = session.run(self.MAKE, 4)
        result = session.run(self.CALL_V, adder, (6,))
        oracle_runtime = Runtime(load(program(self.entities())))
        expected = reference_run(
            oracle_runtime, self.CALL_V,
            reference_run(oracle_runtime, self.MAKE, 4), (6,),
        )

        self.assertEqual(result, 10)
        self.assertEqual(result, expected)
        self.executed(session, state, self.CALL_V, "applyv")

    def test_linksof_returns_the_link_table_of_a_linked_function(self):
        state, session, result, oracle = self.admitted(self.LINKS)

        self.assertEqual(result, oracle)
        self.assertEqual(
            tuple(sorted(result)), tuple(sorted(oracle)),
        )
        self.assertTrue(result)
        self.executed(session, state, self.LINKS, "linksof")


class MissingArtifactsFailClosed(unittest.TestCase):
    """After preparation a missing artifact must fail the run; neither lazy
    host lowering nor a cached host chunk may supply it (hosted_pipeline.md
    sections 6 and 9)."""

    def run_forbidding_host_lowering(self, session, entry, *args):
        def forbidden(*a, **k):
            raise AssertionError("host lowering reached")

        with (
            mock.patch.object(bytecode, "chunk_of", side_effect=forbidden),
            mock.patch.object(bytecode, "lower_value", side_effect=forbidden),
        ):
            return session.run(entry, *args)

    def test_a_withheld_callee_artifact(self):
        runtime = small_runtime()
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
        callee = body(runtime.active.state, G)
        version = runtime.active.state.values[callee].version_id
        artifacts = session._target._artifacts

        self.assertEqual(self.run_forbidding_host_lowering(session, F, 1), 2)

        del artifacts._chunks[(callee, version)]
        del artifacts._artifacts[(callee, version)]

        with self.assertRaises(AdmissionRejected):
            self.run_forbidding_host_lowering(session, F, 1)

    def test_an_unsupported_node_is_recorded_and_never_lowered(self):
        entry = EntityID("hb_quoted")
        runtime = Runtime(load(program({
            entry: Function((), ("quote", ("lit", 1))),
        })))
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
        rejected = [e for e in session.trace() if e.kind == "reject"]

        self.assertTrue(rejected)

        with self.assertRaises(AdmissionRejected):
            self.run_forbidding_host_lowering(session, entry)


class RecordsAreImmutable(unittest.TestCase):
    """The pipeline's records are frozen (CLAUDE.md): nothing can edit an
    admitted artifact, the manifest or the trace after the fact."""

    def records(self):
        runtime = small_runtime()
        session = HostedSession(runtime)
        reports = session.rebuild_through(1)
        session.prepare(compiler_generation=1)
        state = runtime.active.state
        node = body(state, G)
        chunk, evidence = session.produce(node)
        artifact = session.admit(
            node, state.values[node].version_id, chunk, evidence,
        )
        text = "fn hb_f(n):\n    n + 1\n"
        staged = session.stage_edit(text, EntityID("hb_f"), (1,))

        return {
            "artifact": artifact,
            "seed node": session.seed_manifest.code_nodes[0],
            "manifest": session.seed_manifest,
            "report": reports[0],
            "event": session.trace()[0],
            "descriptor": describe(state, node, G),
            "production": next(iter(session._target._productions.values())),
            "staged edit": staged,
        }

    def test_no_record_accepts_an_assignment(self):
        for name, record in self.records().items():
            field = dataclasses.fields(record)[0].name

            with self.subTest(record=name):
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    setattr(record, field, None)


class PrepareDefaults(unittest.TestCase):

    def test_prepare_defaults_to_the_first_generation(self):
        session = HostedSession(small_runtime())
        session.prepare()

        produced = {
            e.compiler_generation for e in session.trace()
            if e.kind == "produce" and e.target_state_id is not None
        }

        self.assertEqual(produced, {1})

    def test_a_target_is_never_compiled_by_the_seed(self):
        session = HostedSession(small_runtime())

        with self.assertRaises(ValueError):
            session.prepare(compiler_generation=0)


class NodesTheCorpusLacks(unittest.TestCase):
    """Cases the corpus does not reach but admission and the compiler must
    still get right."""

    def test_an_invalid_node_lowers_like_the_host(self):
        entry = EntityID("hb_bogus")
        runtime = Runtime(load(program({
            entry: Function((), ("not_an_operation", ("lit", 1))),
        })))
        state = runtime.active.state
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
        node = body(state, entry)
        relation = relation_of(state.values[node])
        chunk, _ = session.produce(node)

        self.assertEqual(relation.kind, "invalid")
        self.assertEqual(chunk, bytecode.lower(relation))

        with self.assertRaises(LanguageError) as hosted:
            session.run(entry)

        with self.assertRaises(LanguageError) as reference:
            reference_run(
                Runtime(load(program({
                    entry: Function((), ("not_an_operation", ("lit", 1))),
                }))),
                entry,
            )

        self.assertEqual(str(hosted.exception), str(reference.exception))

    def test_both_branch_targets_must_be_children(self):
        entry = EntityID("hb_branchy")
        runtime = Runtime(load(program({
            entry: Function(
                ("n",),
                ("if", ("lt", ("arg", "n"), ("lit", 1)),
                 ("lit", 1), ("lit", 2)),
            ),
        })))
        state = runtime.active.state
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
        node = body(state, entry)
        chunk, _ = session.produce(node)
        branch = next(i for i in chunk if i[0] == "BRANCH")
        stranger = EntityID("hb_stranger")

        validate_chunk(state, node, entry, chunk)

        for position in (1, 2):
            forged = list(branch)
            forged[position] = stranger
            replaced = tuple(
                tuple(forged) if i == branch else i for i in chunk
            )

            with self.subTest(position=position):
                with self.assertRaises(AdmissionRejected):
                    validate_chunk(state, node, entry, replaced)

    def test_validation_refuses_entities_that_are_not_code(self):
        runtime = small_runtime()
        state = runtime.active.state
        chunk = (("LIT", 1), ("END",))

        for entity in (EntityID("hb_missing"), F, EntityID("hb_f.links")):
            with self.subTest(entity=entity.value):
                with self.assertRaises(AdmissionRejected):
                    validate_chunk(state, entity, F, chunk)


class MachineResolverHook(unittest.TestCase):

    def test_resolver_is_consulted_and_scoped_to_the_run(self):
        runtime = small_runtime()
        state = runtime.active.state
        seen = []

        def resolver(st, entity, owner):
            seen.append((entity, owner))
            return bytecode.lower(relation_of(st.values[entity]))

        self.assertEqual(machine.run(runtime, F, 1, resolver=resolver), 2)
        self.assertTrue(seen)
        self.assertIn((body(state, G), G), seen)

        seen.clear()
        self.assertEqual(machine.run(runtime, F, 1), 2)
        self.assertEqual(seen, [], "the resolver outlived its run")

    def test_resolver_is_reset_after_a_failed_run(self):
        runtime = small_runtime()

        def refusing(state, entity, owner):
            raise AdmissionRejected("no chunk")

        with self.assertRaises(AdmissionRejected):
            machine.run(runtime, F, 1, resolver=refusing)

        self.assertEqual(machine.run(runtime, F, 1), 2)

    def test_resolver_failure_is_not_catchable_by_the_program(self):
        handler = EntityID("hb_catcher")
        runtime = Runtime(load(program({
            handler: Function((), ("catch", ("call", "g", ("lit", 1)))),
            EntityID("hb_catcher.links"): links(handler, g=G),
            G: Function(("n",), ("add", ("arg", "n"), ("lit", 1))),
        })))

        def refusing(state, entity, owner):
            raise AdmissionRejected("no chunk")

        with self.assertRaises(AdmissionRejected):
            machine.run(runtime, handler, resolver=refusing)


class TraceRecordsFirstUseOnly(unittest.TestCase):

    def test_one_execute_event_per_artifact(self):
        session = HostedSession(small_runtime())
        session.prepare(compiler_generation=1)

        for _ in range(3):
            self.assertEqual(session.run(F, 1), 2)

        executed = [
            (e.entity, e.version, e.artifact_id)
            for e in session.trace()
            if e.kind == "execute" and e.route == "admitted-host"
        ]

        self.assertTrue(executed)
        self.assertEqual(len(executed), len(set(executed)))


class EvidenceNamesTheNode(unittest.TestCase):
    """A produced chunk is evidence for one node only, even when a sibling
    of the same function has the same chunk and is itself well formed."""

    def test_the_same_chunk_does_not_admit_a_different_node(self):
        runtime = Runtime(load(program({
            F: Function(("n",), ("add", ("arg", "n"), ("arg", "n"))),
        })))
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
        state = runtime.active.state
        args = [
            n for n in code_nodes(state)
            if relation_of(state.values[n]).kind == "arg"
        ]
        self.assertEqual(len(args), 2)
        chunk, evidence = session.produce(args[0])

        for other in args[1:]:
            self.assertEqual(session.produce(other)[0], chunk)

            # The integrity check would also refuse it later; the evidence
            # check must refuse it first, on the node.
            with self.assertRaisesRegex(AdmissionRejected, "wrong node"):
                session.admit(
                    other, state.values[other].version_id, chunk, evidence,
                )


class ResolverChecksTheState(unittest.TestCase):

    def setUp(self):
        self.runtime = small_runtime()
        self.session = HostedSession(self.runtime)
        self.session.prepare(compiler_generation=1)
        self.node = body(self.runtime.active.state, G)
        self.resolve = self.session._bound()._artifacts.resolver()

    def test_an_equal_state_is_the_same_state(self):
        twin = small_runtime().active.state

        self.assertIsNot(twin, self.runtime.active.state)
        self.assertEqual(twin.id, self.runtime.active.state.id)
        self.assertTrue(self.resolve(twin, self.node, G))

    def test_a_different_state_is_refused(self):
        other = define(self.runtime.active.state, {
            G: Function(("n",), ("add", ("arg", "n"), ("lit", 7))),
        }).destination

        self.assertNotEqual(other.id, self.runtime.active.state.id)

        with self.assertRaises(AdmissionRejected):
            self.resolve(other, self.node, G)


class HostedRunGrantsNoActivation(unittest.TestCase):

    def test_no_capability_unless_asked(self):
        session = HostedSession(small_runtime())
        session.prepare(compiler_generation=1)

        with mock.patch.object(machine, "run", return_value=2) as run:
            session.run(F, 1)
            session.run(F, 1, may_activate=True)

        self.assertEqual(
            [call.kwargs["may_activate"] for call in run.call_args_list],
            [False, True],
        )


class SeedLoweringIsGenerationZero(unittest.TestCase):

    def test_host_lowered_nodes_are_reported_as_generation_zero(self):
        session = HostedSession(small_runtime())
        session.prepare(compiler_generation=1)
        lowered = [e for e in session.trace() if e.kind == HOST_LOWER]

        self.assertTrue(lowered)
        self.assertEqual({e.generation for e in lowered}, {0})


class OperandTypesOfClosureAndCatch(unittest.TestCase):

    def setUp(self):
        self.runtime = Runtime(load(program({
            F: Function(
                ("n",),
                ("closure", ("x",), ("n",), ("add", ("arg", "n"), ("arg", "x"))),
            ),
            G: Function((), ("catch", ("lit", 1))),
        })))
        self.state = self.runtime.active.state
        self.session = HostedSession(self.runtime)
        self.session.prepare(compiler_generation=1)

    def instruction(self, function, opcode):
        node = body(self.state, function)
        chunk = self.session.produce(node)[0]

        return node, next(i for i in chunk if i[0] == opcode)

    def check(self, function, instruction):
        node = body(self.state, function)
        validate_chunk(self.state, node, function, (instruction, ("END",)))

    def accepts(self, function, instruction):
        self.check(function, instruction)

    def rejects(self, function, instruction):
        with self.assertRaises(AdmissionRejected):
            self.check(function, instruction)

    def test_closure_params_and_captures_are_tuples_of_names(self):
        _, closure = self.instruction(F, "CLOSURE")
        child = closure[1]

        self.accepts(F, closure)
        self.rejects(F, ("CLOSURE", child, "x", ("n",)))
        self.rejects(F, ("CLOSURE", child, (1,), ("n",)))
        self.rejects(F, ("CLOSURE", child, ("x",), "n"))
        self.rejects(F, ("CLOSURE", child, ("x",), (2,)))

    def test_catch_kinds_are_none_or_a_tuple_of_names(self):
        _, catch = self.instruction(G, "CATCH")
        child = catch[1]

        self.accepts(G, catch)
        self.accepts(G, ("CATCH", child, ("invalid",)))
        self.rejects(G, ("CATCH", child, "invalid"))
        self.rejects(G, ("CATCH", child, (1,)))
        self.rejects(G, ("CATCH", child, 7))


class CommandOutputBoundary(unittest.TestCase):
    """The documented command prints JSON: identities as their names,
    canonical tuples as arrays, plain values unchanged."""

    def test_identities_and_canonical_values_become_json(self):
        self.assertEqual(_jsonable(EntityID("e")), "e")
        self.assertEqual(_jsonable(canonicalize((1, EntityID("e")))), [1, "e"])
        self.assertEqual(_jsonable(5), 5)
        self.assertEqual(_jsonable([EntityID("e"), (2,)]), ["e", [2]])


class DescriptorValueDecoding(unittest.TestCase):

    def test_maps_decode_to_dicts_and_unknown_tags_stay_canonical(self):
        mapping = canonicalize({"a": 1, "b": (1, 2)})
        unknown = canonicalize(b"x")

        self.assertEqual(_plain(mapping), {"a": 1, "b": (1, 2)})
        self.assertEqual(_plain(unknown), unknown)


if __name__ == "__main__":
    unittest.main()
