"""Plan-owned Task 30 invalidation and failure-semantics acceptance.

These tests exercise host-initiated state changes, not language-driven
live evolution. Cross-activation artifact reuse is deliberately not
required: conservative invalidation is sufficient.

See docs/hosted_pipeline.md and issue #66.
"""

from __future__ import annotations

import unittest
from unittest import mock

from shear import (
    CellDeclaration,
    EntityID,
    IntRange,
    Runtime,
    bytecode,
    relation_of,
)
from shear.examples import self_hosting
from shear.examples._support import program
from shear.hosted_bootstrap import AdmissionRejected, HostedSession
from shear.lang import Function, LanguageError, define, links, load
from shear.lang import run as reference_run


CALLER = EntityID("safety_caller")
CALLEE = EntityID("safety_callee")
ALTERNATE = EntityID("safety_alternate")
HANDLER = EntityID("safety_handler")
RAISER = EntityID("safety_raiser")
BALANCE = EntityID("safety_balance")
LOG = EntityID("safety_log")


def callable_runtime():
    return Runtime(load(program({
        **self_hosting.compiler_entities(),
        CALLER: Function(
            ("n",),
            ("call", "child", ("arg", "n")),
        ),
        EntityID("safety_caller.links"): links(
            CALLER,
            child=CALLEE,
        ),
        CALLEE: Function(
            ("n",),
            ("add", ("arg", "n"), ("lit", 1)),
        ),
        ALTERNATE: Function(
            ("n",),
            ("add", ("arg", "n"), ("lit", 10)),
        ),
    })))


def body_node(state, function):
    definition = relation_of(state.values[function])
    return definition.roles["body"]


def matching_node(state, function, kind, **roles):
    matches = []

    for entity in state.owned_subtree(function):
        if entity == function:
            continue

        relation = relation_of(state.values[entity])

        if relation is None or relation.kind != kind:
            continue

        if all(
            relation.roles.get(role) == value
            for role, value in roles.items()
        ):
            matches.append(entity)

    assert len(matches) == 1, (function, kind, matches)
    return matches[0]


def forbid_host_lowering(*args, **kwargs):
    raise AssertionError(
        "Admitted execution fell back to ordinary host lowering"
    )


class InvalidationTests(unittest.TestCase):

    def test_changed_callee_invalidates_unchanged_caller(self):
        runtime = callable_runtime()
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)

        self.assertEqual(session.run(CALLER, 4), 5)

        old_state = runtime.active.state
        old_body = body_node(old_state, CALLER)
        old_version = old_state.values[old_body].version_id

        result = define(old_state, {
            CALLEE: Function(
                ("n",),
                ("add", ("arg", "n"), ("lit", 5)),
            ),
        })
        runtime.activate(result)

        new_state = runtime.active.state
        new_body = body_node(new_state, CALLER)

        self.assertEqual(new_body, old_body)
        self.assertEqual(
            new_state.values[new_body].version_id,
            old_version,
            "The witness must retain the caller's node version",
        )

        # The caller node did not change. Its linked callee did.
        # Its earlier execution artifact must not be reused.
        with (
            mock.patch.object(
                bytecode,
                "chunk_of",
                side_effect=forbid_host_lowering,
            ),
            mock.patch.object(
                bytecode,
                "lower_value",
                side_effect=forbid_host_lowering,
            ),
        ):
            with self.assertRaises(AdmissionRejected):
                session.run(CALLER, 4)

        session.prepare(compiler_generation=1)
        self.assertEqual(session.run(CALLER, 4), 9)

    def test_rebound_link_rejects_previous_artifacts(self):
        runtime = callable_runtime()
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)

        self.assertEqual(session.run(CALLER, 3), 4)

        before = runtime.active.state
        original_call = body_node(before, CALLER)

        self.assertEqual(
            relation_of(before.values[original_call]).roles["target"],
            CALLEE,
        )

        # A links-only edit does not retarget already-resolved call nodes.
        # Redefine the caller and its link table together so that define
        # constructs a genuinely changed executable call dependency.
        result = define(before, {
            CALLER: Function(
                ("n",),
                ("call", "child", ("arg", "n")),
            ),
            EntityID("safety_caller.links"): links(
                CALLER,
                child=ALTERNATE,
            ),
        })

        candidate = result.destination
        rebound_call = body_node(candidate, CALLER)

        self.assertEqual(
            relation_of(candidate.values[rebound_call]).roles["target"],
            ALTERNATE,
        )
        self.assertNotEqual(candidate.id, before.id)

        # Independent behavioral oracle. This expectation comes from
        # existing SHEAR semantics, not hosted-route reported results.
        oracle = Runtime(candidate)
        self.assertEqual(reference_run(oracle, CALLER, 3), 13)

        runtime.activate(result)

        self.assertEqual(runtime.active.state.id, candidate.id)

        # Previous artifacts cannot authorize the changed call dependency.
        with self.assertRaises(AdmissionRejected):
            session.run(CALLER, 3)

        session.prepare(compiler_generation=1)
        self.assertEqual(session.run(CALLER, 3), 13)

    def test_host_chunk_cache_cannot_override_admission(self):
        runtime = callable_runtime()
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)

        state = runtime.active.state
        node = body_node(state, CALLEE)

        # Pre-existing ordinary host chunk caches are untrusted.
        state.values[node].__dict__["_chunk"] = (
            ("LIT", 999),
            ("END",),
        )

        with (
            mock.patch.object(
                bytecode,
                "chunk_of",
                side_effect=forbid_host_lowering,
            ),
            mock.patch.object(
                bytecode,
                "lower_value",
                side_effect=forbid_host_lowering,
            ),
        ):
            self.assertEqual(session.run(CALLER, 4), 5)

        executions = [
            event for event in session.trace()
            if event.kind == "execute"
        ]

        self.assertTrue(executions)
        self.assertTrue(all(
            event.route == "admitted-host"
            for event in executions
        ))


