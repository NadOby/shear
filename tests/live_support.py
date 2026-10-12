"""Shared support for the Plan-owned task 31 acceptance tests
(docs/live_evolution.md, issue #67): the live-image program and its step
tables, the problem-carrying activation forms, and the oracles.

Oracles, all independent of the SHEAR compiler under test:

* ordinary host execution (``lang.run``) of the same steps, compared step by
  step: results, failures, cell content, active ``StateID``, loaded versions
  and holds (``drive``);
* ``bytecode.lower``, the independent host lowering, compared with every
  chunk the machine actually opens (``observed_chunks``, ``assert_observed``),
  which does not rely on the session's own trace;
* the heap, for artifact records nothing should keep alive
  (``assert_no_orphans``).

The trace-based provenance check (``assert_provenance``) is a separate,
weaker assertion: it reads what the session reports about itself.
"""


from __future__ import annotations

import contextlib
import gc
from unittest import mock
from weakref import WeakKeyDictionary

from shear import EntityID, Runtime, bytecode, machine
from shear.canonical import canonical_serialize, canonicalize
from shear.examples._support import program
from shear.hosted_bootstrap import AdmissionRejected, HostedSession
from shear.hosted_bootstrap.artifacts import TARGET, Artifact
from shear.lang import Function, _definition_of, links, load, run as host_run
from shear.relations import relation_of
from shear.syntax import parse

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

fn same_trial():
    let old = code(handle)
    catch(trial(handle(1), handle = function(item(old, 0), item(old, 1))))

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

fn same_activate():
    let old = code(handle)
    activate(handle = function(item(old, 0), item(old, 1)))
    handle(1)

fn bound_first():
    activate(handle = fn(x): x * 3)
    let r = catch(activate(handle = fn(x): len((x, 7))))
    item(item(r, 1), 1)

fn grow(k):
    let old = code(handle)
    function(item(old, 0), quote(unquote(item(old, 1)) + len((literal(k),))))

fn guarded(k):
    catch(activate(handle = grow(k)))

fn guarded_trial(k):
    catch(trial(handle(1), handle = grow(k)))

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
    ("same_trial", (), True, ("ok", 12), 2),
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

SAME = (
    ("same_activate", (), True, 2, 1),
    ("handle", (1,), False, 2, 2),
)

BOUND = (
    ("bound_first", (), True, "activation_rejected", 0),
    ("handle", (5,), False, 15, 0),
)

# Activation and trial forms whose link does not resolve, or whose value is
# not a function. Host lowering keeps the problem in the instruction
# (bytecode._lower_activation); each fails as a language error.
G = H("le_g")
MALFORMED = {
    H("le_activate_unknown"): ("activate", "nolink", ("lit", 1)),
    H("le_trial_unknown_target"): (
        "trial", ("call", "le_g", ("lit", 1)), "nolink", ("lit", 1),
    ),
    H("le_trial_unknown_call"): (
        "trial", ("call", "nolink", ("lit", 1)), "le_g", ("lit", 1),
    ),
    H("le_activate_not_a_function"): ("activate", "le_g", ("lit", 1)),
}


def image_state():
    return load(parse(IMAGE))


def malformed_state():
    entities = {G: Function(("x",), ("arg", "x"))}

    for entry, body in MALFORMED.items():
        entities[entry] = Function((), ("catch", body))
        entities[H(f"{entry.value}.links")] = links(entry, le_g=G)

    return load(program(entities))


def forbid_host_lowering(*args, **kwargs):
    raise AssertionError("host lowering reached during an admitted run")


@contextlib.contextmanager
def no_host_lowering():
    """Forbid every host lowering entry, ``bytecode.lower`` included, for the
    duration of an admitted run. The oracle calls ``bytecode.lower`` only
    after the run."""

    with (
        mock.patch.object(
            bytecode, "chunk_of", side_effect=forbid_host_lowering,
        ),
        mock.patch.object(
            bytecode, "lower_value", side_effect=forbid_host_lowering,
        ),
        mock.patch.object(
            bytecode, "lower", side_effect=forbid_host_lowering,
        ),
    ):
        yield


def code_nodes(state):
    """``(node, owner)`` for every code node of every function."""

    for owner, value in state.values.items():
        if _definition_of(value) is None:
            continue

        for node in state.owned_subtree(owner) - {owner}:
            yield node, owner


def admitted_or_none(session, version):
    """The artifact set ``version`` owns, or None if it owns none."""

    try:
        return session.admitted(version)
    except AdmissionRejected:
        return None


@contextlib.contextmanager
def observed_chunks(session):
    """Record every chunk the machine opens for the target, at the machine's
    own chunk boundaries (``_open``, ``_open_closure``, ``_child_chunk``),
    independently of the session's trace.

    Each record is ``(version, entity, chunk, artifact)``: the version whose
    frame opened the chunk, and the artifact admitted for the node in the set
    that version owns at that moment, or None. A trial's version owns its own
    set while the trial runs.
    """

    records = []
    compiler = session.compiler_source_state.id
    open_ = machine._open
    open_closure = machine._open_closure
    child_chunk = machine._child_chunk

    def record(version, entity, chunk):
        if version.state.id == compiler:
            return

        owned = admitted_or_none(session, version)
        key = (entity, version.state.values[entity].version_id)
        artifact = None if owned is None else owned.get(key)
        records.append((version, entity, chunk, artifact))

    def observe_open(activation, *args, **kwargs):
        chunk, env, node = open_(activation, *args, **kwargs)
        record(activation.hold.version, node, chunk)
        return chunk, env, node

    def observe_open_closure(activation, *args, **kwargs):
        chunk, env, node = open_closure(activation, *args, **kwargs)
        record(activation.hold.version, node, chunk)
        return chunk, env, node

    def observe_child_chunk(activation, entity, function):
        chunk = child_chunk(activation, entity, function)
        record(activation.hold.version, entity, chunk)
        return chunk

    with (
        mock.patch.object(machine, "_open", side_effect=observe_open),
        mock.patch.object(
            machine, "_open_closure", side_effect=observe_open_closure,
        ),
        mock.patch.object(
            machine, "_child_chunk", side_effect=observe_child_chunk,
        ),
    ):
        yield records


