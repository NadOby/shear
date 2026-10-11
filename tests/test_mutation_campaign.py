"""Tests for mutation campaign selection, replay and reporting."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import mutation
from tests import mutation_campaign
from tests import mutation_oracle
from tests import mutation_reporting
from tests.lanes import LANES


class OracleMemoryLimitTests(unittest.TestCase):
    """A mutant that allocates without bound must fail its test run, not
    exhaust the runner (a campaign shard was terminated by exactly that)."""

    def test_the_oracle_process_cannot_allocate_past_the_cap(self) -> None:
        done = subprocess.run(
            [
                sys.executable,
                "-c",
                "from tests import mutation_oracle as o\n"
                "o.limit_memory(512 * 1024 * 1024)\n"
                "block = bytearray(1024 * 1024 * 1024)\n",
            ],
            capture_output=True,
            cwd=mutation.ROOT,
        )

        self.assertNotEqual(done.returncode, 0)
        self.assertIn(b"MemoryError", done.stderr)

    def test_the_oracle_applies_the_cap_before_running_any_test(self) -> None:
        order: list[str] = []

        with (
            patch.object(
                mutation_oracle,
                "limit_memory",
                side_effect=lambda: order.append("limit"),
            ),
            patch.object(
                mutation_oracle,
                "suite",
                side_effect=lambda: (order.append("suite"), unittest.TestSuite())[1],
            ),
        ):
            self.assertEqual(mutation_oracle.main(), 0)

        self.assertEqual(order, ["limit", "suite"])

    def test_the_cap_is_never_above_the_inherited_hard_limit(self) -> None:
        with patch.object(
            mutation_oracle.resource,
            "getrlimit",
            return_value=(1 << 40, 1 << 30),
        ), patch.object(
            mutation_oracle.resource,
            "setrlimit",
        ) as setter:
            mutation_oracle.limit_memory(1 << 33)

        setter.assert_called_once_with(
            mutation_oracle.resource.RLIMIT_AS,
            (1 << 30, 1 << 30),
        )


class MutationCampaignTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)

        self.targets = (
            "first.py",
            "second.py",
        )

        (self.root / "first.py").write_text(
            "\n".join(
                f"x{index} = {index} + 1"
                for index in range(12)
            )
            + "\n"
        )
        (self.root / "second.py").write_text(
            "\n".join(
                f"y{index} = {index} + 2"
                for index in range(9)
            )
            + "\n"
        )

        engine = self.root / "tests" / "mutation.py"
        engine.parent.mkdir()
        engine.write_text(
            "fixture mutation engine\n"
        )
        self.engine_blob = mutation.git_blob_id(
            engine.read_bytes()
        )

    def source_blob(
        self,
        target: str,
    ) -> str:
        return mutation.git_blob_id(
            (self.root / target).read_bytes()
        )

    def first_arithmetic_mutant(
        self,
    ) -> mutation.Mutant:
        source = (self.root / "first.py").read_text()

        return next(
            mutant
            for mutant in mutation.site_descriptions(
                source,
                "first.py",
            )
            if mutant.kind == "arithmetic"
        )

    def old_selected_keys(
        self,
        count: int,
        seed: int,
        batch: int,
    ) -> set[mutation.MutationKey]:
        """Reproduce Task 18's per-target selection semantics."""

        selected: set[mutation.MutationKey] = set()

        for target in self.targets:
            source = (self.root / target).read_text()
            descriptions = mutation.site_descriptions(
                source,
                target,
            )
            indexes = mutation.sample(
                source,
                count,
                seed,
                batch=batch,
            )

            selected.update(
                descriptions[index].key
                for index in indexes
            )

        return selected

    def test_work_set_preserves_existing_selection(self) -> None:
        work = mutation_campaign.build_work_set(
            self.root,
            self.targets,
            count=7,
            seed=11,
            batch=1,
        )

        self.assertEqual(
            {
                mutant.key
                for mutant in work
            },
            self.old_selected_keys(
                count=7,
                seed=11,
                batch=1,
            ),
        )

    def test_work_set_is_deterministic(self) -> None:
        first = mutation_campaign.build_work_set(
            self.root,
            self.targets,
            count=8,
            seed=37,
            batch=0,
        )
        second = mutation_campaign.build_work_set(
            self.root,
            self.targets,
            count=8,
            seed=37,
            batch=0,
        )

        self.assertEqual(
            tuple(mutant.key for mutant in first),
            tuple(mutant.key for mutant in second),
        )

    def test_shards_are_disjoint_and_exhaustive(self) -> None:
        work = mutation_campaign.build_work_set(
            self.root,
            self.targets,
            count=7,
            seed=5,
            batch=0,
        )
        shards = [
            mutation_campaign.shard_work(
                work,
                shards=4,
                shard=shard,
            )
            for shard in range(4)
        ]

        full_keys = {
            mutant.key
            for mutant in work
        }
        shard_keys = [
            {
                mutant.key
                for mutant in shard
            }
            for shard in shards
        ]

        self.assertEqual(
            set().union(*shard_keys),
            full_keys,
        )
        self.assertEqual(
            sum(len(keys) for keys in shard_keys),
            len(full_keys),
        )

        for left in range(len(shard_keys)):
            for right in range(left + 1, len(shard_keys)):
                self.assertTrue(
                    shard_keys[left].isdisjoint(
                        shard_keys[right]
                    )
                )

    def test_shard_sizes_differ_by_at_most_one(self) -> None:
        work = mutation_campaign.build_work_set(
            self.root,
            self.targets,
            count=7,
            seed=3,
            batch=0,
        )
        sizes = [
            len(
                mutation_campaign.shard_work(
                    work,
                    shards=4,
                    shard=shard,
                )
            )
            for shard in range(4)
        ]

        self.assertLessEqual(
            max(sizes) - min(sizes),
            1,
        )

    def test_shard_count_does_not_change_selected_work(self) -> None:
        work = mutation_campaign.build_work_set(
            self.root,
            self.targets,
            count=9,
            seed=19,
            batch=0,
        )
        expected = {
            mutant.key
            for mutant in work
        }

        for shard_count in (1, 2, 3, 4, 7):
            with self.subTest(shards=shard_count):
                combined = {
                    mutant.key
                    for shard in range(shard_count)
                    for mutant in mutation_campaign.shard_work(
                        work,
                        shards=shard_count,
                        shard=shard,
                    )
                }

                self.assertEqual(
                    combined,
                    expected,
                )

    def test_work_for_shard_matches_explicit_sharding(self) -> None:
        work = mutation_campaign.build_work_set(
            self.root,
            self.targets,
            count=6,
            seed=13,
            batch=1,
        )

        self.assertEqual(
            mutation_campaign.work_for_shard(
                self.root,
                self.targets,
                count=6,
                seed=13,
                batch=1,
                shards=4,
                shard=2,
            ),
            mutation_campaign.shard_work(
                work,
                shards=4,
                shard=2,
            ),
        )

    def test_plan_sizes_shards_from_the_selected_work(self) -> None:
        plan = mutation_campaign.plan_shards
        per = mutation_campaign.MUTANTS_PER_SHARD
        top = mutation_campaign.MAX_SHARDS

        self.assertEqual(plan(0), 1)
        self.assertEqual(plan(1), 1)
        self.assertEqual(plan(per), 1)
        self.assertEqual(plan(per + 1), 2)
        self.assertEqual(plan(per * top * 10), top)
        self.assertEqual(plan(per * top * 10, " 3 "), 3)

        for bad in ("0", str(top + 1), "x", "-1", "2.5"):
            with self.subTest(requested=bad):
                with self.assertRaises(ValueError):
                    plan(10, bad)

    def test_invalid_shards_are_rejected(self) -> None:
        work = mutation_campaign.build_work_set(
            self.root,
            self.targets,
            count=1,
            seed=1,
        )

        with self.assertRaises(ValueError):
            mutation_campaign.shard_work(
                work,
                shards=0,
                shard=0,
            )

        with self.assertRaises(ValueError):
            mutation_campaign.shard_work(
                work,
                shards=4,
                shard=-1,
            )

        with self.assertRaises(ValueError):
            mutation_campaign.shard_work(
                work,
                shards=4,
                shard=4,
            )

    def test_oracle_is_exactly_non_mutation_lanes(self) -> None:
        expected = tuple(
            module
            for lane, modules in LANES.items()
            if lane != "mutation"
            for module in modules
        )

        self.assertEqual(
            mutation_oracle.modules(),
            expected,
        )
        self.assertTrue(
            set(mutation_oracle.modules()).isdisjoint(
                LANES["mutation"]
            )
        )

    def test_baseline_and_mutant_use_same_oracle_command(self) -> None:
        mutant = self.first_arithmetic_mutant()
        command = mutation_oracle.command()
        completed = subprocess.CompletedProcess(
            command,
            0,
            stdout=b"",
            stderr=b"",
        )

        with patch(
            "tests.mutation.subprocess.run",
            return_value=completed,
        ) as run:
            baseline = mutation.baseline(
                self.root,
                command,
            )
            _, dead = mutation.killed(
                self.root,
                "first.py",
                mutant.index,
                command,
            )

        self.assertEqual(baseline.returncode, 0)
        self.assertFalse(dead)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(
            run.call_args_list[0].args[0],
            command,
        )
        self.assertEqual(
            run.call_args_list[1].args[0],
            command,
        )
        self.assertEqual(
            run.call_args_list[0].kwargs["env"],
            run.call_args_list[1].kwargs["env"],
        )

    def test_exact_key_resolves_under_matching_pins(self) -> None:
        expected = self.first_arithmetic_mutant()

        resolved = mutation_campaign.resolve_exact_key(
            self.root,
            expected.key,
            self.source_blob("first.py"),
            self.engine_blob,
        )

        self.assertEqual(
            resolved,
            expected,
        )

    def test_exact_key_rejects_source_version_mismatch(self) -> None:
        mutant = self.first_arithmetic_mutant()

        with self.assertRaisesRegex(
            ValueError,
            "source version mismatch",
        ):
            mutation_campaign.resolve_exact_key(
                self.root,
                mutant.key,
                "0" * 40,
                self.engine_blob,
            )

    def test_exact_key_rejects_engine_version_mismatch(self) -> None:
        mutant = self.first_arithmetic_mutant()

        with self.assertRaisesRegex(
            ValueError,
            "mutation engine version mismatch",
        ):
            mutation_campaign.resolve_exact_key(
                self.root,
                mutant.key,
                self.source_blob("first.py"),
                "0" * 40,
            )

    def test_exact_key_must_resolve_once(self) -> None:
        mutant = self.first_arithmetic_mutant()
        missing: mutation.MutationKey = (
            mutant.target,
            mutant.kind,
            "not the source line",
            mutant.occurrence,
        )

        with self.assertRaisesRegex(
            ValueError,
            "resolved to 0 sites",
        ):
            mutation_campaign.resolve_exact_key(
                self.root,
                missing,
                self.source_blob("first.py"),
                self.engine_blob,
            )

    def test_exact_replay_runs_resolved_mutant(self) -> None:
        mutant = self.first_arithmetic_mutant()
        command = [
            "python",
            "-m",
            "fixture-oracle",
        ]
        baseline_result = subprocess.CompletedProcess(
            command,
            0,
            stdout=b"",
            stderr=b"",
        )

        with (
            patch(
                "tests.mutation_campaign.mutation.baseline",
                return_value=baseline_result,
            ) as baseline,
            patch(
                "tests.mutation_campaign.mutation.killed",
                return_value=(mutant, False),
            ) as killed,
        ):
            replayed, dead = mutation_campaign.replay_exact(
                self.root,
                mutant.key,
                self.source_blob("first.py"),
                self.engine_blob,
                command,
            )

        self.assertEqual(
            replayed,
            mutant,
        )
        self.assertFalse(dead)
        baseline.assert_called_once_with(
            self.root,
            command,
            timeout=mutation_oracle.TIMEOUT_SECONDS,
        )
        killed.assert_called_once_with(
            self.root,
            mutant.target,
            mutant.index,
            command,
            timeout=mutation_oracle.TIMEOUT_SECONDS,
        )

    def test_exact_replay_stops_when_baseline_fails(self) -> None:
        mutant = self.first_arithmetic_mutant()
        command = [
            "python",
            "-m",
            "fixture-oracle",
        ]
        baseline_result = subprocess.CompletedProcess(
            command,
            1,
            stdout=b"broken baseline",
            stderr=b"fixture failure",
        )

        with (
            patch(
                "tests.mutation_campaign.mutation.baseline",
                return_value=baseline_result,
            ),
            patch(
                "tests.mutation_campaign.mutation.killed",
            ) as killed,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "baseline failed",
            ):
                mutation_campaign.replay_exact(
                    self.root,
                    mutant.key,
                    self.source_blob("first.py"),
                    self.engine_blob,
                    command,
                )

        killed.assert_not_called()

    def test_replay_key_json_round_trips(self) -> None:
        mutant = self.first_arithmetic_mutant()
        encoded = (
            '["first.py", "arithmetic", '
            f'{mutant.text!r}, 0]'
        ).replace(
            "'",
            '"',
        )

        self.assertEqual(
            mutation_campaign._parse_key(encoded),
            mutant.key,
        )

    def test_report_records_versions_inputs_keys_and_outcomes(
        self,
    ) -> None:
        source = (self.root / "first.py").read_text()
        work = tuple(
            mutation.site_descriptions(
                source,
                "first.py",
            )[:3]
        )
        outcomes = {
            work[0].key: (
                True,
                0.10,
            ),
            work[1].key: (
                False,
                0.20,
            ),
            work[2].key: (
                False,
                0.30,
            ),
        }
        classifications = {
            work[1].key: (
                "equivalent",
                "fixture classification",
            ),
        }

        def execute(
            root: Path,
            selected: mutation.Mutant,
            command: list[str],
        ) -> tuple[
            mutation.Mutant,
            bool,
            float,
        ]:
            dead, elapsed = outcomes[
                selected.key
            ]

            return (
                selected,
                dead,
                elapsed,
            )

        report = self.root / "report.jsonl"
        human = io.StringIO()

        with patch(
            "tests.mutation_reporting._execute_one",
            side_effect=execute,
        ):
            result = mutation_reporting.run_campaign(
                self.root,
                work,
                ["fixture-oracle"],
                classifications,
                report,
                {
                    "count": 3,
                    "seed": 7,
                    "batch": 0,
                    "shards": 1,
                    "shard": 0,
                },
                workers=1,
                progress_every=1,
                stream=human,
            )

        events = [
            json.loads(line)
            for line in report.read_text().splitlines()
        ]

        self.assertEqual(
            events[0]["event"],
            "campaign_start",
        )
        self.assertEqual(
            events[0]["engine_blob"],
            self.engine_blob,
        )
        self.assertEqual(
            events[0]["target_source_blobs"],
            {
                "first.py": self.source_blob(
                    "first.py"
                ),
            },
        )
        self.assertEqual(
            events[0]["inputs"]["seed"],
            7,
        )
        self.assertEqual(
            events[0]["selected_count"],
            len(work),
        )
        self.assertEqual(
            {
                tuple(key)
                for key in events[0]["selected_keys"]
            },
            {
                mutant.key
                for mutant in work
            },
        )

        outcome_events = [
            event
            for event in events
            if event["event"] == "mutant_outcome"
        ]

        self.assertEqual(
            {
                tuple(event["key"])
                for event in outcome_events
            },
            {
                mutant.key
                for mutant in work
            },
        )
        self.assertEqual(
            {
                event["outcome"]
                for event in outcome_events
            },
            {
                "killed",
                "classified_survivor",
                "unclassified_survivor",
            },
        )

        for event in outcome_events:
            self.assertEqual(
                event["engine_blob"],
                self.engine_blob,
            )
            self.assertEqual(
                event["source_blob"],
                self.source_blob("first.py"),
            )

        complete = events[-1]

        self.assertEqual(
            complete["event"],
            "campaign_complete",
        )
        self.assertEqual(
            complete["killed"],
            1,
        )
        self.assertEqual(
            complete["classified_survivors"],
            1,
        )
        self.assertEqual(
            complete["unclassified_survivors"],
            1,
        )
        self.assertTrue(
            complete["groups"]
        )
        self.assertEqual(
            complete["target_timings"][0]["count"],
            3,
        )

        self.assertEqual(
            result.killed,
            1,
        )
        self.assertEqual(
            len(result.classified_survivors),
            1,
        )
        self.assertEqual(
            len(result.unclassified_survivors),
            1,
        )

        text = human.getvalue()

        self.assertIn(
            self.engine_blob,
            text,
        )
        self.assertIn(
            self.source_blob("first.py"),
            text,
        )
        self.assertIn(
            "SURVIVOR classified_survivor",
            text,
        )
        self.assertIn(
            "SURVIVOR unclassified_survivor",
            text,
        )
        self.assertNotIn(
            "SURVIVOR killed",
            text,
        )
        self.assertLess(
            text.index("SURVIVOR"),
            text.index("mutation campaign complete"),
        )

    def test_report_is_completed_with_unclassified_survivor(
        self,
    ) -> None:
        mutant = self.first_arithmetic_mutant()
        report = self.root / "survivor.jsonl"

        with patch(
            "tests.mutation_reporting._execute_one",
            return_value=(
                mutant,
                False,
                0.1,
            ),
        ):
            result = mutation_reporting.run_campaign(
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
                progress_every=1,
                stream=io.StringIO(),
            )

        events = [
            json.loads(line)
            for line in report.read_text().splitlines()
        ]

        self.assertEqual(
            events[-1]["event"],
            "campaign_complete",
        )
        self.assertEqual(
            events[-1]["unclassified_survivors"],
            1,
        )
        self.assertEqual(
            result.unclassified_survivors,
            (mutant,),
        )


if __name__ == "__main__":
    unittest.main()
