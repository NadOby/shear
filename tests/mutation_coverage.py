"""Which oracle test modules execute which lines of the mutation targets.

A campaign input and a diagnostic, never a gate. Each oracle module is run
once in its own process, as the oracle runs it, with a line tracer
(``sys.monitoring``, Python 3.12 or newer) that records the lines of the
target files it executes. The result, a coverage map, serves two uses:

- *ordering*: a mutant is run against the modules that execute its line
  first, then the modules that might (those that start processes, whose lines
  the tracer cannot see, or that did not run cleanly), then the rest. Only the
  order of one fail-fast run changes; the modules run are the same, so the
  outcome of a mutant is the one the default order gives;
- *report*: the executable lines of chosen targets that no module executes.

The map is built from, and valid for, one exact tree: it carries a
fingerprint of every file under ``shear/`` and ``tests/`` and a campaign
refuses a map that does not match. It is generated in CI and never checked in.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from tests import mutation, mutation_oracle
from tests.mutation_catalog import TARGETS


MAP_VERSION = 1

COVERED = "covered"
SUBPROCESS_ONLY = "subprocess_only"
UNCOVERED = "uncovered"


@dataclass(frozen=True)
class ModuleCoverage:
    """What one traced oracle module executed."""

    complete: bool
    opaque: bool
    seconds: float
    lines: dict[str, frozenset[int]]

    @property
    def uncertain(self) -> bool:
        """Whether the module may execute lines the tracer did not see."""

        return self.opaque or not self.complete


@dataclass(frozen=True)
class CoverageMap:
    fingerprint: str
    order: tuple[str, ...]
    modules: dict[str, ModuleCoverage]

    def covering(self, target: str, line: int) -> tuple[str, ...]:
        """Modules seen executing the line, in oracle order."""

        return tuple(
            module
            for module in self.order
            if module in self.modules
            and line in self.modules[module].lines.get(target, ())
        )

    def uncertain(self, target: str, line: int) -> tuple[str, ...]:
        """Modules not seen executing the line that might still reach it.

        A module absent from the map counts as one that might.
        """

        seen = set(self.covering(target, line))

        return tuple(
            module
            for module in self.order
            if module not in seen
            and (
                module not in self.modules
                or self.modules[module].uncertain
            )
        )

    def first(self, target: str, line: int) -> tuple[str, ...]:
        """The modules to run before the others for a mutant on this line."""

        return self.covering(target, line) + self.uncertain(target, line)

    def status(self, target: str, line: int) -> str:
        """Whether the line is executed, only possibly reached, or neither."""

        if self.covering(target, line):
            return COVERED

        if self.uncertain(target, line):
            return SUBPROCESS_ONLY

        return UNCOVERED


def fingerprint(root: Path) -> str:
    """A digest of every file under ``shear/`` and ``tests/``."""

    from hashlib import sha1

    digest = sha1(usedforsecurity=False)

    for directory in ("shear", "tests"):
        for path in sorted((root / directory).rglob("*")):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or path.suffix == ".jsonl"
            ):
                continue

            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(
                mutation.git_blob_id(path.read_bytes()).encode()
            )
            digest.update(b"\0")

    return digest.hexdigest()


def _require_monitoring() -> None:
    if not hasattr(sys, "monitoring"):
        raise RuntimeError(
            "coverage tracing needs sys.monitoring (Python 3.12 or newer)"
        )


def trace_module(
    root: Path,
    module: str,
    targets: tuple[str, ...],
) -> dict[str, object]:
    """Run one test module and record the target lines it executes.

    ``module`` is a dotted module name. The run applies the oracle's memory
    cap, so the module behaves as it does inside a mutation run.
    """

    _require_monitoring()

    monitoring = sys.monitoring
    tool = monitoring.COVERAGE_ID
    paths = {
        str((root / target).resolve()): target
        for target in targets
    }
    lines: dict[str, set[int]] = {target: set() for target in targets}
    resolved: dict[str, str | None] = {}

    def on_line(code: object, line: int) -> object:
        filename = code.co_filename  # type: ignore[attr-defined]

        if filename not in resolved:
            resolved[filename] = paths.get(
                str(Path(filename).resolve())
            )

        target = resolved[filename]

        if target is not None:
            lines[target].add(line)

        # A location needs reporting once; this keeps tracing cheap.
        return monitoring.DISABLE

    spawned: list[str] = []
    patches = _spawn_detectors(spawned)

    monitoring.use_tool_id(tool, "shear-mutation-coverage")
    monitoring.register_callback(tool, monitoring.events.LINE, on_line)
    monitoring.set_events(tool, monitoring.events.LINE)
    started = time.perf_counter()

    try:
        mutation_oracle.limit_memory()
        output = io.StringIO()
        result = unittest.TextTestRunner(
            verbosity=0,
            stream=output,
        ).run(
            unittest.defaultTestLoader.loadTestsFromName(module)
        )
    finally:
        monitoring.set_events(tool, 0)
        monitoring.register_callback(tool, monitoring.events.LINE, None)
        monitoring.free_tool_id(tool)

        for restore in patches:
            restore()

    if not result.wasSuccessful():
        print(output.getvalue(), file=sys.stderr)

    return {
        "complete": result.wasSuccessful(),
        "opaque": bool(spawned),
        "seconds": time.perf_counter() - started,
        "lines": {
            target: sorted(seen)
            for target, seen in lines.items()
            if seen
        },
    }


def _spawn_detectors(spawned: list[str]) -> list:
    """Record every attempt to start another process; return the undo steps.

    Lines a child process executes are invisible to the tracer, so a module
    that starts one is *opaque*: it may execute more than the map shows.
    """

    undo = []

    def wrap(owner: object, name: str) -> None:
        original = getattr(owner, name, None)

        if original is None:
            return

        def detector(*args: object, **kwargs: object) -> object:
            spawned.append(name)
            return original(*args, **kwargs)

        setattr(owner, name, detector)
        undo.append(lambda: setattr(owner, name, original))

    original_init = subprocess.Popen.__init__

    def popen_init(self: object, *args: object, **kwargs: object) -> None:
        spawned.append("Popen")
        original_init(self, *args, **kwargs)  # type: ignore[arg-type]

    subprocess.Popen.__init__ = popen_init  # type: ignore[method-assign]
    undo.append(
        lambda: setattr(subprocess.Popen, "__init__", original_init)
    )

    for name in ("fork", "system", "posix_spawn", "posix_spawnp"):
        wrap(os, name)

    return undo


def _module_from(value: dict[str, object]) -> ModuleCoverage:
    return ModuleCoverage(
        complete=bool(value["complete"]),
        opaque=bool(value["opaque"]),
        seconds=float(value["seconds"]),  # type: ignore[arg-type]
        lines={
            target: frozenset(seen)  # type: ignore[arg-type]
            for target, seen in value["lines"].items()  # type: ignore[attr-defined]
        },
    )


def _trace_in_process(root: Path, module: str) -> ModuleCoverage:
    """Trace one module in a fresh interpreter, as the oracle would run it."""

    with tempfile.TemporaryDirectory() as scratch:
        out = Path(scratch) / "trace.json"
        done = subprocess.run(
            [
                sys.executable,
                "-m",
                "tests.mutation_coverage",
                "trace",
                f"tests.{module}",
                str(out),
            ],
            cwd=root,
            env=mutation._suite_environment(),
            capture_output=True,
        )

        try:
            return _module_from(json.loads(out.read_text()))
        except (OSError, ValueError, KeyError):
            # No usable trace: the module may execute anything.
            sys.stderr.write(
                f"coverage trace of {module} failed "
                f"(exit {done.returncode})\n"
                + done.stderr.decode(errors="replace")
            )

            return ModuleCoverage(
                complete=False,
                opaque=True,
                seconds=0.0,
                lines={},
            )


def build(root: Path, jobs: int | None = None) -> CoverageMap:
    """Trace every oracle module, ``jobs`` at a time."""

    order = mutation_oracle.modules()

    with ThreadPoolExecutor(jobs or os.cpu_count() or 1) as pool:
        traced = list(
            pool.map(
                lambda module: _trace_in_process(root, module),
                order,
            )
        )

    return CoverageMap(
        fingerprint=fingerprint(root),
        order=order,
        modules=dict(zip(order, traced)),
    )


def dump(coverage: CoverageMap, path: Path) -> None:
    path.write_text(
        json.dumps({
            "version": MAP_VERSION,
            "fingerprint": coverage.fingerprint,
            "order": list(coverage.order),
            "modules": {
                module: {
                    "complete": value.complete,
                    "opaque": value.opaque,
                    "seconds": value.seconds,
                    "lines": {
                        target: sorted(seen)
                        for target, seen in value.lines.items()
                    },
                }
                for module, value in coverage.modules.items()
            },
        }),
        encoding="utf-8",
    )


def load(path: Path, root: Path) -> CoverageMap:
    """Read a coverage map and require it to describe the current tree."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        coverage = CoverageMap(
            fingerprint=value["fingerprint"],
            order=tuple(value["order"]),
            modules={
                module: _module_from(entry)
                for module, entry in value["modules"].items()
            },
        )
        version = value["version"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(
            f"coverage map {path} is missing or malformed: {exc}"
        ) from exc

    if version != MAP_VERSION:
        raise ValueError(
            f"coverage map {path} has unsupported version {version!r}"
        )

    current = fingerprint(root)

    if coverage.fingerprint != current:
        raise ValueError(
            f"coverage map {path} is stale: it was built for tree "
            f"{coverage.fingerprint}, this tree is {current}"
        )

    if coverage.order != mutation_oracle.modules():
        raise ValueError(
            f"coverage map {path} does not list the current oracle modules"
        )

    return coverage


def executable_lines(source: str, filename: str) -> frozenset[int]:
    """The lines of ``source`` that compile to code."""

    pending = [compile(source, filename, "exec")]
    found: set[int] = set()

    while pending:
        code = pending.pop()
        found.update(
            line
            for _, _, line in code.co_lines()
            if line is not None and line > 0
        )
        pending.extend(
            const
            for const in code.co_consts
            if hasattr(const, "co_lines")
        )

    return frozenset(found)


def _ranges(lines: list[int]) -> str:
    spans: list[str] = []
    start = previous = None

    for line in lines:
        if start is None:
            start = previous = line
        elif line == previous + 1:
            previous = line
        else:
            spans.append(
                str(start) if start == previous else f"{start}-{previous}"
            )
            start = previous = line

    if start is not None:
        spans.append(
            str(start) if start == previous else f"{start}-{previous}"
        )

    return ", ".join(spans)


def report(
    coverage: CoverageMap,
    root: Path,
    prefixes: tuple[str, ...] = (),
) -> dict[str, object]:
    """The executable lines of the chosen targets that no module executes.

    A diagnostic only. Lines listed here may still be reached by the
    ``uncertain`` modules (they start processes, ran with failures, or are
    missing from the map); the tracer cannot see those.
    """

    chosen = [
        target
        for target in TARGETS
        if not prefixes
        or any(target.startswith(prefix) for prefix in prefixes)
    ]
    targets = []

    for target in chosen:
        executable = executable_lines(
            (root / target).read_text(),
            target,
        )
        seen: set[int] = set()

        for value in coverage.modules.values():
            seen.update(value.lines.get(target, ()))

        missed = sorted(executable - seen)

        targets.append({
            "target": target,
            "executable": len(executable),
            "executed": len(executable) - len(missed),
            "unexecuted": missed,
        })

    return {
        "targets": targets,
        "uncertain_modules": sorted(
            module
            for module in coverage.order
            if module not in coverage.modules
            or coverage.modules[module].uncertain
        ),
    }


def render(result: dict[str, object]) -> str:
    out = [
        "coverage diagnostic (not a gate): executable lines of the mutation "
        "targets that no oracle module executes",
    ]

    for entry in result["targets"]:  # type: ignore[attr-defined]
        total = entry["executable"]
        percent = 100.0 * entry["executed"] / total if total else 100.0
        out.append(
            f"{entry['target']}: {entry['executed']}/{total} "
            f"({percent:.1f}%)"
        )

        if entry["unexecuted"]:
            out.append(f"  unexecuted: {_ranges(entry['unexecuted'])}")

    uncertain = result["uncertain_modules"]

    if uncertain:
        out.append(
            "modules whose child processes the tracer cannot see (they "
            "may reach some unexecuted lines): " + ", ".join(uncertain)  # type: ignore[arg-type]
        )

    return "\n".join(out)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.mutation_coverage",
        description="Line coverage of the mutation targets per oracle module.",
    )
    actions = parser.add_subparsers(dest="action", required=True)

    build_parser = actions.add_parser(
        "build",
        help="trace every oracle module and write the coverage map",
    )
    build_parser.add_argument("--out", type=Path, required=True)
    build_parser.add_argument("--jobs", type=int)

    report_parser = actions.add_parser(
        "report",
        help="print the unexecuted lines of chosen targets (a diagnostic)",
    )
    report_parser.add_argument(
        "--map",
        type=Path,
        help="use this coverage map instead of tracing now",
    )
    report_parser.add_argument(
        "--json",
        type=Path,
        help="also write the report as JSON",
    )
    report_parser.add_argument(
        "prefixes",
        nargs="*",
        help="target path prefixes; none selects every target",
    )

    trace_parser = actions.add_parser(
        "trace",
        help="(internal) trace one module in this process",
    )
    trace_parser.add_argument("module")
    trace_parser.add_argument("out", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = mutation.ROOT

    if args.action == "trace":
        value = trace_module(root, args.module, TARGETS)
        args.out.write_text(json.dumps(value), encoding="utf-8")

        return 0

    if args.action == "build":
        started = time.perf_counter()
        coverage = build(root, args.jobs)
        dump(coverage, args.out)
        uncertain = sum(
            value.uncertain for value in coverage.modules.values()
        )
        print(
            f"coverage map: {len(coverage.modules)} modules "
            f"({uncertain} uncertain) in "
            f"{time.perf_counter() - started:.1f}s -> {args.out}"
        )

        return 0

    coverage = (
        load(args.map, root)
        if args.map is not None
        else build(root)
    )
    result = report(coverage, root, tuple(args.prefixes))
    print(render(result))

    if args.json is not None:
        args.json.write_text(
            json.dumps(result, indent=1),
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
