"""Plan-owned task 31 acceptance tests: candidate admission, reuse and
artifact lifetime on the hosted route (docs/live_evolution.md sections 3
and 4, issue #67).

Every test here fails before task 31 is implemented, except
``test_the_oracle_catches_what_the_route_must_not``, which checks the host
oracle. The produced and reused node sets are computed here from the two
states of an activation, not taken from the implementation; leftover
artifacts are counted in the heap, not in the session's own records.
"""

from __future__ import annotations

import contextlib
import gc
import unittest
import weakref
from unittest import mock

from shear import Runtime, bytecode
from shear.hosted_bootstrap import AdmissionRejected, HostedSession
from shear.hosted_bootstrap import descriptors
from shear.relations import relation_of
from tests.live_support import (
    H,
    TOTAL,
    UPDATES,
    admitted_run,
    assert_no_orphans,
    code_nodes,
    host,
    image_state,
    loaded_states,
    no_host_lowering,
)


def fresh(generation=1):
    runtime = Runtime(image_state())
    session = HostedSession(runtime)
    session.prepare(compiler_generation=generation)
    return runtime, session


def recording(runtime):
    """Record the candidate states of the trials ``runtime`` runs."""

    trials = []
    original = runtime.trial

    def trial(*args, **kwargs):
        isolated = original(*args, **kwargs)
        trials.append(isolated.active.state)
        return isolated

    return trials, mock.patch.object(runtime, "trial", side_effect=trial)


def released(session, why):
    return {
        e.target_state_id
        for e in session.trace()
        if e.kind == "release" and e.detail == why
    }


class CandidateAdmission(unittest.TestCase):
    """Section 3: a candidate is admitted whole before it runs or switches,
    and a candidate that cannot be admitted changes nothing."""

    def assert_admitted_before_use(self, events, state):
        """Every code node of ``state`` is admitted before any of its
        artifacts first runs."""

        nodes = {
            (node, state.values[node].version_id)
            for node, _ in code_nodes(state)
        }
        positions = [
            i for i, e in enumerate(events)
            if e.target_state_id == state.id and e.kind == "execute"
        ]
        first = positions[0] if positions else len(events)
        before = {
            (e.entity, e.version)
            for e in events[:first]
            if e.target_state_id == state.id
            and e.kind in ("admit", "reuse")
        }

        self.assertEqual(before, nodes)

    def test_trial_and_activation_candidates_are_admitted_whole(self):
        # migrate activates without a trial and try_wrong trials without
        # activating, so the two candidate states are distinct.
        runtime, session = fresh()
        trials, patch = recording(runtime)
        start = runtime.active.state.id

        with patch:
            self.assertEqual(
                admitted_run(session, H("migrate"), 5, may_activate=True),
                (2, 7, "old tail"),
            )
            activated = runtime.active.state
            self.assertEqual(
                admitted_run(session, H("try_wrong"), may_activate=True),
                "wrong",
            )

        events = session.trace()

        self.assertEqual(len(trials), 1)
        self.assertNotEqual(activated.id, start)
        self.assertNotEqual(trials[0].id, activated.id)

        for state in (trials[0], activated):
            with self.subTest(state=state.id.value[:12]):
                self.assert_admitted_before_use(events, state)

    def test_trial_artifacts_are_released(self):
        # A rejected answer, and a candidate that fails inside its trial.
        for entry, answer in (
            ("try_wrong", "wrong"),
            ("try_crash", "out_of_range"),
        ):
            with self.subTest(entry=entry):
                runtime, session = fresh()
                trials, patch = recording(runtime)

                with patch:
                    self.assertEqual(
                        admitted_run(session, H(entry), may_activate=True),
                        answer,
                    )

                self.assertEqual(len(trials), 1)
                self.assertIn(trials[0].id, released(session, "trial"))
                assert_no_orphans(self, session)

                with self.assertRaises(AdmissionRejected):
                    session.admitted(trials[0].id)

    def unchanged_after(self, entry, failure):
        runtime, session = fresh()
        self.assertEqual(admitted_run(session, H("handle"), 1), 2)
        state = runtime.active.state
        versions = runtime.versions
        total = runtime.read(TOTAL)

        # The program's catch must not see the failure.
        with no_host_lowering(), failure(session):
            with self.assertRaises(AdmissionRejected):
                session.run(H(entry), 5, may_activate=True)

        # The failure came from compiling the candidate: the program's own
        # nodes, including its catch and activate or trial, all ran.
        executed = {
            e.entity for e in session.trace() if e.kind == "execute"
        }
        owned = {
            node for node, owner in code_nodes(state) if owner == H(entry)
        }

        self.assertTrue(owned)
        self.assertLessEqual(owned, executed)
        self.assertIs(runtime.active.state, state)
        self.assertEqual(runtime.versions, versions)
        self.assertEqual(runtime.read(TOTAL), total)
        assert_no_orphans(self, session)

    def invalidated(self, session):
        session.invalidate_compiler_generation(1)
        return contextlib.nullcontext()

    def partway(self, session):
        # plus(k)'s candidate keeps the old body, which reuses its
        # artifacts, and adds a new add node, which now cannot be compiled.
        return mock.patch.object(
            descriptors, "SUPPORTED_KINDS",
            descriptors.SUPPORTED_KINDS - {"add"},
        )

    def test_failed_activation_compilation_changes_nothing(self):
        self.unchanged_after("guarded", self.invalidated)

    def test_failed_trial_compilation_changes_nothing(self):
        self.unchanged_after("guarded_trial", self.invalidated)

    def test_a_failure_partway_through_a_candidate_leaves_nothing(self):
        for entry in ("guarded", "guarded_trial"):
            with self.subTest(entry=entry):
                self.unchanged_after(entry, self.partway)

    def test_the_oracle_catches_what_the_route_must_not(self):
        # On the host the same programs succeed: the difference above is the
        # host failure of D5.2, not a program failure.
        runtime = Runtime(image_state())

        self.assertEqual(
            host(runtime, H("guarded"), 5, may_activate=True),
            ("ok", None),
        )
        self.assertEqual(
            host(runtime, H("guarded_trial"), 5, may_activate=True)[0], "ok",
        )


