"""Plan-owned Task 30 hosted-corpus acceptance tests.

See docs/hosted_pipeline.md and issue #66.

These tests deliberately fail before the hosted pipeline exists.
Do not skip missing implementation or fall back to lang.run.

HostedSession is the provisional public test boundary:
    HostedSession(runtime)
    prepare(compiler_generation=1)
    run(entry, *args, may_activate=False)
    trace() -> immutable sequence of provenance events

Each event exposes kind, route, entity, version and artifact_id.
Production events additionally identify the compiler generation.

The tests use the existing corpus expectations as independent
behavioral oracles.
"""

from __future__ import annotations

import unittest
from unittest import mock
from weakref import WeakKeyDictionary

from shear import CellContentRejected, Runtime, bytecode
from shear.examples import EXAMPLES, play
from shear.hosted_bootstrap import AdmissionRejected, HostedSession
from shear.lang import LanguageError, load


INCLUDED = frozenset({
    "factorial",
    "fibonacci",
    "sum_to_n",
    "gcd",
    "collatz_step_count",
    "deep_loop",
    "deep_recursion",
    "abs_value",
    "max_of_two",
    "clamp",
    "counter",
    "account",
    "insertion_sort",
    "let_bindings",
    "map",
    "fold",
    "map_long_tuple",
    "make_adder",
    "compose",
    "compiler",
})

DEFERRED = frozenset({
    "power_compiler",
    "checked_compile",
    "replace_self",
    "sort_swap",
    "instrument",
    "bootstrap",
    "safe_install",
    "account_report",
    "lookup",
})


def forbid_host_lowering(*args, **kwargs):
    raise AssertionError(
        "Ordinary host lowering reached during admitted execution"
    )


def event_key(event):
    return (
        event.entity,
        event.version,
        event.artifact_id,
    )


def assert_provenance(test, events):
    """Executed artifacts must have observed production and admission."""

    produced = {
        event_key(e)
        for e in events
        if e.kind == "produce" and e.route == "shear-compiler"
    }
    admitted = {
        event_key(e)
        for e in events
        if e.kind == "admit" and e.route == "host-admission"
    }
    executed = [
        e for e in events
        if e.kind == "execute" and e.route == "admitted-host"
    ]

    test.assertTrue(executed, "No admitted execution observed")

    for event in executed:
        with test.subTest(
            entity=event.entity,
            version=event.version,
            artifact=event.artifact_id,
        ):
            key = event_key(event)
            test.assertIn(key, produced)
            test.assertIn(key, admitted)
            test.assertIsNotNone(event.entity)
            test.assertIsNotNone(event.version)
            test.assertTrue(event.artifact_id)


class HostedCorpusTests(unittest.TestCase):

    def test_exact_declared_subset_exists(self):
        names = {example.name for example in EXAMPLES}

        self.assertEqual(len(INCLUDED), 20)
        self.assertTrue(INCLUDED <= names)
        self.assertTrue(DEFERRED <= names)
        self.assertFalse(INCLUDED & DEFERRED)

    def test_admission_failure_is_not_a_program_failure(self):
        """An admission failure must not satisfy an expected error step."""

        self.assertTrue(issubclass(AdmissionRejected, Exception))
        self.assertFalse(issubclass(AdmissionRejected, LanguageError))
        self.assertFalse(issubclass(AdmissionRejected, CellContentRejected))

    def test_complete_scenarios_on_admitted_route(self):
        """All original steps, including failures and cell checks."""

        selected = {
            example.name: example
            for example in EXAMPLES
            if example.name in INCLUDED
        }

        self.assertEqual(set(selected), INCLUDED)

        for name in sorted(INCLUDED):
            with self.subTest(example=name):
                example = selected[name]
                sessions = WeakKeyDictionary()

                def admitted_run(
                    runtime,
                    entry,
                    *args,
                    may_activate=False,
                ):
                    session = sessions.get(runtime)

                    if session is None:
                        session = HostedSession(runtime)
                        session.prepare(compiler_generation=1)
                        sessions[runtime] = session

                    # Preparation is complete. No ordinary host
                    # lowering may rescue missing execution artifacts.
                    # An admission failure must remain outside SHEAR's
                    # normal error semantics, even for Raises steps.
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
                        try:
                            return session.run(
                                entry,
                                *args,
                                may_activate=may_activate,
                            )
                        except AdmissionRejected as exc:
                            raise AssertionError(
                                "Hosted admission failure is not an "
                                "expected SHEAR program error"
                            ) from exc

                play(example, admitted_run)

                self.assertTrue(sessions)

                for session in sessions.values():
                    assert_provenance(self, session.trace())

    def test_corpus_execution_preserves_semantic_source(self):
        """Artifact preparation and execution cannot rewrite source."""

        example = next(
            e for e in EXAMPLES if e.name == "make_adder"
        )

        runtime = Runtime(load(example.program), example.context)
        before = runtime.active.state
        before_versions = {
            entity: value.version_id
            for entity, value in before.values.items()
        }

        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)

        for scenario in example.scenarios:
            for step in scenario:
                self.assertEqual(
                    session.run(step.entry, *step.args),
                    step.expect,
                )

        after = runtime.active.state

        self.assertEqual(after.id, before.id)
        self.assertEqual(
            {
                entity: value.version_id
                for entity, value in after.values.items()
            },
            before_versions,
        )
        assert_provenance(self, session.trace())


if __name__ == "__main__":
    unittest.main()
