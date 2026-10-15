"""Diagnostic measurements of live evolution on the hosted route
(docs/live_evolution.md section 7).

``python3 -m shear.hosted_bootstrap.diagnostics`` prints these with the other
workloads. The method is task 23's: repeated untraced observations with
their medians, peak memory in a separate traced pass, no ratio between
dissimilar workloads, D4's targets diagnostic only.

The workload is a small live image: a cell, ``handle``, ``plus`` (which builds
a changed ``handle`` from ``code(handle)``) and ``update``, which activates
it, plus ``extra`` unrelated one-line functions. One valid update changes
``handle`` only. Two kinds of update fail. A *trial-rejected* update is the
image's own: the program tries a candidate whose answer is wrong and does not
activate it; the candidate is compiled and admitted, run in the trial and
released. A *refused* update is an injected failure: the same update as the
valid one runs while admission refuses the ``ADD`` instruction, so the
program's activation ends with ``AdmissionRejected`` after the compiler
produced a chunk, and no unchanged node is reused (every reused chunk with
``ADD`` is refused too). Phases are timed by wrapping the functions that
perform them, which adds a call of overhead to each.
"""

from __future__ import annotations

import contextlib
import time
import tracemalloc
from statistics import median
from typing import Any, Callable, Iterator

from .. import EntityID, machine
from ..instructions import INSTRUCTIONS
from ..lang import load
from ..runtime import Runtime
from ..syntax import parse
from .errors import AdmissionRejected
from .session import HostedSession
from .target import HostedTarget
from .trace import PRODUCE, REUSE

HANDLE = EntityID("handle")
UPDATE = EntityID("update")
TRIAL_REJECTED = EntityID("rejected")
SIZES = (10, 100, 1000)
PHASES = (
    "construction",
    "staging",
    "compilation",
    "reuse",
    "admission",
    "switch",
)

_IMAGE = '''
cell total: int in 0.. = 0

fn handle(x):
    total = total + x
    x + 1

fn plus(k):
    let old = code(handle)
    function(item(old, 0), quote(unquote(item(old, 1)) + literal(k)))

fn update(k):
    activate(handle = plus(k))
    k

fn verdict(r, expected):
    if item(r, 0) == "ok":
        "passed" if item(r, 1) == expected else "wrong"
    else:
        item(item(r, 1), 1)

fn rejected(k):
    verdict(catch(trial(handle(2), handle = plus(k))), 0)
'''


def image(extra: int) -> str:
    """The live image with ``extra`` unrelated functions."""

    return _IMAGE + "".join(
        f"\nfn filler{number}(x):\n    x + {number}\n"
        for number in range(extra)
    )


def _fresh(extra: int) -> tuple[Runtime, HostedSession]:
    runtime = Runtime(load(parse(image(extra))))
    session = HostedSession(runtime)
    session.prepare(compiler_generation=1)

    return runtime, session


class _Clock:
    """Seconds spent in the phases of the update in progress."""

    def __init__(self) -> None:
        self.totals = dict.fromkeys(PHASES, 0.0)
        self.marks: dict[str, float] = {}

    def reset(self) -> None:
        self.totals = dict.fromkeys(PHASES, 0.0)
        self.marks = {}

    def add(self, phase: str, seconds: float) -> None:
        self.totals[phase] += seconds


