"""Plan-owned task 31 acceptance tests (docs/live_evolution.md, issue #67).

These tests fail before task 31 is implemented. Do not skip missing
behaviour, and do not fall back to host lowering or ``lang.run``.

Oracles, all independent of the SHEAR compiler under test:

* the corpus expectations and the hand-written expectations below;
* ordinary host execution (``lang.run``) of the same steps, compared step by
  step: results, failures, cell content, active ``StateID`` and loaded
  versions;
* ``bytecode.lower``, the independent host lowering, used only to compare;
* the two states of an activation, from which the produced and reused node
  sets are computed here, not taken from the implementation.

``HostedSession`` is the boundary; the names it gains for task 31
(``retained_states``, ``admitted``, the ``reuse`` and ``release`` events and
``TraceEvent.source_artifact_id``) are listed in live_evolution.md section 6.
"""

from __future__ import annotations

import contextlib
import gc
import unittest
import weakref
from unittest import mock
from weakref import WeakKeyDictionary

from shear import EntityID, Runtime, bytecode, machine, operations
from shear.canonical import canonical_serialize, canonicalize
from shear.examples import EXAMPLES, play
from shear.examples import vm
from shear.hosted_bootstrap import AdmissionRejected, HostedSession
from shear.hosted_bootstrap import validation
from shear.lang import _definition_of, load, run as host_run
from shear.relations import relation_of
from shear.syntax import parse
from tests.test_bootstrap_boundary import VM_MISSING_INSTRUCTIONS, _node_for
from tests.test_hosted_corpus import DEFERRED, INCLUDED
from tests.test_operations import dispatched