class SameStateTrial(unittest.TestCase):
    """Section 4.2: a trial whose candidate is the active state itself has
    its own artifact set, and releasing it leaves the loaded version's."""

    def test_releasing_the_trial_keeps_the_active_set(self):
        runtime, session = fresh()
        trials, patch = recording(runtime)
        active = runtime.active.state
        before = dict(session.admitted(active.id))

        with patch:
            self.assertEqual(
                admitted_run(session, H("same_trial"), may_activate=True),
                ("ok", 2),
            )

        self.assertEqual(len(trials), 1)
        self.assertEqual(trials[0].id, active.id, "the witness must coincide")
        self.assertIn(active.id, released(session, "trial"))
        self.assertNotIn(active.id, released(session, "retired"))
        self.assertIs(runtime.active.state, active)
        self.assertEqual(dict(session.admitted(active.id)), before)
        assert_no_orphans(self, session)
        self.assertEqual(admitted_run(session, H("handle"), 1), 2)


class Reuse(unittest.TestCase):
    """Section 4.3: unchanged nodes reuse the active state's artifacts,
    everything else is compiled, and nothing is inferred from a version
    alone."""

    def activate_once(self, entry, *args):
        runtime, session = fresh()
        source = runtime.active.state
        before = dict(session.admitted(source.id))
        admitted_run(session, H(entry), *args, may_activate=True)
        destination = runtime.active.state

        self.assertNotEqual(destination.id, source.id)

        return session, source, before, destination

    def expected_split(self, source, destination):
        produced, reused = set(), set()

        for node, owner in code_nodes(destination):
            version = destination.values[node].version_id
            old = source.values.get(node)

            if (
                old is not None
                and old.version_id == version
                and source.owner_of(node) == owner
            ):
                reused.add((node, version))
            else:
                produced.add((node, version))

        return produced, reused

    def observed(self, session, state):
        produced, reused, sources = set(), set(), set()

        for e in session.trace():
            if e.target_state_id != state.id:
                continue

            if e.kind == "produce":
                produced.add((e.entity, e.version))
            elif e.kind == "reuse":
                reused.add((e.entity, e.version))
                sources.add(e.source_artifact_id)

        return produced, reused, sources

    def assert_split(self, session, source, before, destination):
        produced, reused, sources = self.observed(session, destination)

        self.assertEqual(
            (produced, reused), self.expected_split(source, destination),
        )
        # Every reuse, the trial's and the activation's, comes from the
        # active state's own artifacts, never from a trial's set.
        self.assertLessEqual(
            sources, {artifact.artifact_id for artifact in before.values()},
        )

        return produced, reused

    def test_an_update_compiles_only_what_changed(self):
        session, source, before, destination = self.activate_once(
            "upgrade", 10, 2, 13,
        )
        produced, reused = self.assert_split(
            session, source, before, destination,
        )

        self.assertTrue(produced)
        self.assertTrue(reused)

        after = session.admitted(destination.id)
        fresh_session = HostedSession(Runtime(destination))
        fresh_session.prepare(compiler_generation=1)
        compiled = fresh_session.admitted(destination.id)

        for key in sorted(reused, key=lambda k: k[0].value):
            with self.subTest(node=key[0].value):
                self.assertIs(after[key].chunk, before[key].chunk)
                self.assertEqual(after[key].chunk, compiled[key].chunk)
                self.assertEqual(
                    after[key].chunk,
                    bytecode.lower(relation_of(destination.values[key[0]])),
                )

    def test_an_activation_without_a_trial_reuses_from_the_active_state(self):
        session, source, before, destination = self.activate_once(
            "migrate", 5,
        )
        _, reused = self.assert_split(session, source, before, destination)

        self.assertTrue(reused)

    def test_moved_nodes_are_compiled_again(self):
        session, source, before, destination = self.activate_once("move")
        moved = {
            (node, destination.values[node].version_id)
            for node, owner in code_nodes(destination)
            if node in source.values
            and source.values[node].version_id
            == destination.values[node].version_id
            and source.owner_of(node) != owner
        }
        produced, reused = self.assert_split(
            session, source, before, destination,
        )

        self.assertTrue(moved, "the witness must move nodes")
        self.assertLessEqual(moved, produced)
        self.assertFalse(moved & reused)


