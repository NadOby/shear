"""Plan-owned task 31 acceptance tests: the corpus and the live image
(docs/live_evolution.md sections 2 and 3, issue #67).

Every test here fails before task 31 is implemented, except
``test_every_corpus_example_is_claimed``, a check of the declared sets. Do
not skip missing behaviour, and do not fall back to host lowering or
``lang.run``. The program, the step tables and the oracles are in
``tests/live_support.py``; ``tests/test_live_artifacts.py`` covers artifact
admission, reuse and lifetime, ``tests/test_instruction_table.py`` the
shared instruction table.
"""

from __future__ import annotations

import unittest

from shear import Runtime, bytecode
from shear.examples import EXAMPLES, play
from shear.hosted_bootstrap import HostedSession
from shear.relations import relation_of
from tests.live_support import (
    BOUND,
    CLOSURES,
    LIVE,
    MAIN,
    MALFORMED,
    MIGRATE,
    MOVE,
    SAME,
    TWICE,
    HostedRunner,
    admitted_run,
    assert_observed,
    assert_provenance,
    code_nodes,
    drive,
    host,
    image_state,
    malformed_state,
    outcome,
    retained_as_loaded,
)
from tests.test_hosted_corpus import DEFERRED, INCLUDED


class LiveCorpus(unittest.TestCase):
    """Section 2.1: the corpus examples task 30 deferred."""

    def test_every_corpus_example_is_claimed(self):
        names = {example.name for example in EXAMPLES}

        self.assertEqual(LIVE, DEFERRED)
        self.assertEqual(INCLUDED | LIVE, names)

    def test_deferred_examples_run_on_the_admitted_route(self):
        for example in EXAMPLES:
            if example.name not in LIVE:
                continue

            with self.subTest(example=example.name):
                runner = HostedRunner()
                play(example, runner)

                self.assertTrue(runner.sessions)
                assert_observed(self, runner.records)

                for session in runner.sessions.values():
                    assert_provenance(self, session.trace())
                    retained_as_loaded(self, session)


class LiveImage(unittest.TestCase):
    """Section 2.2: a persistent image changing itself."""

    def test_image_evolves_on_the_self_rebuilt_compiler(self):
        sessions = []
        drive(self, MAIN, generation=3, session_out=sessions)
        events = sessions[0].trace()
        initial = image_state().id
        candidate = [
            e for e in events
            if e.kind == "produce"
            and e.target_state_id is not None
            and e.target_state_id != initial
        ]

        self.assertTrue(candidate, "no candidate was compiled")
        self.assertEqual(
            {e.compiler_generation for e in candidate}, {3},
        )

    def test_old_frame_continues_in_its_version(self):
        drive(self, MIGRATE)

    def test_two_version_bound(self):
        drive(self, TWICE)

    def test_closures_across_activation(self):
        for steps in CLOSURES:
            with self.subTest(entry=steps[0][0]):
                drive(self, steps)

    def test_moved_nodes(self):
        drive(self, MOVE)

    def test_activation_of_the_active_state_itself(self):
        drive(self, SAME)

    def test_a_bound_rejection_inside_a_run(self):
        drive(self, BOUND)


class MalformedActivation(unittest.TestCase):
    """Section 2.3: activation and trial forms that carry a problem are
    compiled as host lowering compiles them and fail as on the host."""

    def test_problem_forms_compile_as_host_lowering_does(self):
        state = malformed_state()
        runtime = Runtime(state)
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
        admitted = session.admitted(runtime.active)
        kinds = set()

        for node, owner in code_nodes(state):
            relation = relation_of(state.values[node])
            kinds.add(relation.kind)

            with self.subTest(node=node.value):
                key = (node, state.values[node].version_id)
                self.assertEqual(admitted[key].chunk, bytecode.lower(relation))

        self.assertLessEqual({"activate", "trial"}, kinds)

    def test_problem_forms_fail_as_on_the_host(self):
        state = malformed_state()
        host_runtime = Runtime(state)
        runtime = Runtime(state)
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
        records = []

        for entry in MALFORMED:
            with self.subTest(entry=entry.value):
                expected = outcome(
                    lambda: host(host_runtime, entry, may_activate=True)
                )
                actual = outcome(
                    lambda: admitted_run(
                        session, entry, may_activate=True, records=records,
                    )
                )

                self.assertEqual(expected[0], "ok")
                self.assertEqual(actual, expected)
                self.assertEqual(
                    runtime.active.state.id, host_runtime.active.state.id,
                )

        assert_observed(self, records)


if __name__ == "__main__":
    unittest.main()
