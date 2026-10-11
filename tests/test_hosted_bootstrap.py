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

import json
import tempfile
import unittest
from pathlib import Path

from shear import EntityID, Runtime, bytecode, machine
from shear.canonical import canonicalize
from shear.examples import EXAMPLES
from shear.examples._support import program
from shear.hosted_bootstrap import AdmissionRejected, HostedSession
from shear.hosted_bootstrap import seed
from shear.hosted_bootstrap.descriptors import (
    SUPPORTED_KINDS,
    decode_chunk,
    describe,
)
from shear.hosted_bootstrap.errors import UnsupportedOperation
from shear.hosted_bootstrap.validation import validate_chunk
from shear.lang import NODE_KINDS, Function, _definition_of, define, links, load
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


if __name__ == "__main__":
    unittest.main()