class Lifetime(unittest.TestCase):
    """Section 4.1: a version owns its artifacts."""

    def test_repeated_updates_release_retired_versions(self):
        runtime, session = fresh()
        first = runtime.active.state.id
        artifact = next(iter(session.admitted(first).values()))
        witness = weakref.ref(artifact)
        del artifact
        seen = {first}

        for m in range(1, UPDATES + 1):
            with self.subTest(update=m):
                self.assertEqual(
                    admitted_run(
                        session, H("upgrade"), 1, 2, 2 + m, may_activate=True,
                    ),
                    "installed",
                )
                seen.add(runtime.active.state.id)
                self.assertEqual(len(runtime.versions), 1)
                assert_no_orphans(self, session)

        retired = released(session, "retired")

        self.assertEqual(len(seen), UPDATES + 1)
        self.assertEqual(retired, seen - {runtime.active.state.id})

        gc.collect()
        self.assertIsNone(
            witness(), "a retired version's artifact record is still alive",
        )

    def test_a_held_version_keeps_its_artifacts_until_released(self):
        runtime, session = fresh()
        original = runtime.activate
        during = []

        def activate(*args, **kwargs):
            version = original(*args, **kwargs)
            during.append((loaded_states(runtime), session.retained_states()))
            return version

        with mock.patch.object(runtime, "activate", side_effect=activate):
            self.assertEqual(
                admitted_run(session, H("migrate"), 5, may_activate=True),
                (2, 7, "old tail"),
            )

        self.assertEqual(len(during), 1)
        loaded, retained = during[0]
        self.assertEqual(len(loaded), 2)
        self.assertLessEqual(loaded, retained)
        self.assertEqual(len(runtime.versions), 1)
        assert_no_orphans(self, session)


if __name__ == "__main__":
    unittest.main()
