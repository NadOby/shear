"""The verdict protocol between the mutation oracle and a campaign."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests import mutation_verdict as verdict


def status(result: str, test: str | None = None) -> verdict.Status:
    return verdict.Status(result, test, 1.0, 1.0)


class ClassifyTests(unittest.TestCase):
    def test_a_failing_test_is_a_kill(self) -> None:
        self.assertEqual(
            verdict.classify(True, 5.0, 100.0, status("failed")),
            verdict.KILLED,
        )

    def test_a_timeout_verdict_is_not_a_kill(self) -> None:
        # The oracle's own watchdog reports a timeout well before the limit
        # the engine would enforce; the verdict, not elapsed time, decides.
        self.assertEqual(
            verdict.classify(True, 1.0, 100.0, status("timeout")),
            verdict.TIMEOUT,
        )

    def test_memory_exhaustion_is_not_a_kill(self) -> None:
        self.assertEqual(
            verdict.classify(True, 5.0, 100.0, status("resource")),
            verdict.RESOURCE_KILL,
        )

    def test_a_passing_run_is_a_survivor(self) -> None:
        self.assertEqual(
            verdict.classify(False, 5.0, 100.0, status("passed")),
            verdict.SURVIVED,
        )

    def test_a_verdict_that_contradicts_the_exit_is_never_a_kill(
        self,
    ) -> None:
        for result, dead in (
            ("passed", True),
            ("failed", False),
            ("resource", False),
            ("timeout", False),
        ):
            with self.subTest(result=result, dead=dead):
                self.assertEqual(
                    verdict.classify(dead, 5.0, 100.0, status(result)),
                    verdict.ABNORMAL_EXIT,
                )

    def test_without_a_verdict_a_dead_run_at_the_limit_is_a_timeout(
        self,
    ) -> None:
        self.assertEqual(
            verdict.classify(True, 130.0, 100.0, None),
            verdict.TIMEOUT,
        )

    def test_without_a_verdict_an_early_death_is_abnormal(self) -> None:
        self.assertEqual(
            verdict.classify(True, 5.0, 100.0, None),
            verdict.ABNORMAL_EXIT,
        )

    def test_without_a_verdict_a_clean_exit_is_still_a_survivor(
        self,
    ) -> None:
        # Never hide a survivor: it is reported, and an unclassified one
        # fails the campaign.
        self.assertEqual(
            verdict.classify(False, 5.0, 100.0, None),
            verdict.SURVIVED,
        )

    def test_only_a_failing_test_counts_as_a_kill(self) -> None:
        self.assertEqual(
            verdict.NOT_A_KILL,
            {
                verdict.TIMEOUT,
                verdict.RESOURCE_KILL,
                verdict.ABNORMAL_EXIT,
            },
        )


class StatusFileTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.path = Path(scratch.name) / "status.json"

    def test_a_written_status_reads_back(self) -> None:
        verdict.write_status(
            self.path,
            "failed",
            "tests.test_lang.LangTests.test_x",
            1.5,
            1.25,
        )

        self.assertEqual(
            verdict.read_status(self.path),
            verdict.Status(
                "failed",
                "tests.test_lang.LangTests.test_x",
                1.5,
                1.25,
            ),
        )
        self.assertEqual(
            verdict.read_status(self.path).module,
            "test_lang",
        )

    def test_writing_leaves_no_partial_file_behind(self) -> None:
        verdict.write_status(self.path, "passed", None, 1.0, 1.0)

        self.assertEqual(
            sorted(entry.name for entry in self.path.parent.iterdir()),
            ["status.json"],
        )

    def test_an_unknown_result_is_refused_on_write(self) -> None:
        with self.assertRaises(ValueError):
            verdict.write_status(self.path, "killed", None, 1.0, 1.0)

    def test_a_missing_file_is_no_verdict(self) -> None:
        self.assertIsNone(verdict.read_status(self.path))

    def test_malformed_files_are_no_verdict(self) -> None:
        good = {
            "version": 1,
            "result": "failed",
            "test": "tests.test_x.T.test_y",
            "seconds": 1.0,
            "cpu_seconds": 1.0,
        }
        bad = {
            "not json": None,
            "wrong version": {**good, "version": 2},
            "unknown result": {**good, "result": "killed"},
            "boolean seconds": {**good, "seconds": True},
            "missing cpu": {
                key: value
                for key, value in good.items()
                if key != "cpu_seconds"
            },
            "numeric test": {**good, "test": 7},
            "not an object": [good],
        }

        for name, value in bad.items():
            with self.subTest(name):
                self.path.write_text(
                    "{broken"
                    if name == "not json"
                    else json.dumps(value)
                )
                self.assertIsNone(verdict.read_status(self.path))

        self.path.write_text(json.dumps(good))
        self.assertIsNotNone(verdict.read_status(self.path))

    def test_the_module_of_a_test_id(self) -> None:
        self.assertEqual(
            verdict.module_of("tests.test_vm.VmTests.test_a"),
            "test_vm",
        )
        self.assertIsNone(
            verdict.module_of("unittest.loader._FailedTest.test_x"),
        )
        self.assertIsNone(verdict.module_of(None))


if __name__ == "__main__":
    unittest.main()
