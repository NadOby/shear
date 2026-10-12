"""How a mutant run ends: kill, timeout, resource kill, abnormal exit, survivor.

These run the real oracle protocol (``tests/mutation_oracle.py`` with
``--status``, ``--limit`` and ``--first``) over a tiny fixture suite in real
subprocesses, and the campaign code that reads the verdicts. The ordinary
semantic suite is never involved.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import mutation
from tests import mutation_coverage
from tests import mutation_oracle
from tests import mutation_reporting
from tests import mutation_verdict


CALC = """\
_unused = 0


def add(a, b):
    return a + b


def count_down(n):
    while n > 0:
        n = n - 1
    return n


def reserve(n):
    if n > 3:
        raise MemoryError("too big")
    return n
"""

# The runner stands in for ``python -m tests.mutation_oracle`` over three
# fixture tests, so a mutant of calc.py is judged by the real protocol.
RUNNER = """\
import os
import sys
import unittest

sys.path.insert(0, {root!r})
sys.path.insert(0, os.getcwd())

from tests import mutation_oracle as oracle
import calc


class FixtureTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(calc.add(2, 3), 5)

    def test_count_down(self):
        self.assertEqual(calc.count_down(3), 0)

    def test_reserve(self):
        self.assertEqual(calc.reserve(1), 1)

    def test_sub_tests(self):
        for value in (1, 2):
            with self.subTest(value=value):
                self.assertEqual(calc.add(value, 0), value)


oracle.suite = lambda *a: unittest.defaultTestLoader.loadTestsFromTestCase(
    FixtureTests
)
oracle.TEST_BUDGET_FLOOR_SECONDS = float(os.environ.get("FLOOR", "30"))
raise SystemExit(oracle.main(sys.argv[1:]))
"""


# A mutant can break a test module at import time with something other than
# ImportError, or hang while it is imported; the loader here fakes both for
# the module named ``boom`` or ``hang``.
LOADER_RUNNER = """\
import os
import sys
import time
import unittest

sys.path.insert(0, {root!r})

from tests import mutation_oracle as oracle

real = unittest.defaultTestLoader.loadTestsFromName


def load(name, *args):
    if name == "tests.boom":
        raise {error}
    if name == "tests.hang":
        time.sleep(60)
    return unittest.TestSuite()


unittest.defaultTestLoader.loadTestsFromName = load
oracle.modules = lambda: tuple(os.environ["MODULES"].split(","))
raise SystemExit(oracle.main(sys.argv[1:]))
"""


# The address-space cap can be hit where unittest does not catch it: the
# runner itself raises MemoryError.
ESCAPING_RUNNER = """\
import sys
import unittest

sys.path.insert(0, {root!r})

from tests import mutation_oracle as oracle


def run(self, test):
    raise MemoryError()


