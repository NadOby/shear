"""Regression tests for mutation campaign reporting and report-driven replay."""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import mutation
from tests import mutation_campaign
from tests import mutation_oracle
from tests import mutation_reporting


class MutationReportingTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(
            temporary.cleanup
        )
        self.root = Path(
            temporary.name
        )

        (self.root / "first.py").write_text(
            "first = 1 + 2\n"
            "second = 3 + 4\n"
        )

        engine = (
            self.root
            / "tests"
            / "mutation.py"
        )
        engine.parent.mkdir()
        engine.write_text(
            "fixture mutation engine\n"
        )
        self.engine_blob = mutation.git_blob_id(
            engine.read_bytes()
        )

    def source_blob(self) -> str:
        return mutation.git_blob_id(
            (self.root / "first.py").read_bytes()
        )

    def mutants(
        self,
    ) -> tuple[mutation.Mutant, ...]:
        return tuple(
            mutation.site_descriptions(
                (
                    self.root
                    / "first.py"
                ).read_text(),
                "first.py",
            )
        )

    def write_report(
        self,
        path: Path,
        outcomes: tuple[
            tuple[
                mutation.Mutant,
                str,
            ],
            ...,
        ],
    ) -> None:
        source_blob = self.source_blob()

        events: list[
            dict[str, object]
        ] = [
            {
                "event": "campaign_start",
                "engine_blob": self.engine_blob,
                "target_source_blobs": {
                    "first.py": source_blob,
                },
                "inputs": {
                    "count": len(outcomes),
                    "seed": 1,
                    "batch": 0,
                    "shards": 2,
                    "shard": 0,
                },
                "selected_count": len(outcomes),
                "selected_keys": [
                    list(mutant.key)
                    for mutant, _ in outcomes
                ],
                "oracle_command": [
                    "fixture-oracle",
                ],
            }
        ]

        killed = 0
        classified = 0
        unclassified = 0

        for mutant, outcome in outcomes:
            event: dict[str, object] = {
                "event": "mutant_outcome",
                "key": list(mutant.key),
                "target": mutant.target,
                "index": mutant.index,
                "line": mutant.line,
                "mutation_kind": mutant.kind,
                "source": mutant.text,
                "occurrence": mutant.occurrence,
                "outcome": outcome,
                "elapsed_seconds": 0.1,
                "source_blob": source_blob,
                "engine_blob": self.engine_blob,
            }

            if outcome == "killed":
                killed += 1
            elif outcome == "classified_survivor":
                classified += 1
                event["classification"] = (
                    "equivalent"
                )
                event["reason"] = (
                    "fixture classification"
                )
            elif outcome == "unclassified_survivor":
                unclassified += 1
            else:
                raise AssertionError(
                    f"unknown fixture outcome {outcome!r}"
                )

            events.append(event)

        events.append({
            "event": "campaign_complete",
            "completed": len(outcomes),
            "total": len(outcomes),
            "killed": killed,
            "classified_survivors": classified,
            "unclassified_survivors": unclassified,
            "elapsed_seconds": 0.2,
            "groups": [],
            "target_timings": [],
        })

        path.write_text(
            "".join(
                json.dumps(
                    event,
                    sort_keys=True,
                )
                + "\n"
                for event in events
            ),
            encoding="utf-8",
        )

    def test_slow_mutant_emits_progress_before_outcome(
        self,
    ) -> None:
        mutant = next(
            candidate
            for candidate
            in self.mutants()
            if candidate.kind == "arithmetic"
        )

        def delayed_execute(
            root: Path,
            selected: mutation.Mutant,
            command: list[str],
        ) -> tuple[
            mutation.Mutant,
            bool,
            float,
        ]:
            time.sleep(0.10)

            return (
                selected,
                True,
                0.10,
            )

        report = (
            self.root
            / "heartbeat.jsonl"
        )

        with patch(
            "tests.mutation_reporting._execute_one",
            side_effect=delayed_execute,
        ):
            mutation_reporting.run_campaign(
                self.root,
                (mutant,),
                ["fixture-oracle"],
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
                progress_every=100,
                progress_interval_seconds=0.02,
                stream=io.StringIO(),
            )

        events = [
            json.loads(line)
            for line
            in report.read_text().splitlines()
        ]

        progress_index = next(
            index
            for index, event
            in enumerate(events)
            if (
                event["event"]
                == "progress"
                and event["completed"] == 0
            )
        )
        outcome_index = next(
            index
            for index, event
            in enumerate(events)
            if event["event"] == "mutant_outcome"
        )

        self.assertLess(
            progress_index,
            outcome_index,
        )
        self.assertEqual(
            events[
                progress_index
            ]["current_target"],
            "first.py",
        )

    def test_worker_failure_is_reported_before_other_workers_finish(
        self,
    ) -> None:
        sites = self.mutants()

        self.assertGreaterEqual(
            len(sites),
            2,
        )

        failing = sites[0]
        slow = sites[1]
        slow_started = threading.Event()
        order: list[str] = []

        def execute(
            root: Path,
            selected: mutation.Mutant,
            command: list[str],
        ) -> tuple[
            mutation.Mutant,
            bool,
            float,
        ]:
            if selected.key == failing.key:
                if not slow_started.wait(
                    timeout=1.0
                ):
                    raise RuntimeError(
                        "slow fixture worker did not start"
                    )

                raise RuntimeError(
                    "fixture worker failure"
                )

            self.assertEqual(
                selected.key,
                slow.key,
            )
            slow_started.set()
            time.sleep(0.10)
            order.append(
                "slow-finished"
            )

            return (
                selected,
                True,
                0.10,
            )

        original_emit = (
            mutation_reporting.EventReporter.emit
        )

        def emit(
            reporter: mutation_reporting.EventReporter,
            event: dict[str, object],
        ) -> None:
            if (
                event["event"]
                == "campaign_error"
            ):
                order.append(
                    "campaign-error"
                )

            original_emit(
                reporter,
                event,
            )

        report = (
            self.root
            / "worker-failure.jsonl"
        )

        with (
            patch(
                "tests.mutation_reporting._execute_one",
                side_effect=execute,
            ),
            patch.object(
                mutation_reporting.EventReporter,
                "emit",
                new=emit,
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "fixture worker failure",
            ):
                mutation_reporting.run_campaign(
                    self.root,
                    (
                        failing,
                        slow,
                    ),
                    ["fixture-oracle"],
                    {},
                    report,
                    {
                        "count": 2,
                        "seed": 1,
                        "batch": 0,
                        "shards": 1,
                        "shard": 0,
                    },
                    workers=2,
                    progress_every=100,
                    stream=io.StringIO(),
                )

        self.assertEqual(
            order,
            [
                "campaign-error",
                "slow-finished",
            ],
        )

        events = [
            json.loads(line)
            for line
            in report.read_text().splitlines()
        ]
        errors = [
            event
            for event in events
            if event["event"] == "campaign_error"
        ]

        self.assertEqual(
            len(errors),
            1,
        )
        self.assertIn(
            "fixture worker failure",
            errors[0]["error"],
        )

    def test_a_mutant_run_may_take_as_long_as_the_oracle_limit(self) -> None:
        """A mutant that hits the limit counts as killed, so the limit must
        be the oracle's own (generous) one, not the engine's short default,
        or a slow runner turns survivors into kills."""

        selected = self.mutants()[0]

        with patch.object(
            mutation_reporting.mutation,
            "killed",
            return_value=(selected, True),
        ) as killed:
            mutation_reporting._execute_one(
                self.root,
                selected,
                ["fixture-oracle"],
            )

        self.assertEqual(
            killed.call_args.kwargs["timeout"],
            mutation_oracle.TIMEOUT_SECONDS,
        )
        self.assertGreater(
            mutation_oracle.TIMEOUT_SECONDS,
            mutation.killed.__defaults__[0],
        )

    def test_replay_failures_uses_only_unclassified_survivors(
        self,
    ) -> None:
        sites = self.mutants()

        self.assertGreaterEqual(
            len(sites),
            4,
        )

        killed = sites[0]
        failed_first = sites[1]
        classified = sites[2]
        failed_second = sites[3]

        first_report = (
            self.root
            / "shard-0.jsonl"
        )
        second_report = (
            self.root
            / "shard-1.jsonl"
        )

        self.write_report(
            first_report,
            (
                (
                    killed,
                    "killed",
                ),
                (
                    failed_first,
                    "unclassified_survivor",
                ),
            ),
        )
        self.write_report(
            second_report,
            (
                (
                    classified,
                    "classified_survivor",
                ),
                (
                    failed_second,
                    "unclassified_survivor",
                ),
            ),
        )

        command = [
            "fixture-oracle",
        ]
        baseline_result = subprocess.CompletedProcess(
            command,
            0,
            stdout=b"",
            stderr=b"",
        )

        def execute(
            root: Path,
            selected: mutation.Mutant,
            oracle: list[str],
        ) -> tuple[
            mutation.Mutant,
            bool,
        ]:
            self.assertEqual(
                root,
                self.root,
            )
            self.assertEqual(
                oracle,
                command,
            )

            return (
                selected,
                True,
            )

        with patch(
            "tests.mutation_campaign.mutation.baseline",
            return_value=baseline_result,
        ) as baseline, patch(
            "tests.mutation_campaign._execute_exact",
            side_effect=execute,
        ) as execute_exact:
            results = (
                mutation_campaign.replay_failures(
                    self.root,
                    (
                        first_report,
                        second_report,
                    ),
                    command,
                )
            )

        baseline.assert_called_once_with(
            self.root,
            command,
            timeout=mutation_oracle.TIMEOUT_SECONDS,
        )

        replayed_keys = [
            call.args[1].key
            for call
            in execute_exact.call_args_list
        ]

        self.assertEqual(
            replayed_keys,
            [
                failed_first.key,
                failed_second.key,
            ],
        )
        self.assertNotIn(
            killed.key,
            replayed_keys,
        )
        self.assertNotIn(
            classified.key,
            replayed_keys,
        )
        self.assertEqual(
            results,
            (
                (
                    failed_first,
                    True,
                ),
                (
                    failed_second,
                    True,
                ),
            ),
        )

    def test_replay_failures_stops_when_baseline_fails(
        self,
    ) -> None:
        mutant = self.mutants()[0]
        report = (
            self.root
            / "failed-baseline.jsonl"
        )

        self.write_report(
            report,
            (
                (
                    mutant,
                    "unclassified_survivor",
                ),
            ),
        )

        command = [
            "fixture-oracle",
        ]
        failed_baseline = subprocess.CompletedProcess(
            command,
            1,
            stdout=b"baseline stdout",
            stderr=b"baseline stderr",
        )

        with patch(
            "tests.mutation_campaign.mutation.baseline",
            return_value=failed_baseline,
        ) as baseline, patch(
            "tests.mutation_campaign._execute_exact",
        ) as execute_exact:
            with self.assertRaisesRegex(
                RuntimeError,
                "mutation replay baseline failed",
            ):
                mutation_campaign.replay_failures(
                    self.root,
                    (report,),
                    command,
                )

        baseline.assert_called_once_with(
            self.root,
            command,
            timeout=mutation_oracle.TIMEOUT_SECONDS,
        )
        execute_exact.assert_not_called()

    def test_failure_report_requires_completed_campaign(
        self,
    ) -> None:
        mutant = self.mutants()[0]
        report = (
            self.root
            / "incomplete.jsonl"
        )

        report.write_text(
            json.dumps({
                "event": "campaign_start",
                "engine_blob": self.engine_blob,
                "target_source_blobs": {
                    "first.py": self.source_blob(),
                },
                "inputs": {},
                "selected_count": 1,
                "selected_keys": [
                    list(mutant.key),
                ],
                "oracle_command": [
                    "fixture-oracle",
                ],
            })
            + "\n"
            + json.dumps({
                "event": "mutant_outcome",
                "key": list(mutant.key),
                "target": mutant.target,
                "index": mutant.index,
                "line": mutant.line,
                "mutation_kind": mutant.kind,
                "source": mutant.text,
                "occurrence": mutant.occurrence,
                "outcome": "unclassified_survivor",
                "elapsed_seconds": 0.1,
                "source_blob": self.source_blob(),
                "engine_blob": self.engine_blob,
            })
            + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            ValueError,
            "expected exactly one campaign_complete",
        ):
            mutation_campaign.failure_cases(
                (report,)
            )


if __name__ == "__main__":
    unittest.main()
