"""Diagnostic measurements of the hosted pipeline
(docs/hosted_pipeline.md section 10).

    python3 -m shear.hosted_bootstrap.diagnostics [--repeats N]

Prints one JSON document: the environment, then separately timed phases.
Timings are repeated, untraced observations; each phase reports every
observation and their median. Different workloads are never combined into a
ratio. Peak memory is a separate traced pass, so tracing never affects a
timing. D4's targets are diagnostic only; nothing here asserts them.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
from statistics import median
import subprocess
import sys
import time
import tracemalloc
from typing import Any, Callable

from .. import bytecode
from ..canonical import canonical_serialize, canonicalize
from ..examples import EXAMPLES
from ..lang import _definition_of, load
from ..lang import run as host_run
from ..reconcile import reconcile
from ..relations import relation_of
from ..runtime import Runtime
from ..syntax import render_program
from . import seed
from .descriptors import SUPPORTED_KINDS
from .session import HostedSession

# Fixed, dissimilar workloads: a small recursive function, a data-structure
# function and the embedded compiler's own corpus entry.
WORKLOADS = ("factorial", "insertion_sort", "compiler")
EDIT_WORKLOAD = "factorial"


def _timed(action: Callable[[], Any]) -> tuple[float, Any]:
    started = time.perf_counter()
    result = action()

    return time.perf_counter() - started, result


def _summary(observations: list[float]) -> dict[str, Any]:
    return {
        "observations_s": [round(value, 6) for value in observations],
        "median_s": round(median(observations), 6),
    }


def _repeat(repeats: int, action: Callable[[], Any]) -> dict[str, Any]:
    return _summary([_timed(action)[0] for _ in range(repeats)])


def environment() -> dict[str, Any]:
    def command(*arguments: str) -> str:
        try:
            return subprocess.run(
                arguments, capture_output=True, text=True, timeout=10,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    processor = ""

    try:
        with open("/proc/cpuinfo", encoding="utf-8") as stream:
            for line in stream:
                if line.startswith("model name"):
                    processor = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass

    return {
        "hardware": {
            "machine": platform.machine(),
            "processor": processor or platform.processor(),
            "cpus": os.cpu_count(),
        },
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "os": platform.platform(),
        "revision": command("git", "rev-parse", "HEAD") or "unknown",
        "modified": bool(command("git", "status", "--porcelain")),
    }


def _example(name: str):
    return next(e for e in EXAMPLES if e.name == name)


def _runtime(name: str) -> Runtime:
    example = _example(name)

    return Runtime(load(example.program), example.context)


def _first_step(name: str):
    return _example(name).scenarios[0][0]


def _code_nodes(runtime: Runtime) -> list:
    state = runtime.active.state

    return [
        node
        for owner in sorted(state.values, key=lambda e: e.value)
        if _definition_of(state.values[owner]) is not None
        for node in sorted(
            state.owned_subtree(owner) - {owner}, key=lambda e: e.value,
        )
    ]


def _size(chunk: tuple) -> int:
    return len(canonical_serialize(canonicalize(chunk)))


def initialization(repeats: int) -> dict[str, Any]:
    def source():
        seed.compiler_source_state.cache_clear()
        return seed.compiler_source_state()

    def derive():
        return seed.derive(seed.compiler_source_state())

    def verify():
        seed.verified_manifest.cache_clear()
        return seed.verified_manifest()

    return {
        "compiler_source_state": _repeat(repeats, source),
        "seed_derivation": _repeat(repeats, derive),
        "manifest_verification": _repeat(repeats, verify),
        "seed_nodes": len(seed.verified_manifest().code_nodes),
    }


def generations(repeats: int) -> dict[str, Any]:
    observations: dict[int, list[float]] = {1: [], 2: [], 3: []}

    for _ in range(repeats):
        session = HostedSession(_runtime(WORKLOADS[0]))

        for number in (1, 2, 3):
            observations[number].append(
                _timed(lambda: session.rebuild_through(number))[0]
            )

    session = HostedSession(_runtime(WORKLOADS[0]))
    session.rebuild_through(3)

    return {
        str(number): {
            **_summary(observations[number]),
            "artifacts": len(session.compiler_artifacts(number)),
            "chunk_bytes": sum(
                _size(chunk)
                for chunk in session.compiler_artifacts(number).values()
            ),
        }
        for number in (1, 2, 3)
    }


def target_phases(name: str, repeats: int) -> dict[str, Any]:
    produce: list[float] = []
    admit: list[float] = []
    verify: list[float] = []
    cold: list[float] = []
    warm: list[float] = []
    host: list[float] = []
    step = _first_step(name)

    for _ in range(repeats):
        runtime = _runtime(name)
        session = HostedSession(runtime)
        session.rebuild_through(1)
        session.prepare(compiler_generation=1)
        state = runtime.active.state
        nodes = [
            node for node in _code_nodes(runtime)
            if relation_of(state.values[node]).kind in SUPPORTED_KINDS
        ]

        started = time.perf_counter()
        produced = [(node, *session.produce(node)) for node in nodes]
        produce.append(time.perf_counter() - started)

        started = time.perf_counter()

        for node, chunk, evidence in produced:
            session.admit(
                node, state.values[node].version_id, chunk, evidence,
            )

        admit.append(time.perf_counter() - started)

        started = time.perf_counter()

        for node, chunk, _ in produced:
            if chunk != bytecode.lower(relation_of(state.values[node])):
                raise AssertionError(f"{node.value}: chunk differs from host")

        verify.append(time.perf_counter() - started)

        cold.append(_timed(lambda: session.run(step.entry, *step.args))[0])
        warm.append(_timed(lambda: session.run(step.entry, *step.args))[0])

        ordinary = _runtime(name)
        host.append(_timed(
            lambda: host_run(ordinary, step.entry, *step.args)
        )[0])

    return {
        "entry": step.entry.value,
        "nodes": len(nodes),
        "artifact_chunk_bytes": sum(_size(chunk) for _, chunk, _ in produced),
        "production": _summary(produce),
        "admission": _summary(admit),
        "independent_verification_against_host_lowering": _summary(verify),
        "admitted_cold_execution": _summary(cold),
        "admitted_warm_execution": _summary(warm),
        "ordinary_host_execution_for_reference": _summary(host),
    }


def small_edit(repeats: int) -> dict[str, Any]:
    name = EDIT_WORKLOAD
    step = _first_step(name)
    text = render_program(load(_example(name).program))
    edited = text.replace("n - 1", "n - 2", 1)
    phases: dict[str, list[float]] = {
        "reconciliation": [],
        "preparation_and_admitted_compilation": [],
        "candidate_execution": [],
        "activation": [],
    }

    for _ in range(repeats):
        runtime = _runtime(name)
        session = HostedSession(runtime)
        session.prepare(compiler_generation=1)
        base = runtime.active.state

        spent, result = _timed(lambda: reconcile(base, edited))
        phases["reconciliation"].append(spent)

        candidate = Runtime(result.destination, runtime.context)
        spent, target = _timed(lambda: session._prepared(candidate, 1))
        phases["preparation_and_admitted_compilation"].append(spent)

        phases["candidate_execution"].append(
            _timed(lambda: target.run(step.entry, *step.args))[0]
        )

        activated = _runtime(name)
        phases["activation"].append(
            _timed(lambda: activated.activate(result))[0]
        )

    return {
        "edit": "n - 1 -> n - 2 in factorial",
        **{key: _summary(value) for key, value in phases.items()},
    }


def peak_memory() -> dict[str, Any]:
    """One traced pass; never part of a timing."""

    tracemalloc.start()

    try:
        session = HostedSession(_runtime(WORKLOADS[0]))
        session.rebuild_through(3)
        session.prepare(compiler_generation=1)
        step = _first_step(WORKLOADS[0])
        session.run(step.entry, *step.args)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    return {
        "workload": f"rebuild_through(3), prepare and run of {WORKLOADS[0]}",
        "peak_bytes": peak,
    }


def measure(repeats: int) -> dict[str, Any]:
    return {
        "environment": environment(),
        "repeats": repeats,
        "initialization": initialization(repeats),
        "compiler_generations": generations(repeats),
        "targets": {
            name: target_phases(name, repeats) for name in WORKLOADS
        },
        "small_edit": small_edit(repeats),
        "peak_memory": peak_memory(),
        "note": (
            "Workloads differ and are not combined into ratios. Task 23 "
            "and Task 29 measurements are historical and unchanged."
        ),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m " + __spec__.name)
    parser.add_argument("--repeats", type=int, default=5)
    arguments = parser.parse_args(argv)

    if arguments.repeats < 1:
        parser.error("--repeats must be positive")

    json.dump(measure(arguments.repeats), sys.stdout, indent=2)
    sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
