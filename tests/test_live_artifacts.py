"""Plan-owned task 31 acceptance tests: candidate admission, reuse and
artifact lifetime on the hosted route (docs/live_evolution.md sections 3
and 4, issue #67).

Every test here fails before task 31 is implemented, except
``test_the_oracle_catches_what_the_route_must_not``, which checks the host
oracle. Artifact sets belong to versions (and to a running trial's version),
not to a ``StateID``: two loaded versions, or a trial and a loaded version,
can share one. The produced and reused node sets are computed here from the
two states of an activation, not taken from the implementation; leftover
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
    assert_observed,
    code_nodes,
    host,
    image_state,
    no_host_lowering,
    observation,
    retained_as_loaded,
)


def fresh(generation=1):
    runtime = Runtime(image_state())
    session = HostedSession(runtime)
    session.prepare(compiler_generation=generation)
    return runtime, session


def recording(runtime):
    """Record the versions of the trials ``runtime`` runs."""

    trials = []
    original = runtime.trial

    def trial(*args, **kwargs):
        isolated = original(*args, **kwargs)
        trials.append(isolated.active)
        return isolated

    return trials, mock.patch.object(runtime, "trial", side_effect=trial)


def released(session, why):
    return [
        e.target_state_id
        for e in session.trace()
        if e.kind == "release" and e.detail == why
    ]


def without_kind(kind):
    """The SHEAR compiler cannot lower ``kind`` for the duration."""

    return mock.patch.object(
        descriptors, "SUPPORTED_KINDS", descriptors.SUPPORTED_KINDS - {kind},
    )


def without_instruction(op):
    """Admission refuses every chunk with ``op`` for the duration: the
    failure can only be found after the compiler produced a chunk."""

    from shear.instructions import INSTRUCTIONS

    @contextlib.contextmanager
    def patched():
        with mock.patch.dict(INSTRUCTIONS):
            del INSTRUCTIONS[op]
            yield

    return patched()


class CandidateAdmission(unittest.TestCase):
    """Section 3: a candidate is admitted whole before it runs or switches,
    a candidate that cannot be admitted changes nothing, and a language
    rejection wins over a compilation failure."""

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
        self.assertNotEqual(trials[0].state.id, activated.id)

        for state in (trials[0].state, activated):
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
                records = []

                with patch:
                    self.assertEqual(
                        admitted_run(
                            session, H(entry),
                            may_activate=True, records=records,
                        ),
                        answer,
                    )

                self.assertEqual(len(trials), 1)
                trial = trials[0]

                # The trial ran on artifacts of a set its own version owned.
                self.assertTrue(
                    [r for r in records if r[0] is trial],
                    "no chunk of the trial was opened",
                )
                assert_observed(self, records)
                self.assertIn(trial.state.id, released(session, "trial"))

                with self.assertRaises(AdmissionRejected):
                    session.admitted(trial)

                # Drop the test's own references before counting the heap.
                del records, trial, trials
                assert_no_orphans(self, session)

    def unchanged_after(self, entry, failure):
        runtime, session = fresh()
        self.assertEqual(admitted_run(session, H("handle"), 1), 2)
        state = runtime.active.state
        versions = runtime.versions
        total = runtime.read(TOTAL)
        before = len(session.trace())

        # The program's catch must not see the failure.
        with no_host_lowering(), failure(session):
            with self.assertRaises(AdmissionRejected):
                session.run(H(entry), 5, may_activate=True)

        # The failure came from compiling the candidate: the program's own
        # nodes, including its catch and activate or trial, all ran.
        events = session.trace()
        executed = {e.entity for e in events if e.kind == "execute"}
        owned = {
            node for node, owner in code_nodes(state) if owner == H(entry)
        }

        self.assertTrue(owned)
        self.assertLessEqual(owned, executed)
        self.assertIs(runtime.active.state, state)
        self.assertEqual(runtime.versions, versions)
        self.assertEqual(runtime.read(TOTAL), total)
        assert_no_orphans(self, session)

        return [
            e for e in events[before:]
            if e.target_state_id not in (None, state.id)
        ]

    def invalidated(self, session):
        session.invalidate_compiler_generation(1)
        return contextlib.nullcontext()

    def test_failed_activation_compilation_changes_nothing(self):
        self.unchanged_after("guarded", self.invalidated)

    def test_failed_trial_compilation_changes_nothing(self):
        self.unchanged_after("guarded_trial", self.invalidated)

    def test_a_failure_partway_through_a_candidate_leaves_nothing(self):
        # grow(k)'s candidate keeps the old body, which reuses its artifacts,
        # and adds new nodes, among them the only len node of the program.
        # Without the LEN instruction its produced chunk is refused at
        # admission, so the compiler has already produced it when the
        # failure is found.
        for entry in ("guarded", "guarded_trial"):
            with self.subTest(entry=entry, failure="admission"):
                work = self.unchanged_after(
                    entry, lambda session: without_instruction("LEN"),
                )
                self.assertTrue(
                    [e for e in work if e.kind == "produce"],
                    "the candidate failed before the compiler produced "
                    "anything",
                )

            with self.subTest(entry=entry, failure="kind"):
                self.unchanged_after(
                    entry, lambda session: without_kind("len"),
                )

    def test_a_language_rejection_wins_over_a_compilation_failure(self):
        # bound_first's second activation breaks the two-version bound, and
        # its candidate (the only len node of the program) cannot be
        # compiled. The language's rejection is what the program sees.
        runtime, session = fresh()
        host_runtime = Runtime(image_state())

        self.assertEqual(
            host(host_runtime, H("bound_first"), may_activate=True),
            "activation_rejected",
        )

        with without_kind("len"):
            self.assertEqual(
                admitted_run(session, H("bound_first"), may_activate=True),
                "activation_rejected",
            )

        self.assertEqual(observation(runtime), observation(host_runtime))
        assert_no_orphans(self, session)

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


class SameState(unittest.TestCase):
    """Sections 4.1 and 4.2: a set belongs to a version or a trial, even when
    its state is the state of another owner."""

    def test_a_trial_of_the_active_state_has_its_own_set(self):
        runtime, session = fresh()
        trials, patch = recording(runtime)
        active = runtime.active
        before = dict(session.admitted(active))
        records = []

        with patch:
            self.assertEqual(
                admitted_run(
                    session, H("same_trial"),
                    may_activate=True, records=records,
                ),
                ("ok", 2),
            )

        self.assertEqual(len(trials), 1)
        trial = trials[0]
        self.assertEqual(trial.state.id, active.state.id, "must coincide")
        self.assertIsNot(trial, active)

        # The trial ran on records of its own set: each shares the active
        # set's chunk (every node is reused) but is a separate admission.
        mine = [r for r in records if r[0] is trial]
        self.assertTrue(mine, "no chunk of the trial was opened")
        assert_observed(self, records)

        for _, entity, chunk, artifact in mine:
            key = (entity, trial.state.values[entity].version_id)
            self.assertIsNot(artifact, before[key])
            self.assertIs(artifact.chunk, before[key].chunk)

        self.assertIn(active.state.id, released(session, "trial"))
        self.assertNotIn(active.state.id, released(session, "retired"))
        self.assertIs(runtime.active, active)
        self.assertEqual(dict(session.admitted(active)), before)

        with self.assertRaises(AdmissionRejected):
            session.admitted(trial)

        # Drop the test's own references before counting the heap.
        del records, mine, trial, trials, artifact, chunk
        assert_no_orphans(self, session)
        self.assertEqual(admitted_run(session, H("handle"), 1), 2)

    def test_two_loaded_versions_of_one_state_have_separate_sets(self):
        runtime, session = fresh()
        old = runtime.active
        original = runtime.activate
        during = []

        def activate(*args, **kwargs):
            version = original(*args, **kwargs)
            during.append((
                runtime.versions,
                session.retained_versions(),
                dict(session.admitted(old)),
                dict(session.admitted(version)),
            ))
            return version

        with mock.patch.object(runtime, "activate", side_effect=activate):
            self.assertEqual(
                admitted_run(session, H("same_activate"), may_activate=True),
                2,
            )

        self.assertEqual(len(during), 1)
        loaded, retained, old_set, new_set = during[0]
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].state.id, loaded[1].state.id)
        self.assertEqual(frozenset(loaded), retained)
        self.assertEqual(old_set.keys(), new_set.keys())

        for key, artifact in new_set.items():
            self.assertIsNot(artifact, old_set[key])
            self.assertIs(artifact.chunk, old_set[key].chunk)

        self.assertIsNot(runtime.active, old)
        self.assertEqual(len(runtime.versions), 1)
        self.assertEqual(
            released(session, "retired"), [runtime.active.state.id],
        )

        # Drop the test's own references before counting the heap.
        del old_set, new_set, during, loaded, retained, old, artifact
        assert_no_orphans(self, session)


class Reuse(unittest.TestCase):
    """Section 4.3: unchanged nodes reuse the active version's artifacts,
    everything else is compiled, and nothing is inferred from a version
    alone."""

    def activate_once(self, entry, *args):
        runtime, session = fresh()
        source = runtime.active.state
        before = dict(session.admitted(runtime.active))
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
        # active version's own artifacts, never from a trial's set.
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

        after = session.admitted(session.target_runtime.active)
        compiled_runtime = Runtime(destination)
        compiled_session = HostedSession(compiled_runtime)
        compiled_session.prepare(compiler_generation=1)
        compiled = compiled_session.admitted(compiled_runtime.active)

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
        artifact = next(iter(session.admitted(runtime.active).values()))
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
        self.assertEqual(len(retired), UPDATES)
        self.assertEqual(set(retired), seen - {runtime.active.state.id})

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
            during.append((runtime.versions, session.retained_versions()))
            return version

        with mock.patch.object(runtime, "activate", side_effect=activate):
            self.assertEqual(
                admitted_run(session, H("migrate"), 5, may_activate=True),
                (2, 7, "old tail"),
            )

        self.assertEqual(len(during), 1)
        loaded, retained = during[0]
        self.assertEqual(len(loaded), 2)
        self.assertLessEqual(frozenset(loaded), retained)
        self.assertEqual(len(runtime.versions), 1)
        retained_as_loaded(self, session)

        # Drop the test's own references before counting the heap.
        del during, loaded, retained
        assert_no_orphans(self, session)


if __name__ == "__main__":
    unittest.main()