LIVE = frozenset({
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

# Instructions the host machine dispatches but lowering never emits.
INTERNAL = frozenset({"CATCH_OK", "RETURN"})

H = EntityID
TOTAL = H("total")

IMAGE = '''
cell total: int in 0.. = 0

fn handle(x):
    total = total + x
    x + 1

fn plus(k):
    let old = code(handle)
    function(item(old, 0), quote(unquote(item(old, 1)) + literal(k)))

fn verdict(r, expected):
    if item(r, 0) == "ok":
        "passed" if item(r, 1) == expected else "wrong"
    else:
        item(item(r, 1), 1)

fn install(f, x, expected):
    let v = verdict(catch(trial(handle(x), handle = f)), expected)
    if v == "passed":
        activate(handle = f)
        "installed"
    else:
        v

fn upgrade(k, x, expected):
    install(plus(k), x, expected)

fn try_crash():
    install(fn(x): item((), x), 1, 0)

fn try_raise():
    install(fn(x): raise("bad_input", x), 1, 0)

fn try_wrong():
    install(fn(x): x + x, 3, 99)

fn migrate(k):
    let before = handle(1)
    activate(handle = plus(k), migrate = fn(k): "migrated")
    (before, handle(1), "old tail")

fn twice(k):
    activate(handle = plus(k))
    let r = catch(activate(handle = plus(k + 1)))
    item(item(r, 1), 1)

fn scaler(n):
    closure(x) captures(n): label(calc, handle(x) * n)

fn keep(k):
    let c = scaler(3)
    activate(handle = plus(k))
    c(2)

fn rescale():
    let c = scaler(3)
    activate(scaler.calc = quote(handle(x) * (n + 100)))
    c(2)

fn drop_scaler():
    let c = scaler(3)
    activate(scaler = fn(n): n)
    let r = catch(c(2))
    item(item(r, 1), 1)

fn guarded(k):
    catch(activate(handle = plus(k)))

fn guarded_trial(k):
    catch(trial(handle(1), handle = plus(k)))

fn whole(x):
    x * 2 + 1

fn part(x):
    0

fn move():
    activate(part = fn(x): x * 2, whole = fn(x): part(x) + 1)
'''

UPDATES = 8

# (entry, args, may_activate, expected result, expected total)
MAIN = (
    ("handle", (1,), False, 2, 1),
    ("upgrade", (10, 2, 13), False, "no_capability", 1),
    ("upgrade", (10, 2, 13), True, "installed", 1),
    ("handle", (1,), False, 12, 2),
    ("try_crash", (), True, "out_of_range", 2),
    ("try_raise", (), True, "bad_input", 2),
    ("try_wrong", (), True, "wrong", 2),
    ("handle", (1,), False, 12, 3),
    *(
        step
        for m in range(1, UPDATES + 1)
        for step in (
            ("upgrade", (1, 2, 13 + m), True, "installed", 3 + 2 * (m - 1)),
            ("handle", (2,), False, 13 + m, 3 + 2 * m),
        )
    ),
)

MIGRATE = (
    ("migrate", (5,), True, (2, 7, "old tail"), 2),
    ("handle", (1,), False, 7, 3),
    ("migrate", (5,), True, "migrated", 3),
)

TWICE = (
    ("twice", (5,), True, "activation_rejected", 0),
    ("handle", (1,), False, 7, 1),
)

CLOSURES = (
    (("keep", (5,), True, 24, 2),),
    (("rescale", (), True, 309, 2),),
    (("drop_scaler", (), True, "absent", 0),),
)

MOVE = (
    ("move", (), True, None, 0),
    ("whole", (5,), False, 11, 0),
)


def image_state():
    return load(parse(IMAGE))


def forbid_host_lowering(*args, **kwargs):
    raise AssertionError("host lowering reached during an admitted run")


@contextlib.contextmanager
def no_host_lowering():
    with (
        mock.patch.object(
            bytecode, "chunk_of", side_effect=forbid_host_lowering,
        ),
        mock.patch.object(
            bytecode, "lower_value", side_effect=forbid_host_lowering,
        ),
    ):
        yield


def admitted_run(session, entry, *args, may_activate=False):
    """``session.run`` with host lowering forbidden. An admission failure is
    a test failure, never an expected program failure."""

    with no_host_lowering():
        try:
            return session.run(entry, *args, may_activate=may_activate)
        except AdmissionRejected as exc:
            raise AssertionError(
                "a hosted admission failure is not a SHEAR program error"
            ) from exc


def same(left, right):
    return canonical_serialize(canonicalize(left)) == canonical_serialize(
        canonicalize(right)
    )


def code_nodes(state):
    """``(node, owner)`` for every code node of every function."""

    for owner, value in state.values.items():
        if _definition_of(value) is None:
            continue

        for node in state.owned_subtree(owner) - {owner}:
            yield node, owner


def loaded_states(runtime):
    return frozenset(version.id for version in runtime.versions)


def authentic(events):
    """A function telling whether an artifact id has an authentic chain:
    produced and admitted, or reused from an authentic artifact."""

    produced = {
        (e.entity, e.version, e.artifact_id)
        for e in events
        if e.kind == "produce" and e.route == "shear-compiler"
    }
    admitted = {
        (e.entity, e.version, e.artifact_id)
        for e in events
        if e.kind == "admit" and e.route == "host-admission"
    }
    reused = {
        e.artifact_id: e
        for e in events
        if e.kind == "reuse" and e.route == "host-admission"
    }

    def check(entity, version, artifact_id, depth=0):
        key = (entity, version, artifact_id)

        if key in produced and key in admitted:
            return True

        event = reused.get(artifact_id)

        return (
            event is not None
            and depth < len(events)
            and event.entity == entity
            and event.version == version
            and check(entity, version, event.source_artifact_id, depth + 1)
        )

    return check


def admitted_for(events):
    """Artifact id to the state it was admitted for."""

    return {
        e.artifact_id: e.target_state_id
        for e in events
        if e.kind in ("admit", "reuse") and e.route == "host-admission"
    }


def assert_provenance(test, events):
    check = authentic(events)
    states = admitted_for(events)
    executed = [
        e for e in events
        if e.kind == "execute" and e.route == "admitted-host"
    ]

    test.assertTrue(executed, "no admitted execution observed")

    for event in executed:
        with test.subTest(entity=event.entity, artifact=event.artifact_id):
            test.assertTrue(
                check(event.entity, event.version, event.artifact_id),
                "executed artifact without an authentic chain",
            )
            test.assertEqual(
                states.get(event.artifact_id), event.target_state_id,
            )


class HostedRunner:
    """A ``play``-compatible runner: one session per runtime."""

    def __init__(self, generation=1):
        self.generation = generation
        self.sessions = WeakKeyDictionary()

    def __call__(self, runtime, entry, *args, may_activate=False):
        session = self.sessions.get(runtime)

        if session is None:
            session = HostedSession(runtime)
            session.prepare(compiler_generation=self.generation)
            self.sessions[runtime] = session

        return admitted_run(session, entry, *args, may_activate=may_activate)


def host(runtime, entry, *args, may_activate=False):
    return host_run(runtime, entry, *args, may_activate=may_activate)


def outcome(call):
    try:
        return ("ok", canonical_serialize(canonicalize(call())))
    except AssertionError:
        raise
    except Exception as exc:
        return ("raised", type(exc).__name__)


def drive(test, steps, generation=1, session_out=None):
    """Run ``steps`` on a fresh image on the host and on the admitted route.

    Checks each step's hand-written expectation on the host, that the hosted
    observation equals the host's, and that the retained artifact states are
    the loaded versions at every step boundary. Returns the session.
    """

    host_runtime = Runtime(image_state())
    runtime = Runtime(image_state())
    session = HostedSession(runtime)
    session.prepare(compiler_generation=generation)

    if session_out is not None:
        session_out.append(session)

    for index, (entry, args, may, expect, total) in enumerate(steps):
        with test.subTest(step=index, entry=entry):
            expected = outcome(
                lambda: host(host_runtime, H(entry), *args, may_activate=may)
            )
            test.assertEqual(
                expected,
                ("ok", canonical_serialize(canonicalize(expect))),
                "the host oracle disagrees with the written expectation",
            )
            test.assertEqual(host_runtime.read(TOTAL), total)

            actual = outcome(
                lambda: admitted_run(
                    session, H(entry), *args, may_activate=may,
                )
            )
            test.assertEqual(actual, expected)
            test.assertEqual(runtime.read(TOTAL), total)
            test.assertEqual(
                runtime.active.state.id, host_runtime.active.state.id,
            )
            test.assertEqual(
                len(runtime.versions), len(host_runtime.versions),
            )
            test.assertEqual(session.retained_states(), loaded_states(runtime))

    assert_provenance(test, session.trace())
    return session


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

                for session in runner.sessions.values():
                    assert_provenance(self, session.trace())
                    self.assertEqual(
                        session.retained_states(),
                        loaded_states(session.target_runtime),
                    )


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


class CandidateAdmission(unittest.TestCase):
    """Section 3: a candidate is admitted whole before it runs or switches,
    and a candidate that cannot be admitted changes nothing."""

    def recording(self, runtime):
        """Record the states of the trials ``runtime`` runs."""

        trials = []
        original = runtime.trial

        def trial(*args, **kwargs):
            isolated = original(*args, **kwargs)
            trials.append(isolated.active.state)
            return isolated

        return trials, mock.patch.object(runtime, "trial", side_effect=trial)

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
        runtime = Runtime(image_state())
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
        trials, patch = self.recording(runtime)

        with patch:
            self.assertEqual(
                admitted_run(
                    session, H("upgrade"), 10, 2, 13, may_activate=True,
                ),
                "installed",
            )
            self.assertEqual(
                admitted_run(session, H("try_wrong"), may_activate=True),
                "wrong",
            )

        events = session.trace()

        self.assertEqual(len(trials), 2)

        for state in (*trials, runtime.active.state):
            with self.subTest(state=state.id.value[:12]):
                self.assert_admitted_before_use(events, state)

    def test_trial_artifacts_are_released(self):
        runtime = Runtime(image_state())
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
        trials, patch = self.recording(runtime)

        with patch:
            admitted_run(session, H("try_wrong"), may_activate=True)

        released = {
            e.target_state_id for e in session.trace() if e.kind == "release"
        }

        self.assertEqual(len(trials), 1)
        self.assertIn(trials[0].id, released)
        self.assertEqual(session.retained_states(), loaded_states(runtime))

        with self.assertRaises(AdmissionRejected):
            session.admitted(trials[0].id)

    def unchanged_after(self, entry):
        runtime = Runtime(image_state())
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
        self.assertEqual(admitted_run(session, H("handle"), 1), 2)
        state = runtime.active.state
        versions = runtime.versions
        total = runtime.read(TOTAL)
        session.invalidate_compiler_generation(1)

        # The program's catch must not see the failure.
        with no_host_lowering():
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
        self.assertEqual(session.retained_states(), loaded_states(runtime))

    def test_failed_activation_compilation_changes_nothing(self):
        self.unchanged_after("guarded")

    def test_failed_trial_compilation_changes_nothing(self):
        self.unchanged_after("guarded_trial")

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


class Reuse(unittest.TestCase):
    """Section 4.3: unchanged nodes reuse their artifacts, everything else is
    compiled, and nothing is inferred from a version alone."""

    def activate_once(self, entry, *args):
        runtime = Runtime(image_state())
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
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

    def observed_split(self, session, state):
        produced, reused = set(), set()

        for e in session.trace():
            if e.target_state_id != state.id:
                continue

            if e.kind == "produce":
                produced.add((e.entity, e.version))
            elif e.kind == "reuse":
                reused.add((e.entity, e.version))

        return produced, reused

    def test_an_update_compiles_only_what_changed(self):
        session, source, before, destination = self.activate_once(
            "upgrade", 10, 2, 13,
        )
        produced, reused = self.expected_split(source, destination)

        self.assertTrue(produced)
        self.assertTrue(reused)
        self.assertEqual(
            self.observed_split(session, destination), (produced, reused),
        )

        after = session.admitted(destination.id)
        fresh = HostedSession(Runtime(destination))
        fresh.prepare(compiler_generation=1)
        compiled = fresh.admitted(destination.id)

        for key in sorted(reused, key=lambda k: k[0].value):
            with self.subTest(node=key[0].value):
                self.assertIs(after[key].chunk, before[key].chunk)
                self.assertEqual(after[key].chunk, compiled[key].chunk)
                self.assertEqual(
                    after[key].chunk,
                    bytecode.lower(relation_of(destination.values[key[0]])),
                )

    def test_moved_nodes_are_compiled_again(self):
        session, source, _, destination = self.activate_once("move")
        moved = {
            (node, destination.values[node].version_id)
            for node, owner in code_nodes(destination)
            if node in source.values
            and source.values[node].version_id
            == destination.values[node].version_id
            and source.owner_of(node) != owner
        }
        produced, reused = self.observed_split(session, destination)

        self.assertTrue(moved, "the witness must move nodes")
        self.assertLessEqual(moved, produced)
        self.assertFalse(moved & reused)
        self.assertEqual(
            (produced, reused), self.expected_split(source, destination),
        )


class Lifetime(unittest.TestCase):
    """Section 4.1: a version owns its artifacts."""

    def test_repeated_updates_release_retired_versions(self):
        runtime = Runtime(image_state())
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
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
                self.assertEqual(
                    session.retained_states(), loaded_states(runtime),
                )

        released = {
            e.target_state_id for e in session.trace() if e.kind == "release"
        }

        self.assertEqual(len(seen), UPDATES + 1)
        self.assertLessEqual(seen - {runtime.active.state.id}, released)

        gc.collect()
        self.assertIsNone(
            witness(), "a retired version's artifact record is still alive",
        )

    def test_a_held_version_keeps_its_artifacts_until_released(self):
        runtime = Runtime(image_state())
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
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
        self.assertEqual(session.retained_states(), loaded_states(runtime))
        self.assertEqual(len(runtime.versions), 1)


class InstructionTable(unittest.TestCase):
    """Section 5.2: one table of the instructions lowering emits."""

    def table(self):
        from shear.instructions import INSTRUCTIONS

        return INSTRUCTIONS

    def test_the_table_is_the_emitted_instruction_set(self):
        self.assertEqual(
            set(self.table()),
            dispatched(machine._execute, "op") - INTERNAL,
        )

    def test_host_lowering_agrees_with_the_table(self):
        table = self.table()
        chunks = [
            (kind, bytecode.lower(_node_for(kind)))
            for kind in operations.OPERATIONS
        ]

        for example in EXAMPLES:
            state = load(example.program)

            for node, _ in code_nodes(state):
                relation = relation_of(state.values[node])
                chunks.append((example.name, bytecode.lower(relation)))

        for where, chunk in chunks:
            for instruction in chunk:
                with self.subTest(where=where, op=instruction[0]):
                    self.assertIn(instruction[0], table)
                    self.assertEqual(
                        len(instruction) - 1, table[instruction[0]].operands,
                    )

    def test_the_vm_lacks_exactly_the_declared_instructions(self):
        table = set(self.table())

        self.assertLessEqual(set(vm._ORDER), table)
        self.assertEqual(table - set(vm._ORDER), VM_MISSING_INSTRUCTIONS)

    def test_admission_accepts_host_chunks_and_rejects_extra_operands(self):
        for example in EXAMPLES:
            if example.name not in LIVE - {"bootstrap"}:
                continue

            state = load(example.program)

            for node, owner in code_nodes(state):
                chunk = bytecode.lower(relation_of(state.values[node]))

                with self.subTest(example=example.name, node=node.value):
                    validation.validate_chunk(state, node, owner, chunk)

                    for index, instruction in enumerate(chunk[:-1]):
                        widened = (
                            *chunk[:index],
                            (*instruction, None),
                            *chunk[index + 1:],
                        )

                        with self.assertRaises(AdmissionRejected):
                            validation.validate_chunk(
                                state, node, owner, widened,
                            )


if __name__ == "__main__":
    unittest.main()