def assert_observed(test, records):
    """Every opened chunk is host lowering's chunk of its node, and the very
    object admitted for it in the set its frame's version owns."""

    test.assertTrue(records, "no chunk was opened")
    checked = set()

    for version, entity, chunk, artifact in records:
        key = (id(version), entity, id(chunk))

        if key in checked:
            continue

        checked.add(key)
        state = version.state

        with test.subTest(entity=entity.value, state=state.id.value[:12]):
            test.assertEqual(
                chunk, bytecode.lower(relation_of(state.values[entity])),
            )
            test.assertIsNotNone(
                artifact, "an opened chunk with no admitted artifact",
            )
            test.assertIs(artifact.chunk, chunk)


def admitted_run(session, entry, *args, may_activate=False, records=None):
    """``session.run`` with host lowering forbidden and the opened chunks
    recorded into ``records``. An admission failure is a test failure,
    never an expected program failure."""

    with contextlib.ExitStack() as stack:
        stack.enter_context(no_host_lowering())

        seen = (
            None
            if records is None
            else stack.enter_context(observed_chunks(session))
        )

        try:
            return session.run(entry, *args, may_activate=may_activate)
        except AdmissionRejected as exc:
            raise AssertionError(
                "a hosted admission failure is not a SHEAR program error"
            ) from exc
        finally:
            if seen is not None:
                records.extend(seen)


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
    """Artifact id to the states it was admitted for."""

    found = {}

    for e in events:
        if e.kind in ("admit", "reuse") and e.route == "host-admission":
            found.setdefault(e.artifact_id, set()).add(e.target_state_id)

    return found


def assert_provenance(test, events):
    """The trace's own account: every executed artifact has an authentic
    chain and was admitted for the state it ran in."""

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
            test.assertIn(
                event.target_state_id, states.get(event.artifact_id, ()),
            )


def live_target_artifacts(session):
    """Target artifact records still alive for this session's states."""

    states = {e.target_state_id for e in session.trace()}
    gc.collect()

    return [
        o for o in gc.get_objects()
        if isinstance(o, Artifact)
        and o.domain == TARGET
        and o.state_id in states
    ]


def retained_as_loaded(test, session):
    """The versions that own artifact sets are the loaded versions."""

    test.assertEqual(
        session.retained_versions(),
        frozenset(session.target_runtime.versions),
    )


def assert_no_orphans(test, session):
    """Nothing but the loaded versions' sets keeps target artifacts alive,
    and no frame still holds a version."""

    runtime = session.target_runtime
    retained = sum(
        len(session.admitted(version))
        for version in session.retained_versions()
    )

    retained_as_loaded(test, session)
    test.assertEqual(len(live_target_artifacts(session)), retained)

    for version in runtime.versions:
        test.assertEqual(version.holds, frozenset())


class HostedRunner:
    """A ``play``-compatible runner: one session per runtime, every opened
    chunk recorded."""

    def __init__(self, generation=1):
        self.generation = generation
        self.sessions = WeakKeyDictionary()
        self.records = []

    def __call__(self, runtime, entry, *args, may_activate=False):
        session = self.sessions.get(runtime)

        if session is None:
            session = HostedSession(runtime)
            session.prepare(compiler_generation=self.generation)
            self.sessions[runtime] = session

        return admitted_run(
            session, entry, *args,
            may_activate=may_activate, records=self.records,
        )


def host(runtime, entry, *args, may_activate=False):
    return host_run(runtime, entry, *args, may_activate=may_activate)


def outcome(call):
    try:
        return ("ok", canonical_serialize(canonicalize(call())))
    except AssertionError:
        raise
    except Exception as exc:
        return ("raised", type(exc).__name__)


def observation(runtime):
    return (
        runtime.read(TOTAL),
        runtime.active.state.id,
        len(runtime.versions),
        tuple(len(version.holds) for version in runtime.versions),
    )


def drive(test, steps, generation=1, session_out=None):
    """Run ``steps`` on a fresh image on the host and on the admitted route.

    Checks each step's hand-written expectation on the host, that the hosted
    observation equals the host's, that the versions owning artifact sets are
    the loaded versions at every step boundary, and that every opened chunk
    is host lowering's and the admitted one. Returns the session.
    """

    host_runtime = Runtime(image_state())
    runtime = Runtime(image_state())
    session = HostedSession(runtime)
    session.prepare(compiler_generation=generation)
    records = []

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
                    session, H(entry), *args,
                    may_activate=may, records=records,
                )
            )
            test.assertEqual(actual, expected)
            test.assertEqual(observation(runtime), observation(host_runtime))
            retained_as_loaded(test, session)

    assert_observed(test, records)
    assert_provenance(test, session.trace())
    return session