unittest.TextTestRunner.run = run
oracle.suite = lambda *a: unittest.TestSuite()
raise SystemExit(oracle.main(sys.argv[1:]))
"""


class FixtureCase(unittest.TestCase):
    """A fixture repository whose oracle is the runner above."""

    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)
        self.root = self.scratch / "repo"
        self.root.mkdir()
        (self.root / "calc.py").write_text(CALC)
        (self.root / "tests").mkdir()
        (self.root / "tests" / "mutation.py").write_text("fixture engine\n")
        self.runner = self.scratch / "runner.py"
        self.runner.write_text(RUNNER.format(root=str(mutation.ROOT)))
        self.command = [sys.executable, str(self.runner)]

    def site(self, kind: str, text: str) -> mutation.Mutant:
        matches = [
            mutant
            for mutant in mutation.site_descriptions(CALC, "calc.py")
            if mutant.kind == kind and mutant.text == text
        ]

        self.assertEqual(len(matches), 1, f"{kind} site on {text!r}")

        return matches[0]

    @property
    def killed_site(self) -> mutation.Mutant:
        return self.site("arithmetic", "return a + b")

    @property
    def hanging_site(self) -> mutation.Mutant:
        return self.site("arithmetic", "n = n - 1")

    @property
    def memory_site(self) -> mutation.Mutant:
        return self.site("compare", "if n > 3:")

    @property
    def surviving_site(self) -> mutation.Mutant:
        return self.site("constant", "_unused = 0")

    def run_runner(self, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            self.command + list(arguments),
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=60,
        )


class OracleProtocolTests(FixtureCase):
    def test_a_passing_run_reports_passed(self) -> None:
        status = self.scratch / "status.json"
        done = self.run_runner("--status", str(status), "--limit", "30")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(
            mutation_verdict.read_status(status).result,
            "passed",
        )

    def test_a_passing_run_records_how_long_each_test_took(self) -> None:
        status = self.scratch / "status.json"
        self.run_runner("--status", str(status))

        tests = mutation_verdict.read_status(status).tests

        self.assertEqual(len(tests), 4)
        self.assertTrue(any(name.endswith("test_add") for name in tests))
        self.assertTrue(all(seconds >= 0 for seconds in tests.values()))

    def test_a_test_far_over_its_budget_is_a_timeout_at_once(self) -> None:
        # The whole-run limit is a minute; the hung test is cut off after
        # its own budget (the floor, one second here).
        mutated, _ = mutation.mutate(
            CALC,
            "calc.py",
            self.hanging_site.index,
        )
        (self.root / "calc.py").write_text(mutated)
        times = self.scratch / "times.json"
        times.write_text(json.dumps({}))
        status = self.scratch / "status.json"

        started = time.perf_counter()
        done = subprocess.run(
            self.command
            + ["--status", str(status), "--limit", "60", "--times", str(times)],
            cwd=self.root,
            env={**os.environ, "FLOOR": "1"},
            capture_output=True,
            text=True,
            timeout=60,
        )
        elapsed = time.perf_counter() - started
        verdict = mutation_verdict.read_status(status)

        self.assertEqual(done.returncode, mutation_verdict.EXIT_TIMEOUT)
        self.assertEqual(verdict.result, "timeout")
        self.assertTrue(verdict.test.endswith("test_count_down"), verdict.test)
        self.assertLess(elapsed, 30)
        self.assertIn("test budget", done.stderr)

    def test_a_budget_follows_the_tests_own_honest_time(self) -> None:
        self.assertEqual(mutation_oracle.test_budget(0.1), 30.0)
        self.assertEqual(mutation_oracle.test_budget(20.0), 200.0)

    def test_an_unreadable_times_file_is_a_usage_error(self) -> None:
        done = self.run_runner("--times", str(self.scratch / "missing.json"))

        self.assertEqual(done.returncode, mutation_verdict.EXIT_USAGE)

    def test_a_failing_test_reports_failed_and_names_the_test(self) -> None:
        mutated, _ = mutation.mutate(
            CALC,
            "calc.py",
            self.killed_site.index,
        )
        (self.root / "calc.py").write_text(mutated)
        status = self.scratch / "status.json"

        done = self.run_runner("--status", str(status))
        verdict = mutation_verdict.read_status(status)

        self.assertEqual(done.returncode, mutation_verdict.EXIT_FAILED)
        self.assertEqual(verdict.result, "failed")
        self.assertTrue(verdict.test.endswith("test_add"), verdict.test)

    def test_a_failing_subtest_is_a_failure_of_its_test(self) -> None:
        (self.root / "calc.py").write_text(
            CALC.replace("return a + b", "return 0 if b == 0 else a + b")
        )
        status = self.scratch / "status.json"

        done = self.run_runner("--status", str(status))

        self.assertEqual(done.returncode, mutation_verdict.EXIT_FAILED)
        self.assertEqual(
            mutation_verdict.read_status(status).result,
            "failed",
        )

    def test_memory_exhaustion_is_reported_as_a_resource_kill(self) -> None:
        mutated, _ = mutation.mutate(
            CALC,
            "calc.py",
            self.memory_site.index,
        )
        (self.root / "calc.py").write_text(mutated)
        status = self.scratch / "status.json"

        done = self.run_runner("--status", str(status))
        verdict = mutation_verdict.read_status(status)

        self.assertEqual(done.returncode, mutation_verdict.EXIT_FAILED)
        self.assertEqual(verdict.result, "resource")
        self.assertTrue(verdict.test.endswith("test_reserve"), verdict.test)

    def test_a_hang_reports_a_timeout_where_it_happened(self) -> None:
        mutated, _ = mutation.mutate(
            CALC,
            "calc.py",
            self.hanging_site.index,
        )
        (self.root / "calc.py").write_text(mutated)
        status = self.scratch / "status.json"

        done = self.run_runner("--status", str(status), "--limit", "1")
        verdict = mutation_verdict.read_status(status)

        self.assertEqual(done.returncode, mutation_verdict.EXIT_TIMEOUT)
        self.assertEqual(verdict.result, "timeout")
        self.assertTrue(verdict.test.endswith("test_count_down"), verdict.test)
        self.assertIn("time limit", done.stderr)

    def test_an_unknown_module_in_the_order_is_refused(self) -> None:
        status = self.scratch / "status.json"

        done = self.run_runner(
            "--status",
            str(status),
            "--first",
            "test_no_such_module",
        )

        self.assertEqual(done.returncode, mutation_verdict.EXIT_USAGE)
        self.assertFalse(status.exists())
        self.assertIn("test_no_such_module", done.stderr)


class OracleOrderTests(unittest.TestCase):
    def test_the_default_order_is_the_oracle_modules(self) -> None:
        self.assertEqual(
            mutation_oracle.ordered_modules(),
            mutation_oracle.modules(),
        )

    def test_first_modules_move_to_the_front_and_nothing_else_changes(
        self,
    ) -> None:
        every = mutation_oracle.modules()
        chosen = (every[-1], every[3])
        ordered = mutation_oracle.ordered_modules(chosen)

        self.assertEqual(ordered[:2], chosen)
        self.assertEqual(sorted(ordered), sorted(every))
        self.assertEqual(len(ordered), len(set(ordered)))
        self.assertEqual(
            ordered[2:],
            tuple(module for module in every if module not in chosen),
        )

    def test_an_unknown_or_repeated_module_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            mutation_oracle.ordered_modules(("test_no_such_module",))

        first = mutation_oracle.modules()[0]

        with self.assertRaises(ValueError):
            mutation_oracle.ordered_modules((first, first))

    def test_the_suite_follows_the_requested_order(self) -> None:
        last = mutation_oracle.modules()[-1]
        loaded: list[str] = []

        def load(name: str) -> unittest.TestSuite:
            loaded.append(name)

            return unittest.TestSuite()

        with patch.object(
            unittest.defaultTestLoader,
            "loadTestsFromName",
            side_effect=load,
        ):
            mutation_oracle.suite((last,))

        self.assertEqual(loaded[0], f"tests.{last}")
        self.assertEqual(
            sorted(loaded),
            sorted(f"tests.{m}" for m in mutation_oracle.modules()),
        )

    def test_the_mutant_limit_scales_with_the_baseline(self) -> None:
        self.assertEqual(mutation_oracle.mutant_limit(136.0), 408.0)
        self.assertEqual(
            mutation_oracle.mutant_limit(1.0),
            mutation_oracle.MUTANT_LIMIT_FLOOR_SECONDS,
        )

        with self.assertRaises(ValueError):
            mutation_oracle.mutant_limit(-1.0)


class ExecutionTests(FixtureCase):
    def execute(
        self,
        mutant: mutation.Mutant,
        limit: float = 2.0,
    ) -> mutation_reporting.Execution:
        _, execution, _ = mutation_reporting.execute(
            self.root,
            mutant,
            self.command,
            mutation_reporting.RunOptions(limit=limit),
        )

        return execution

    def test_each_way_a_run_can_end_has_its_own_outcome(self) -> None:
        self.assertEqual(
            self.execute(self.killed_site).outcome,
            mutation_verdict.KILLED,
        )
        self.assertEqual(
            self.execute(self.memory_site).outcome,
            mutation_verdict.RESOURCE_KILL,
        )
        self.assertEqual(
            self.execute(self.surviving_site).outcome,
            mutation_verdict.SURVIVED,
        )

    def test_a_hung_mutant_is_a_timeout_not_a_kill(self) -> None:
        execution = self.execute(self.hanging_site, limit=1.0)

        self.assertEqual(execution.outcome, mutation_verdict.TIMEOUT)
        self.assertTrue(
            execution.killed_by.endswith("test_count_down"),
            execution.killed_by,
        )

    def test_a_run_that_dies_without_a_verdict_is_abnormal(self) -> None:
        _, execution, _ = mutation_reporting.execute(
            self.root,
            self.killed_site,
            [sys.executable, "-c", "raise SystemExit(5)"],
            mutation_reporting.RunOptions(limit=60.0),
        )

        self.assertEqual(execution.outcome, mutation_verdict.ABNORMAL_EXIT)

    def test_the_engine_timeout_backstops_an_oracle_that_cannot_report(
        self,
    ) -> None:
        mutant = self.killed_site

        with patch.object(
            mutation_reporting.mutation,
            "killed",
            return_value=(mutant, True),
        ) as killed:
            _, execution, _ = mutation_reporting.execute(
                self.root,
                mutant,
                ["fixture-oracle"],
                mutation_reporting.RunOptions(limit=0.0),
            )

        self.assertEqual(execution.outcome, mutation_verdict.TIMEOUT)
        self.assertEqual(
            killed.call_args.kwargs["timeout"],
            mutation_verdict.BACKSTOP_GRACE_SECONDS,
        )

    def test_the_run_carries_its_limit_and_status_path(self) -> None:
        mutant = self.killed_site

        with patch.object(
            mutation_reporting.mutation,
            "killed",
            return_value=(mutant, False),
        ) as killed:
            mutation_reporting.execute(
                self.root,
                mutant,
                ["fixture-oracle"],
                mutation_reporting.RunOptions(limit=408.0),
            )

        command = killed.call_args.args[3]

        self.assertEqual(command[0], "fixture-oracle")
        self.assertEqual(
            command[command.index("--limit") + 1],
            "408.0",
        )
        self.assertIn("--status", command)
        self.assertNotIn("--first", command)


class CoverageOrderingTests(FixtureCase):
    def setUp(self) -> None:
        super().setUp()
        self.mutant = self.killed_site

        def module(lines: set[int], opaque: bool = False):
            return mutation_coverage.ModuleCoverage(
                complete=True,
                opaque=opaque,
                seconds=1.0,
                lines={"calc.py": frozenset(lines)},
            )

        self.coverage = mutation_coverage.CoverageMap(
            fingerprint="fixture",
            order=("test_a", "test_b", "test_c"),
            modules={
                "test_a": module(set()),
                "test_b": module({self.mutant.line}),
                "test_c": module(set(), opaque=True),
            },
        )

    def execute_killed_by(
        self,
        test: str,
    ) -> tuple[list[str], mutation_reporting.Execution]:
        captured: list[str] = []

        def killed(root, target, index, command, timeout):
            captured.extend(command)
            path = Path(command[command.index("--status") + 1])
            mutation_verdict.write_status(path, "failed", test, 1.0, 1.0)

            return self.mutant, True

        with patch.object(
            mutation_reporting.mutation,
            "killed",
            side_effect=killed,
        ):
            _, execution, _ = mutation_reporting.execute(
                self.root,
                self.mutant,
                ["fixture-oracle"],
                mutation_reporting.RunOptions(
                    limit=60.0,
                    coverage=self.coverage,
                ),
            )

        return captured, execution

    def test_modules_that_execute_the_line_run_first(self) -> None:
        command, execution = self.execute_killed_by(
            "tests.test_b.T.test_x"
        )

        self.assertEqual(
            command[command.index("--first") + 1],
            "test_b,test_c",
        )
        self.assertEqual(execution.stage, "covering")
        self.assertEqual(execution.coverage, mutation_coverage.COVERED)

    def test_a_kill_by_a_module_outside_the_first_set_is_marked_rest(
        self,
    ) -> None:
        _, execution = self.execute_killed_by("tests.test_a.T.test_x")

        self.assertEqual(execution.stage, "rest")


class CampaignOutcomeTests(FixtureCase):
    def campaign(
        self,
        work: tuple[mutation.Mutant, ...],
        classifications: dict | None = None,
        **options: object,
    ) -> tuple[mutation_reporting.CampaignResult, list[dict], str]:
        report = self.scratch / "report.jsonl"
        human = io.StringIO()
        result = mutation_reporting.run_campaign(
            self.root,
            work,
            self.command,
            classifications or {},
            report,
            {
                "count": len(work),
                "seed": 1,
                "batch": 0,
                "shards": 1,
                "shard": 0,
            },
            workers=2,
            stream=human,
            options=mutation_reporting.RunOptions(
                limit=options.pop("limit", 2.0),  # type: ignore[arg-type]
                **options,  # type: ignore[arg-type]
            ),
        )
        events = [
            json.loads(line)
            for line in report.read_text().splitlines()
        ]

        return result, events, human.getvalue()

    def test_a_campaign_reports_each_ending_separately(self) -> None:
        work = (
            self.killed_site,
            self.hanging_site,
            self.memory_site,
            self.surviving_site,
        )
        classified = {
            self.surviving_site.key: ("equivalent", "fixture"),
        }

        result, events, text = self.campaign(work, classified, limit=1.5)
        outcomes = {
            tuple(event["key"]): event["outcome"]
            for event in events
            if event["event"] == "mutant_outcome"
        }
        complete = events[-1]

        self.assertEqual(
            outcomes,
            {
                self.killed_site.key: "killed",
                self.hanging_site.key: "timeout",
                self.memory_site.key: "resource_kill",
                self.surviving_site.key: "classified_survivor",
            },
        )
        self.assertEqual(result.killed, 1)
        self.assertEqual(
            [mutant.key for mutant in result.timeouts],
            [self.hanging_site.key],
        )
        self.assertEqual(len(result.resource_kills), 1)
        self.assertEqual(result.abnormal_exits, ())
        self.assertEqual(complete["killed"], 1)
        self.assertEqual(complete["timeouts"], 1)
        self.assertEqual(complete["resource_kills"], 1)
        self.assertEqual(complete["abnormal_exits"], 0)
        self.assertGreater(complete["cpu_seconds"], 0.0)
        self.assertIn("NOT KILLED timeout", text)
        self.assertIn("test_count_down", text)
        self.assertNotIn("SURVIVOR timeout", text)

    def test_a_timeout_is_never_counted_as_a_kill(self) -> None:
        result, events, _ = self.campaign((self.hanging_site,), limit=1.0)

        self.assertEqual(result.killed, 0)
        self.assertEqual(events[-1]["killed"], 0)
        self.assertEqual(events[-1]["timeouts"], 1)

    def test_a_run_without_a_verdict_is_reported_as_abnormal(self) -> None:
        report = self.scratch / "report.jsonl"
        result = mutation_reporting.run_campaign(
            self.root,
            (self.killed_site,),
            [sys.executable, "-c", "raise SystemExit(5)"],
            {},
            report,
            {
                "count": 1,
                "seed": 1,
                "batch": 0,
                "shards": 1,
                "shard": 0,
            },
            workers=1,
            stream=io.StringIO(),
            options=mutation_reporting.RunOptions(limit=60.0),
        )

        self.assertEqual(result.killed, 0)
        self.assertEqual(len(result.abnormal_exits), 1)

    def test_reviewed_survivors_are_not_run_unless_revalidating(
        self,
    ) -> None:
        survivor = self.surviving_site
        work = (self.killed_site, survivor)
        classified = {survivor.key: ("equivalent", "fixture")}
        executed: list[mutation.MutationKey] = []

        def execute(root, selected, command, options):
            executed.append(selected.key)

            return (
                selected,
                mutation_reporting.Execution(mutation_verdict.KILLED),
                0.1,
            )

        with patch(
            "tests.mutation_reporting._execute_one",
            side_effect=execute,
        ):
            result, events, text = self.campaign(
                work,
                classified,
                rerun_classified=False,
            )

        outcome = next(
            event
            for event in events
            if event["event"] == "mutant_outcome"
            and tuple(event["key"]) == survivor.key
        )

        self.assertEqual(executed, [self.killed_site.key])
        self.assertEqual(outcome["outcome"], "classified_survivor")
        self.assertIs(outcome["executed"], False)
        self.assertEqual(outcome["classification"], "equivalent")
        self.assertEqual(len(result.classified_survivors), 1)
        self.assertEqual(events[-1]["not_run"], 1)
        self.assertEqual(events[-1]["completed"], 2)
        self.assertEqual(events[0]["run_options"]["rerun_classified"], False)
        self.assertIn("(pinned, not run)", text)

        executed.clear()

        with patch(
            "tests.mutation_reporting._execute_one",
            side_effect=execute,
        ):
            self.campaign(work, classified, rerun_classified=True)

        self.assertEqual(
            sorted(executed),
            sorted([self.killed_site.key, survivor.key]),
        )

    def test_a_pinned_survivor_does_not_hide_an_unclassified_one(
        self,
    ) -> None:
        # Only keys with a reviewed classification are skipped.
        work = (self.surviving_site,)

        result, events, _ = self.campaign(
            work,
            {},
            rerun_classified=False,
        )

        self.assertEqual(len(result.unclassified_survivors), 1)
        self.assertEqual(events[-1]["not_run"], 0)

    def test_the_baseline_has_no_time_limit_and_is_timed(self) -> None:
        completed = subprocess.CompletedProcess([], 0, b"", b"")

        with patch.object(
            mutation_reporting.mutation,
            "baseline",
            return_value=completed,
        ) as baseline:
            done, seconds, times = mutation_reporting.run_baseline(
                self.root,
                ["fixture-oracle"],
            )

        self.assertIs(done, completed)
        self.assertGreaterEqual(seconds, 0.0)
        self.assertEqual(times, {})
        (root, command), options = baseline.call_args
        self.assertEqual(root, self.root)
        self.assertEqual(command[:1], ["fixture-oracle"])
        self.assertEqual(command[1], "--status")
        self.assertIsNone(options["timeout"])


class ImportFailureTests(FixtureCase):
    def run_loader(
        self,
        *arguments: str,
        modules: str = "fine,boom",
        error: str = "TypeError('broken at import')",
    ) -> tuple[subprocess.CompletedProcess, mutation_verdict.Status | None]:
        runner = self.scratch / "loader_runner.py"
        runner.write_text(
            LOADER_RUNNER.format(root=str(mutation.ROOT), error=error)
        )
        status = self.scratch / "status.json"
        done = subprocess.run(
            [sys.executable, str(runner), "--status", str(status)]
            + list(arguments),
            cwd=self.root,
            env={**os.environ, "MODULES": modules},
            capture_output=True,
            text=True,
            timeout=60,
        )

        return done, mutation_verdict.read_status(status)

    def test_a_module_that_fails_to_import_is_a_failed_test(self) -> None:
        # Not a crash without a verdict: the suite noticed the change.
        done, status = self.run_loader()

        self.assertEqual(done.returncode, mutation_verdict.EXIT_FAILED)
        self.assertIsNotNone(status, done.stderr)
        self.assertEqual(status.result, "failed")
        self.assertEqual(status.module, "boom")

    def test_memory_exhaustion_while_importing_is_a_resource_kill(
        self,
    ) -> None:
        done, status = self.run_loader(error="MemoryError()")

        self.assertIsNotNone(status, done.stderr)
        self.assertEqual(status.result, "resource")

    def test_a_hang_while_importing_is_reported_as_a_timeout(self) -> None:
        done, status = self.run_loader("--limit", "1", modules="fine,hang")

        self.assertEqual(done.returncode, mutation_verdict.EXIT_TIMEOUT)
        self.assertIsNotNone(status, done.stderr)
        self.assertEqual(status.result, "timeout")


    def test_memory_exhaustion_outside_a_test_is_a_resource_kill(
        self,
    ) -> None:
        # It used to escape with no verdict and show up as an abnormal exit.
        runner = self.scratch / "escaping_runner.py"
        runner.write_text(ESCAPING_RUNNER.format(root=str(mutation.ROOT)))
        status = self.scratch / "status.json"
        done = subprocess.run(
            [sys.executable, str(runner), "--status", str(status)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(done.returncode, mutation_verdict.EXIT_FAILED)
        verdict = mutation_verdict.read_status(status)
        self.assertIsNotNone(verdict, done.stderr)
        self.assertEqual(verdict.result, "resource")


if __name__ == "__main__":
    unittest.main()
