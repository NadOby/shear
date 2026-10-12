"""Explicit semantic oracle used by mutation subprocesses.

Mutation campaigns must run the same semantic tests against the unmodified
baseline and every mutant. Harness-integrity and survivor-catalog tests remain
mandatory in ordinary CI but are not mutation-kill oracles.
"""

from __future__ import annotations

import argparse
import os
import resource
import sys
import threading
import time
import unittest
from pathlib import Path

from tests import mutation_verdict
from tests.lanes import LANES, validate_partition


EXCLUDED_LANES = frozenset({"mutation"})

# The whole semantic suite runs once per mutant that survives and once as the
# baseline, on shared runners that vary in speed. A mutant that reaches its
# limit is reported as a timeout, never as a kill. The limit therefore scales
# with the baseline measured on the same runner: ``mutant_limit``. This fixed
# value is only the limit of a run that has no measured baseline.
TIMEOUT_SECONDS = 900.0

# A mutant may take this many times the baseline, but at least the floor. An
# honest run takes about one baseline; a mutant that needs three is a hang or
# a pathological slowdown, not a slow runner.
MUTANT_LIMIT_FACTOR = 3.0
MUTANT_LIMIT_FLOOR_SECONDS = 180.0

# A mutant can make code allocate without bound (one in ``matching.py`` grows
# by tens of megabytes a second); within the time limit that exhausts the
# runner and terminates the whole job. The honest suite peaks near 110 MB of
# resident memory, so a cap on the oracle process's address space turns such a
# mutant into an ordinary failing test within seconds.
MEMORY_LIMIT_BYTES = 3 * 1024**3


def limit_memory(limit: int = MEMORY_LIMIT_BYTES) -> None:
    """Cap this process's address space; never raise it above the hard limit."""

    _, hard = resource.getrlimit(resource.RLIMIT_AS)

    if hard != resource.RLIM_INFINITY:
        limit = min(limit, hard)

    resource.setrlimit(resource.RLIMIT_AS, (limit, hard))


def mutant_limit(baseline_seconds: float) -> float:
    """The time limit of one mutant run, from the baseline's duration."""

    if baseline_seconds < 0:
        raise ValueError("baseline duration cannot be negative")

    return max(
        MUTANT_LIMIT_FLOOR_SECONDS,
        MUTANT_LIMIT_FACTOR * baseline_seconds,
    )


def modules() -> tuple[str, ...]:
    """Return the exact ordered module set used as the mutation oracle."""

    validate_partition()

    return tuple(
        module
        for lane, lane_modules in LANES.items()
        if lane not in EXCLUDED_LANES
        for module in lane_modules
    )


def ordered_modules(first: tuple[str, ...] = ()) -> tuple[str, ...]:
    """The oracle modules with ``first`` moved to the front.

    Only the order changes: the result holds exactly the modules of
    ``modules()``, each once, so a run decides the same thing in any order.
    A name that is not an oracle module is an error, never ignored.
    """

    every = modules()
    unknown = [name for name in first if name not in every]

    if unknown:
        raise ValueError(
            "not oracle modules: " + ", ".join(sorted(set(unknown)))
        )

    if len(set(first)) != len(first):
        raise ValueError("duplicate module in the requested order")

    return tuple(first) + tuple(
        module for module in every if module not in first
    )


def suite(first: tuple[str, ...] = ()) -> unittest.TestSuite:
    """Build the explicit mutation semantic suite."""

    loader = unittest.defaultTestLoader
    result = unittest.TestSuite()

    for module in ordered_modules(first):
        try:
            result.addTests(
                loader.loadTestsFromName(
                    f"tests.{module}"
                )
            )
        except Exception as error:
            # A mutant can make a test module fail to import with something
            # other than ImportError, which the loader does not catch. That
            # is the suite noticing the change, so it becomes a failing test
            # and not a crash with no verdict.
            result.addTest(_import_failure(module, error))

    return result


def _import_failure(
    module: str,
    error: Exception,
) -> unittest.TestCase:
    def run_test(self: unittest.TestCase) -> None:
        raise error

    return type(
        "ImportFailure",
        (unittest.TestCase,),
        {"runTest": run_test, "__module__": f"tests.{module}"},
    )()


def command() -> list[str]:
    """Return the subprocess command for the semantic oracle."""

    return [
        sys.executable,
        "-m",
        "tests.mutation_oracle",
    ]


_current_test: str | None = None


class _Result(unittest.TextTestResult):
    """Remembers which test is running, for a run that must be cut short."""

    def startTest(self, test: unittest.TestCase) -> None:
        global _current_test

        _current_test = test.id()
        super().startTest(test)


def _cpu_seconds() -> float:
    """CPU time of this process and of the children it has waited for."""

    children = resource.getrusage(resource.RUSAGE_CHILDREN)

    return (
        time.process_time()
        + children.ru_utime
        + children.ru_stime
    )


def _verdict(result: unittest.TestResult) -> tuple[str, str | None]:
    """The oracle's result and the test that decided it.

    A first failure that is ``MemoryError`` came from the address-space cap,
    not from a check, and is reported as a resource kill.
    """

    problems = result.errors + result.failures

    if not problems:
        return ("passed" if result.wasSuccessful() else "failed"), None

    test, text = problems[0]
    last = text.strip().splitlines()[-1] if text.strip() else ""

    return (
        "resource" if last.startswith("MemoryError") else "failed",
        test.id(),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.mutation_oracle",
        description="Run the mutation semantic oracle.",
    )
    parser.add_argument(
        "--first",
        default="",
        help="comma-separated oracle modules to run before the others",
    )
    parser.add_argument(
        "--status",
        type=Path,
        help="write the verdict (killed, timeout, resource) to this file",
    )
    parser.add_argument(
        "--limit",
        type=float,
        help="stop and report a timeout after this many seconds",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args([] if argv is None else argv)
    first = tuple(
        name for name in args.first.split(",") if name
    )

    try:
        ordered_modules(first)
    except ValueError as exc:
        print(f"mutation oracle: {exc}", file=sys.stderr)
        return mutation_verdict.EXIT_USAGE

    started = time.perf_counter()

    def report(result: str, test: str | None) -> None:
        if args.status is not None:
            mutation_verdict.write_status(
                args.status,
                result,
                test,
                time.perf_counter() - started,
                _cpu_seconds(),
            )

    def expire() -> None:
        print(
            f"mutation oracle: time limit of {args.limit}s reached "
            f"while running {_current_test or 'test loading'}",
            file=sys.stderr,
            flush=True,
        )
        report("timeout", _current_test)
        os._exit(mutation_verdict.EXIT_TIMEOUT)

    limit_memory()

    # Started before the tests are loaded: a mutant can hang while a test
    # module is being imported.
    if args.limit is not None:
        watchdog = threading.Timer(args.limit, expire)
        watchdog.daemon = True
        watchdog.start()

    tests = suite(first) if first else suite()

    result = unittest.TextTestRunner(
        verbosity=0,
        failfast=True,
        resultclass=_Result,
    ).run(tests)
    outcome, test = _verdict(result)

    report(outcome, test)

    return (
        mutation_verdict.EXIT_PASSED
        if outcome == "passed"
        else mutation_verdict.EXIT_FAILED
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
