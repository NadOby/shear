"""Explicit semantic oracle used by mutation subprocesses.

Mutation campaigns must run the same semantic tests against the unmodified
baseline and every mutant. Harness-integrity and survivor-catalog tests remain
mandatory in ordinary CI but are not mutation-kill oracles.
"""

from __future__ import annotations

import resource
import sys
import unittest

from tests.lanes import LANES, validate_partition


EXCLUDED_LANES = frozenset({"mutation"})

# The whole semantic suite runs once per mutant that survives and once as the
# baseline, on shared runners that vary in speed. The limit only has to stop
# a mutant that never terminates; a mutant that hits it counts as killed, so
# it must stay well above the slowest honest run.
TIMEOUT_SECONDS = 900.0

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


def modules() -> tuple[str, ...]:
    """Return the exact ordered module set used as the mutation oracle."""

    validate_partition()

    return tuple(
        module
        for lane, lane_modules in LANES.items()
        if lane not in EXCLUDED_LANES
        for module in lane_modules
    )


def suite() -> unittest.TestSuite:
    """Build the explicit mutation semantic suite."""

    loader = unittest.defaultTestLoader
    result = unittest.TestSuite()

    for module in modules():
        result.addTests(
            loader.loadTestsFromName(
                f"tests.{module}"
            )
        )

    return result


def command() -> list[str]:
    """Return the subprocess command for the semantic oracle."""

    return [
        sys.executable,
        "-m",
        "tests.mutation_oracle",
    ]


def main() -> int:
    limit_memory()
    result = unittest.TextTestRunner(
        verbosity=0,
        failfast=True,
    ).run(suite())

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