class FailureSemanticsTests(unittest.TestCase):

    def test_caught_failed_write_keeps_previous_write(self):
        runtime = Runtime(load(program({
            **self_hosting.compiler_entities(),
            BALANCE: CellDeclaration(IntRange(0, None), 10),
            LOG: CellDeclaration(IntRange(0, None), 0),
            HANDLER: Function(
                (),
                (
                    "catch",
                    (
                        "seq",
                        ("write", "log", ("lit", 1)),
                        ("write", "balance", ("lit", -1)),
                    ),
                ),
            ),
            EntityID("safety_handler.links"): links(
                HANDLER,
                balance=BALANCE,
                log=LOG,
            ),
        })))

        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)

        failed_write = matching_node(
            runtime.active.state,
            HANDLER,
            "write",
            cell=BALANCE,
        )

        expected = (
            "failed",
            (
                "runtime",
                "cell_rejected",
                (
                    ("cell", BALANCE),
                    ("constraint", "violated"),
                    ("operation", "write"),
                ),
                (HANDLER, failed_write),
            ),
        )

        self.assertEqual(session.run(HANDLER), expected)
        self.assertEqual(runtime.read(LOG), 1)
        self.assertEqual(runtime.read(BALANCE), 10)

    def test_unmatched_filter_preserves_callee_provenance(self):
        runtime = Runtime(load(program({
            **self_hosting.compiler_entities(),
            RAISER: Function(
                (),
                ("raise", ("lit", "missing"), ("lit", 7)),
            ),
            HANDLER: Function(
                (),
                (
                    "catch",
                    ("call", "raiser"),
                    ("wrong_kind",),
                ),
            ),
            EntityID("safety_handler.links"): links(
                HANDLER,
                raiser=RAISER,
            ),
        })))

        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)

        raise_node = matching_node(
            runtime.active.state,
            RAISER,
            "raise",
        )

        with self.assertRaises(LanguageError) as caught:
            session.run(HANDLER)

        self.assertEqual(
            caught.exception.error,
            (
                "program",
                "missing",
                7,
                (RAISER, raise_node),
            ),
        )

        # The failed execution must not authorize a host fallback.
        events = session.trace()
        executed = [
            e for e in events if e.kind == "execute"
        ]

        self.assertTrue(executed)
        self.assertTrue(all(
            e.route == "admitted-host"
            for e in executed
        ))


if __name__ == "__main__":
    unittest.main()
