"""Mutation campaign work selection, sharding and exact replay."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path

from tests import mutation
from tests import mutation_oracle
from tests import mutation_reporting
from tests import mutation_verdict


@dataclass(frozen=True)
class ReplayCase:
    key: mutation.MutationKey
    source_blob: str
    engine_blob: str


def select_targets(
    available: tuple[str, ...],
    requested: str = "",
) -> tuple[str, ...]:
    """Filter registered mutation targets using exact paths or directories.

    Blank input means all targets. Directory selectors must end in "/".
    Selection follows catalog order and removes duplicates.
    """

    selectors = requested.split()

    if not selectors:
        return available

    selected: set[str] = set()

    for selector in selectors:
        if selector.endswith("/"):
            matches = tuple(
                target for target in available
                if target.startswith(selector)
            )
        else:
            matches = (
                (selector,)
                if selector in available
                else ()
            )

        if not matches:
            raise ValueError(
                "unknown mutation target or directory prefix: "
                f"{selector!r}"
            )

        selected.update(matches)

    return tuple(
        target for target in available
        if target in selected
    )


def build_work_set(
    root: Path,
    targets: tuple[str, ...],
    count: int,
    seed: int,
    batch: int = 0,
) -> tuple[mutation.Mutant, ...]:
    """Build the exact selected mutation work set.

    Selection retains the Task 18 semantics: each target independently uses
    mutation.sample() with the requested count, seed and batch. Only after that
    complete unsharded set exists is it shuffled for mutant-level sharding.
    """

    selected: list[mutation.Mutant] = []

    for target in targets:
        source = (root / target).read_text()
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

        selected.extend(
            descriptions[index]
            for index in indexes
        )

    keys = [
        mutant.key
        for mutant in selected
    ]

    if len(keys) != len(set(keys)):
        raise RuntimeError(
            "selected mutation work set contains duplicate keys"
        )

    shuffled = list(selected)
    random.Random(seed).shuffle(shuffled)

    return tuple(shuffled)


MAX_SHARDS = 16
MUTANTS_PER_SHARD = 150


def plan_shards(selected: int, requested: str = "") -> int:
    """How many shards a campaign of ``selected`` mutants uses.

    An explicit request wins and must be an integer from 1 to MAX_SHARDS.
    Otherwise there is one shard per MUTANTS_PER_SHARD selected mutants,
    between 1 and MAX_SHARDS: each shard pays a fixed cost (runner setup and
    one baseline oracle run) before its first mutant, so tiny campaigns stay
    on few runners. MAX_SHARDS keeps a campaign below the account's
    concurrent-job limit.
    """

    requested = requested.strip()

    if requested:
        if not requested.isdigit() or not 1 <= int(requested) <= MAX_SHARDS:
            raise ValueError(
                f"shard count must be an integer from 1 to {MAX_SHARDS}, "
                f"got {requested!r}"
            )

        return int(requested)

    return min(MAX_SHARDS, max(1, math.ceil(selected / MUTANTS_PER_SHARD)))


def shard_work(
    work: tuple[mutation.Mutant, ...],
    shards: int,
    shard: int,
) -> tuple[mutation.Mutant, ...]:
    """Return one balanced deterministic mutant shard.

    ``work`` is already deterministically shuffled. Round-robin assignment
    therefore changes only ownership of mutants, never the selected set.
    """

    if shards < 1:
        raise ValueError(
            "SHEAR_MUTATE_SHARDS must be a positive integer"
        )

    if shard < 0 or shard >= shards:
        raise ValueError(
            "SHEAR_MUTATE_SHARD must be between 0 and "
            "SHEAR_MUTATE_SHARDS - 1"
        )

    return tuple(
        mutant
        for index, mutant in enumerate(work)
        if index % shards == shard
    )


def work_for_shard(
    root: Path,
    targets: tuple[str, ...],
    count: int,
    seed: int,
    batch: int,
    shards: int,
    shard: int,
) -> tuple[mutation.Mutant, ...]:
    """Build the unsharded selection, then return one mutant-level shard."""

    return shard_work(
        build_work_set(
            root,
            targets,
            count,
            seed,
            batch,
        ),
        shards,
        shard,
    )


def resolve_exact_key(
    root: Path,
    key: mutation.MutationKey,
    source_blob: str,
    engine_blob: str,
) -> mutation.Mutant:
    """Resolve one exact mutation key under pinned source and engine versions."""

    engine_path = root / "tests" / "mutation.py"

    if not engine_path.is_file():
        raise ValueError(
            "reviewed mutation engine is missing: tests/mutation.py"
        )

    current_engine = mutation.git_blob_id(
        engine_path.read_bytes()
    )

    if current_engine != engine_blob:
        raise ValueError(
            "mutation engine version mismatch: "
            f"expected {engine_blob}, got {current_engine}"
        )

    target = key[0]
    target_path = root / target

    if not target_path.is_file():
        raise ValueError(
            f"mutation target is missing: {target}"
        )

    current_source = mutation.git_blob_id(
        target_path.read_bytes()
    )

    if current_source != source_blob:
        raise ValueError(
            f"{target}: source version mismatch: "
            f"expected {source_blob}, got {current_source}"
        )

    source = target_path.read_text()
    matches = [
        mutant
        for mutant in mutation.site_descriptions(
            source,
            target,
        )
        if mutant.key == key
    ]

    if len(matches) != 1:
        raise ValueError(
            f"{target}: exact mutation key resolved to "
            f"{len(matches)} sites, expected exactly one"
        )

    return matches[0]


def _require_replay_baseline(
    root: Path,
    oracle: list[str],
) -> None:
    """Require a clean semantic baseline before interpreting replay results."""

    baseline = mutation.baseline(
        root,
        oracle,
        timeout=mutation_oracle.TIMEOUT_SECONDS,
    )

    if baseline.returncode != 0:
        raise RuntimeError(
            "mutation replay baseline failed; "
            "replay results would be invalid\n\n"
            "stdout:\n"
            f"{baseline.stdout.decode(errors='replace')}\n"
            "stderr:\n"
            f"{baseline.stderr.decode(errors='replace')}"
        )


def _execute_exact(
    root: Path,
    selected: mutation.Mutant,
    oracle: list[str],
) -> tuple[mutation.Mutant, mutation_reporting.Execution]:
    """Execute one already-resolved exact mutant.

    The result says how the run ended, so a timeout is not mistaken for a kill.
    """

    try:
        executed, execution, _ = mutation_reporting.execute(
            root,
            selected,
            oracle,
            mutation_reporting.RunOptions(
                limit=mutation_oracle.TIMEOUT_SECONDS,
            ),
        )
    except RuntimeError as exc:
        raise RuntimeError(
            "resolved mutation key changed during replay"
        ) from exc

    return executed, execution


def replay_exact(
    root: Path,
    key: mutation.MutationKey,
    source_blob: str,
    engine_blob: str,
    command: list[str] | None = None,
) -> tuple[mutation.Mutant, mutation_reporting.Execution]:
    """Run one exact pinned mutation after a clean semantic baseline."""

    selected = resolve_exact_key(
        root,
        key,
        source_blob,
        engine_blob,
    )
    oracle = (
        mutation_oracle.command()
        if command is None
        else command
    )

    _require_replay_baseline(
        root,
        oracle,
    )

    return _execute_exact(
        root,
        selected,
        oracle,
    )


def _key_from_value(
    value: object,
) -> mutation.MutationKey:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or not isinstance(value[0], str)
        or not isinstance(value[1], str)
        or not isinstance(value[2], str)
        or not isinstance(value[3], int)
        or isinstance(value[3], bool)
        or value[3] < 0
    ):
        raise ValueError(
            "mutation key must be "
            '[target, kind, source, occurrence]'
        )

    return (
        value[0],
        value[1],
        value[2],
        value[3],
    )


def _parse_key(raw: str) -> mutation.MutationKey:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "mutation key must be valid JSON"
        ) from exc

    return _key_from_value(value)


def _blob_id(
    value: object,
    field: str,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        raise ValueError(
            f"{field} must be a lowercase 40-character Git blob ID"
        )

    return value


def _report_failure_cases(
    path: Path,
) -> tuple[ReplayCase, ...]:
    if not path.is_file():
        raise ValueError(
            f"mutation report is missing: {path}"
        )

    start_events: list[dict[str, object]] = []
    complete_events: list[dict[str, object]] = []
    failures: list[ReplayCase] = []

    for line_number, raw in enumerate(
        path.read_text(
            encoding="utf-8"
        ).splitlines(),
        start=1,
    ):
        if not raw.strip():
            continue

        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{path}:{line_number}: invalid JSON"
            ) from exc

        if not isinstance(event, dict):
            raise ValueError(
                f"{path}:{line_number}: event must be an object"
            )

        event_kind = event.get("event")

        if event_kind == "campaign_start":
            start_events.append(event)
            continue

        if event_kind == "campaign_complete":
            complete_events.append(event)
            continue

        if (
            event_kind != "mutant_outcome"
            or event.get("outcome")
            != "unclassified_survivor"
        ):
            continue

        try:
            key = _key_from_value(
                event.get("key")
            )
            source_blob = _blob_id(
                event.get("source_blob"),
                "source_blob",
            )
            engine_blob = _blob_id(
                event.get("engine_blob"),
                "engine_blob",
            )
        except ValueError as exc:
            raise ValueError(
                f"{path}:{line_number}: {exc}"
            ) from exc

        failures.append(
            ReplayCase(
                key=key,
                source_blob=source_blob,
                engine_blob=engine_blob,
            )
        )

    if len(start_events) != 1:
        raise ValueError(
            f"{path}: expected exactly one campaign_start event, "
            f"found {len(start_events)}"
        )

    if len(complete_events) != 1:
        raise ValueError(
            f"{path}: expected exactly one campaign_complete event, "
            f"found {len(complete_events)}"
        )

    start = start_events[0]
    complete = complete_events[0]

    try:
        start_engine = _blob_id(
            start.get("engine_blob"),
            "campaign_start engine_blob",
        )
    except ValueError as exc:
        raise ValueError(
            f"{path}: {exc}"
        ) from exc

    sources = start.get(
        "target_source_blobs"
    )

    if not isinstance(sources, dict):
        raise ValueError(
            f"{path}: campaign_start target_source_blobs "
            "must be an object"
        )

    expected_failures = complete.get(
        "unclassified_survivors"
    )

    if (
        not isinstance(
            expected_failures,
            int,
        )
        or isinstance(
            expected_failures,
            bool,
        )
        or expected_failures < 0
    ):
        raise ValueError(
            f"{path}: campaign_complete "
            "unclassified_survivors must be "
            "a non-negative integer"
        )

    if expected_failures != len(failures):
        raise ValueError(
            f"{path}: campaign_complete records "
            f"{expected_failures} unclassified survivors "
            f"but {len(failures)} outcome events were found"
        )

    for case in failures:
        if case.engine_blob != start_engine:
            raise ValueError(
                f"{path}: mutation outcome engine blob "
                "does not match campaign_start"
            )

        start_source = sources.get(
            case.key[0]
        )

        if start_source != case.source_blob:
            raise ValueError(
                f"{path}: mutation outcome source blob "
                f"for {case.key[0]} does not match "
                "campaign_start"
            )

    return tuple(failures)


def failure_cases(
    report_paths: tuple[Path, ...],
) -> tuple[ReplayCase, ...]:
    """Load the exact unclassified survivors from completed shard reports."""

    if not report_paths:
        raise ValueError(
            "at least one mutation report is required"
        )

    selected: list[ReplayCase] = []
    seen: dict[
        mutation.MutationKey,
        tuple[str, str],
    ] = {}

    for path in report_paths:
        for case in _report_failure_cases(
            path
        ):
            pins = (
                case.source_blob,
                case.engine_blob,
            )
            previous = seen.get(
                case.key
            )

            if previous is not None:
                if previous != pins:
                    raise ValueError(
                        "same mutation key appears with "
                        "conflicting source or engine pins"
                    )

                continue

            seen[case.key] = pins
            selected.append(case)

    return tuple(selected)


def replay_failures(
    root: Path,
    report_paths: tuple[Path, ...],
    command: list[str] | None = None,
) -> tuple[
    tuple[mutation.Mutant, mutation_reporting.Execution],
    ...,
]:
    """Replay only unclassified survivors recorded by completed campaigns."""

    cases = failure_cases(
        report_paths
    )

    if not cases:
        return ()

    oracle = (
        mutation_oracle.command()
        if command is None
        else command
    )

    _require_replay_baseline(
        root,
        oracle,
    )

    results = []

    for case in cases:
        selected = resolve_exact_key(
            root,
            case.key,
            case.source_blob,
            case.engine_blob,
        )
        results.append(
            _execute_exact(
                root,
                selected,
                oracle,
            )
        )

    return tuple(results)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mutation campaign utilities",
    )
    subparsers = parser.add_subparsers(
        dest="action",
        required=True,
    )

    replay = subparsers.add_parser(
        "replay",
        help="replay one exact pinned mutation key",
    )
    replay.add_argument(
        "--key-json",
        required=True,
        help=(
            "JSON mutation key: "
            '[target, kind, source, occurrence]'
        ),
    )
    replay.add_argument(
        "--source-blob",
        required=True,
        help="expected Git blob id of the mutation target",
    )
    replay.add_argument(
        "--engine-blob",
        required=True,
        help="expected Git blob id of tests/mutation.py",
    )
    replay.add_argument(
        "--root",
        default=str(mutation.ROOT),
        help="repository root; defaults to the current repository",
    )

    plan = subparsers.add_parser(
        "plan",
        help="size the shard matrix for a campaign",
    )
    plan.add_argument("--count", type=int, required=True)
    plan.add_argument("--seed", type=int, required=True)
    plan.add_argument("--batch", type=int, default=0)
    plan.add_argument(
        "--targets",
        default="",
        help=(
            "space-separated target paths or directory prefixes; "
            "empty selects every target"
        ),
    )
    plan.add_argument(
        "--shards",
        default="",
        help="explicit shard count; empty sizes it from the selected work",
    )

    replay_failures_parser = subparsers.add_parser(
        "replay-failures",
        help=(
            "replay only unclassified survivors "
            "from completed JSONL campaign reports"
        ),
    )
    replay_failures_parser.add_argument(
        "reports",
        nargs="+",
        help=(
            "one or more mutation-report JSONL files; "
            "shell globs may be used"
        ),
    )
    replay_failures_parser.add_argument(
        "--root",
        default=str(mutation.ROOT),
        help="repository root; defaults to the current repository",
    )

    return parser


def _print_result(
    mutant: mutation.Mutant,
    verdict: bool | mutation_reporting.Execution,
) -> None:
    execution = mutation_reporting._execution(verdict)
    outcome = (
        "survived"
        if execution.outcome == mutation_verdict.SURVIVED
        else execution.outcome
    )

    print(
        f"{outcome}: "
        f"{mutant.target}:site-{mutant.index}:"
        f"line-{mutant.line} "
        f"{mutant.kind}[{mutant.occurrence}]: "
        f"{mutant.text}",
        flush=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    if args.action == "plan":
        from tests.mutation_catalog import TARGETS

        try:
            targets = select_targets(TARGETS, args.targets)
            work = build_work_set(
                mutation.ROOT,
                targets,
                args.count,
                args.seed,
                batch=args.batch,
            )
            shards = plan_shards(len(work), args.shards)
        except ValueError as exc:
            print(f"mutation plan failed: {exc}", file=sys.stderr)
            return 2

        print(
            f"selected={len(work)} shards={shards} "
            f"targets={len(targets)}"
        )
        print(f"target paths: {', '.join(targets)}")
        output = os.environ.get("GITHUB_OUTPUT")

        if output:
            with open(output, "a") as handle:
                handle.write(f"count={shards}\n")
                handle.write(f"shards={json.dumps(list(range(shards)))}\n")

        return 0

    if args.action == "replay":
        try:
            key = _parse_key(
                args.key_json
            )
            mutant, verdict = replay_exact(
                Path(args.root),
                key,
                args.source_blob,
                args.engine_blob,
            )
        except (
            ValueError,
            RuntimeError,
        ) as exc:
            print(
                f"mutation replay failed: {exc}",
                file=sys.stderr,
            )
            return 2

        _print_result(
            mutant,
            verdict,
        )
        return 0

    if args.action == "replay-failures":
        try:
            results = replay_failures(
                Path(args.root),
                tuple(
                    Path(path)
                    for path in args.reports
                ),
            )
        except (
            ValueError,
            RuntimeError,
        ) as exc:
            print(
                f"mutation replay failed: {exc}",
                file=sys.stderr,
            )
            return 2

        if not results:
            print(
                "no unclassified survivors recorded "
                "in the supplied reports",
                flush=True,
            )
            return 0

        surviving = 0

        for mutant, verdict in results:
            _print_result(
                mutant,
                verdict,
            )

            if (
                mutation_reporting._execution(verdict).outcome
                != mutation_verdict.KILLED
            ):
                surviving += 1

        print(
            "replayed "
            f"{len(results)} previously unclassified "
            "survivors; "
            f"{surviving} still survive",
            flush=True,
        )

        return 1 if surviving else 0

    parser.error(
        f"unsupported action: {args.action}"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