def _wrapped(
    clock: _Clock,
    original: Callable[..., Any],
    phase: str,
) -> Callable[..., Any]:
    def timed(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()

        try:
            return original(*args, **kwargs)
        finally:
            clock.add(phase, time.perf_counter() - started)

    return timed


@contextlib.contextmanager
def _instrumented(clock: _Clock) -> Iterator[None]:
    """Wrap the phase functions for the duration. Staging runs from the start
    of ``Runtime.activate`` (or ``Runtime.trial``) to the start of the
    target's ``candidate``; the switch runs from the end of ``candidate`` to
    the end of ``activate``. A trial has no switch."""

    activate = Runtime.activate
    trial = Runtime.trial
    candidate = HostedTarget.candidate
    define = machine._define_for_operation
    produce = HostedTarget._produce
    admit = HostedTarget._admit
    reuse = HostedTarget._reuse

    def timed_activate(self: Runtime, *args: Any, **kwargs: Any) -> Any:
        clock.marks["activate"] = time.perf_counter()

        try:
            return activate(self, *args, **kwargs)
        finally:
            if "candidate_end" in clock.marks:
                clock.add(
                    "switch",
                    time.perf_counter() - clock.marks.pop("candidate_end"),
                )

    def timed_trial(self: Runtime, *args: Any, **kwargs: Any) -> Any:
        clock.marks["activate"] = time.perf_counter()

        try:
            return trial(self, *args, **kwargs)
        finally:
            clock.marks.pop("candidate_end", None)

    def timed_candidate(self: HostedTarget, *args: Any, **kwargs: Any) -> Any:
        entered = time.perf_counter()
        clock.add("staging", entered - clock.marks.pop("activate", entered))

        answer = candidate(self, *args, **kwargs)
        clock.marks["candidate_end"] = time.perf_counter()

        return answer

    Runtime.activate = timed_activate  # type: ignore[method-assign]
    Runtime.trial = timed_trial  # type: ignore[method-assign]
    HostedTarget.candidate = timed_candidate  # type: ignore[method-assign]
    machine._define_for_operation = _wrapped(  # type: ignore[assignment]
        clock, define, "construction",
    )
    HostedTarget._produce = _wrapped(  # type: ignore[method-assign]
        clock, produce, "compilation",
    )
    HostedTarget._admit = _wrapped(  # type: ignore[method-assign]
        clock, admit, "admission",
    )
    HostedTarget._reuse = _wrapped(  # type: ignore[method-assign]
        clock, reuse, "reuse",
    )

    try:
        yield
    finally:
        Runtime.activate = activate  # type: ignore[method-assign]
        Runtime.trial = trial  # type: ignore[method-assign]
        HostedTarget.candidate = candidate  # type: ignore[method-assign]
        machine._define_for_operation = define  # type: ignore[assignment]
        HostedTarget._produce = produce  # type: ignore[method-assign]
        HostedTarget._admit = admit  # type: ignore[method-assign]
        HostedTarget._reuse = reuse  # type: ignore[method-assign]


@contextlib.contextmanager
def _admission_refuses(op: str) -> Iterator[None]:
    """Admission refuses every chunk with ``op`` for the duration."""

    entry = INSTRUCTIONS.pop(op)  # type: ignore[attr-defined]

    try:
        yield
    finally:
        INSTRUCTIONS[op] = entry  # type: ignore[index]


def _counts(session: HostedSession, since: int) -> dict[str, int]:
    events = session.trace()[since:]

    return {
        "produced": sum(1 for event in events if event.kind == PRODUCE),
        "reused": sum(1 for event in events if event.kind == REUSE),
    }


def _retention(runtime: Runtime, session: HostedSession) -> dict[str, int]:
    retained = session.retained_versions()

    return {
        "loaded_versions": len(runtime.versions),
        "retained_sets": len(retained),
        "artifacts": sum(len(session.admitted(v)) for v in retained),
    }


def _update(
    runtime: Runtime,
    session: HostedSession,
    clock: _Clock,
    k: int,
    kind: str,
) -> dict[str, Any]:
    """One update of ``handle`` by ``k`` (``kind`` is ``"valid"``,
    ``"refused"`` or ``"trial_rejected"``): its phases, the produced and
    reused counts, and for a valid one the first call of the changed
    function."""

    valid = kind == "valid"
    clock.reset()
    since = len(session.trace())
    started = time.perf_counter()

    if kind == "trial_rejected":
        answer = session.run(TRIAL_REJECTED, k, may_activate=True)

        if answer != "wrong":
            raise AssertionError(f"the trial was not rejected: {answer!r}")
    elif valid:
        session.run(UPDATE, k, may_activate=True)
    else:
        try:
            session.run(UPDATE, k, may_activate=True)
        except AdmissionRejected:
            pass
        else:
            raise AssertionError("the update was not rejected")

    total = time.perf_counter() - started
    record: dict[str, Any] = {
        "total_s": total,
        **dict(clock.totals),
        **_counts(session, since),
    }

    if valid:
        first = time.perf_counter()
        session.run(HANDLE, 2)
        record["first_call_s"] = time.perf_counter() - first

    record.update(_retention(runtime, session))

    return record


def _phase_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    def summary(key: str) -> dict[str, Any]:
        values = [record[key] for record in records]

        return {
            "observations": [round(value, 6) for value in values],
            "median": round(median(values), 6),
        }

    keys = ["total_s", *PHASES]

    if "first_call_s" in records[0]:
        keys.append("first_call_s")

    return {
        **{key: summary(key) for key in keys},
        "produced": [record["produced"] for record in records],
        "reused": [record["reused"] for record in records],
        "loaded_versions": [record["loaded_versions"] for record in records],
        "retained_sets": [record["retained_sets"] for record in records],
        "artifacts": [record["artifacts"] for record in records],
    }


def updates(count: int, extra: int = 10) -> dict[str, Any]:
    """``count`` valid updates in sequence, then ``count`` trial-rejected and
    ``count`` refused ones, on one live image. Retention is read after every
    update."""

    runtime, session = _fresh(extra)
    clock = _Clock()
    records: dict[str, list[dict[str, Any]]] = {
        "valid": [], "trial_rejected": [], "refused": [],
    }

    with _instrumented(clock):
        for k in range(1, count + 1):
            records["valid"].append(_update(runtime, session, clock, k, "valid"))

        state = runtime.active.state.id

        for k in range(1, count + 1):
            records["trial_rejected"].append(
                _update(runtime, session, clock, k, "trial_rejected")
            )

        with _admission_refuses("ADD"):
            for k in range(1, count + 1):
                records["refused"].append(
                    _update(runtime, session, clock, k, "refused")
                )

        if runtime.active.state.id != state:
            raise AssertionError("a rejected update changed the active state")

    return {
        "functions": 6 + extra,
        **{kind: _phase_summary(found) for kind, found in records.items()},
    }


def peak_memory(count: int, extra: int = 10) -> dict[str, Any]:
    """The same sequence of valid updates in one traced pass; never part of
    a timing."""

    tracemalloc.start()

    try:
        runtime, session = _fresh(extra)
        baseline, _ = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()

        for k in range(1, count + 1):
            session.run(UPDATE, k, may_activate=True)
            session.run(HANDLE, 2)

        current, peak = tracemalloc.get_traced_memory()
        retention = _retention(runtime, session)
    finally:
        tracemalloc.stop()

    return {
        "workload": f"prepare, then {count} valid updates and calls",
        "bytes_after_prepare": baseline,
        "bytes_after_updates": current,
        "peak_bytes": peak,
        **retention,
    }


def scaling(sizes: tuple[int, ...], repeats: int) -> dict[str, Any]:
    """One small edit of ``handle`` at several program sizes. Each repeat is
    a fresh image, so a size's observations are of the same first update."""

    result: dict[str, Any] = {}

    for extra in sizes:
        records = []
        preparation = []

        for _ in range(repeats):
            started = time.perf_counter()
            runtime, session = _fresh(extra)
            preparation.append(time.perf_counter() - started)

            clock = _Clock()

            with _instrumented(clock):
                records.append(_update(runtime, session, clock, 1, "valid"))

        summary = _phase_summary(records)
        summary["preparation_s"] = {
            "observations": [round(value, 6) for value in preparation],
            "median": round(median(preparation), 6),
        }
        result[str(6 + extra)] = summary

    return result


def measure(
    count: int = 20,
    sizes: tuple[int, ...] = SIZES,
    scaling_repeats: int = 3,
) -> dict[str, Any]:
    return {
        "updates": updates(count),
        "peak_memory": peak_memory(count),
        "scaling_functions": scaling(sizes, scaling_repeats),
        "note": (
            "Phases are wrapped calls: construction is the define of the "
            "candidate, staging the runtime's checks up to the target's "
            "report, compilation and admission the SHEAR compiler runs and "
            "the target's checks (reuse is timed apart), switch everything "
            "after admission up to the end of activate. The first call is "
            "the next run of the changed function. Different sizes are "
            "different workloads and are not combined into ratios."
        ),
    }
