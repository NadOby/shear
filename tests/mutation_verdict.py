"""What one mutation oracle run reports, and how a campaign reads it.

The oracle (``tests/mutation_oracle.py``) writes a small status file when it
is given ``--status``. A campaign reads it back to tell apart the ways a
mutant run can end, which the process exit status alone cannot:

- ``killed``: a test failed or errored, so the suite noticed the change;
- ``timeout``: the run reached its time limit, so nothing was noticed in time;
- ``resource_kill``: the first failure was ``MemoryError`` from the oracle's
  address-space cap, so the mutant exhausted a resource rather than failed a
  check;
- ``abnormal_exit``: the oracle process ended without a usable verdict;
- ``survived``: every test passed.

Only a failing test is evidence that the suite catches a mutant. A timeout,
a resource kill or an abnormal exit is reported as such and never counted as a
kill. A timeout or a resource kill does not fail a campaign; an unclassified
survivor or an abnormal exit does. The engine (``tests/mutation.py``) is deliberately not involved, so its
version pin and the reviewed survivor classifications stay valid.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


KILLED = "killed"
TIMEOUT = "timeout"
RESOURCE_KILL = "resource_kill"
ABNORMAL_EXIT = "abnormal_exit"
SURVIVED = "survived"

# Outcomes of a mutant run that ended without a failing test.
NOT_A_KILL = frozenset({TIMEOUT, RESOURCE_KILL, ABNORMAL_EXIT})

# The oracle's exit status for each verdict. Only 0 and 1 existed before.
EXIT_PASSED = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_TIMEOUT = 3

STATUS_VERSION = 1
RESULTS = frozenset({"passed", "failed", "resource", "timeout"})

# The engine's own timeout only has to outlast the oracle's watchdog, which
# reports where a hang happened; it is the fallback for a run that cannot
# report (a hang inside a C call that never releases the interpreter lock).
BACKSTOP_GRACE_SECONDS = 30.0


@dataclass(frozen=True)
class Status:
    """The verdict an oracle run wrote."""

    result: str
    test: str | None
    seconds: float
    cpu_seconds: float
    # Seconds each test took; only a passing run (the baseline) records them.
    tests: dict[str, float] = field(default_factory=dict)

    @property
    def module(self) -> str | None:
        return module_of(self.test)


def module_of(test_id: str | None) -> str | None:
    """The ``tests`` module a test id belongs to, or ``None``."""

    if test_id is None:
        return None

    parts = test_id.split(".")

    if len(parts) >= 2 and parts[0] == "tests":
        return parts[1]

    return None


def write_status(
    path: Path,
    result: str,
    test: str | None,
    seconds: float,
    cpu_seconds: float,
    tests: dict[str, float] | None = None,
) -> None:
    """Write a status file atomically, so a reader never sees half of one."""

    if result not in RESULTS:
        raise ValueError(f"unknown oracle result {result!r}")

    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps({
            "version": STATUS_VERSION,
            "result": result,
            "test": test,
            "seconds": seconds,
            "cpu_seconds": cpu_seconds,
            **({"tests": tests} if tests else {}),
        }),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def read_status(path: Path) -> Status | None:
    """The verdict in a status file, or ``None`` if there is no valid one.

    A missing, unreadable or malformed file is "no verdict", never a guess.
    """

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    if (
        not isinstance(value, dict)
        or value.get("version") != STATUS_VERSION
        or value.get("result") not in RESULTS
        or not isinstance(value.get("seconds"), (int, float))
        or not isinstance(value.get("cpu_seconds"), (int, float))
        or isinstance(value.get("seconds"), bool)
        or isinstance(value.get("cpu_seconds"), bool)
    ):
        return None

    test = value.get("test")

    if test is not None and not isinstance(test, str):
        return None

    tests = value.get("tests", {})

    if not isinstance(tests, dict) or not all(
        isinstance(name, str)
        and isinstance(seconds, (int, float))
        and not isinstance(seconds, bool)
        for name, seconds in tests.items()
    ):
        return None

    return Status(
        result=value["result"],
        test=test,
        seconds=float(value["seconds"]),
        cpu_seconds=float(value["cpu_seconds"]),
        tests={name: float(seconds) for name, seconds in tests.items()},
    )


def classify(
    dead: bool,
    elapsed: float,
    limit: float,
    status: Status | None,
) -> str:
    """The outcome of one mutant run.

    ``dead`` is the engine's answer (the run failed or timed out), ``elapsed``
    the run's wall time and ``limit`` its time limit. A verdict that
    contradicts the exit status is never trusted as a kill.
    """

    if status is not None:
        agrees = {
            "passed": not dead,
            "failed": dead,
            "resource": dead,
            "timeout": dead,
        }[status.result]

        if not agrees:
            return ABNORMAL_EXIT

        return {
            "passed": SURVIVED,
            "failed": KILLED,
            "resource": RESOURCE_KILL,
            "timeout": TIMEOUT,
        }[status.result]

    if not dead:
        return SURVIVED

    if elapsed >= limit:
        return TIMEOUT

    return ABNORMAL_EXIT
