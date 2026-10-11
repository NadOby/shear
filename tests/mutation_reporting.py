"""Observable execution and evidence reporting for mutation campaigns."""

from __future__ import annotations

import json
import os
import shlex
import sys
import time
from collections import defaultdict
from concurrent.futures import (
    FIRST_COMPLETED,
    ThreadPoolExecutor,
    wait,
)
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from tests import mutation, mutation_oracle


@dataclass(frozen=True)
class CampaignResult:
    killed: int
    classified_survivors: tuple[mutation.Mutant, ...]
    unclassified_survivors: tuple[mutation.Mutant, ...]
    elapsed_seconds: float


def _engine_blob(root: Path) -> str:
    path = root / "tests" / "mutation.py"

    if not path.is_file():
        raise ValueError(
            "mutation engine is missing: tests/mutation.py"
        )

    return mutation.git_blob_id(
        path.read_bytes()
    )


def _source_blobs(
    root: Path,
    work: tuple[mutation.Mutant, ...],
) -> dict[str, str]:
    targets = sorted({
        mutant.target
        for mutant in work
    })

    return {
        target: mutation.git_blob_id(
            (root / target).read_bytes()
        )
        for target in targets
    }


def _execute_one(
    root: Path,
    selected: mutation.Mutant,
    command: list[str],
) -> tuple[mutation.Mutant, bool, float]:
    started = time.perf_counter()

    executed, dead = mutation.killed(
        root,
        selected.target,
        selected.index,
        command,
        timeout=mutation_oracle.TIMEOUT_SECONDS,
    )

    elapsed = time.perf_counter() - started

    if executed.key != selected.key:
        raise RuntimeError(
            "selected mutation key changed during execution"
        )

    return executed, dead, elapsed


class EventReporter:
    """Write machine evidence and render its human-facing event stream."""

    def __init__(
        self,
        path: Path,
        stream: TextIO | None = None,
    ) -> None:
        self.path = path
        self.stream = (
            sys.stdout
            if stream is None
            else stream
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._file = path.open(
            "w",
            encoding="utf-8",
        )

    def close(self) -> None:
        self._file.close()

    def emit(
        self,
        event: dict[str, object],
    ) -> None:
        self._file.write(
            json.dumps(
                event,
                sort_keys=True,
            )
            + "\n"
        )
        self._file.flush()

        rendered = self._render(event)

        if rendered is not None:
            print(
                rendered,
                file=self.stream,
                flush=True,
            )

    def _render(
        self,
        event: dict[str, object],
    ) -> str | None:
        kind = event["event"]

        if kind == "campaign_start":
            inputs = event["inputs"]
            sources = event["target_source_blobs"]

            input_text = ", ".join(
                f"{name}={value}"
                for name, value in sorted(
                    inputs.items()
                )
            )
            source_text = "\n".join(
                f"  {target}: {blob}"
                for target, blob in sorted(
                    sources.items()
                )
            )

            return (
                "mutation campaign start: "
                f"selected {event['selected_count']} mutants\n"
                f"engine: {event['engine_blob']}\n"
                f"inputs: {input_text}\n"
                "target sources:\n"
                f"{source_text}"
            )

        if kind == "mutant_outcome":
            outcome = event["outcome"]

            if outcome == "killed":
                return None

            classification = ""

            if outcome == "classified_survivor":
                classification = (
                    " "
                    f"{event['classification']}: "
                    f"{event['reason']}"
                )

            key_json = json.dumps(
                event["key"]
            )
            replay = shlex.join([
                "python",
                "-m",
                "tests.mutation_campaign",
                "replay",
                "--key-json",
                key_json,
                "--source-blob",
                str(event["source_blob"]),
                "--engine-blob",
                str(event["engine_blob"]),
            ])

            return (
                "SURVIVOR "
                f"{outcome}: "
                f"{event['target']}:"
                f"site-{event['index']}:"
                f"line-{event['line']} "
                f"{event['mutation_kind']}"
                f"[{event['occurrence']}]: "
                f"{event['source']}"
                f"{classification}\n"
                "  key-json: "
                f"{key_json}\n"
                "  source-blob: "
                f"{event['source_blob']}\n"
                "  engine-blob: "
                f"{event['engine_blob']}\n"
                "  replay: "
                f"{replay}"
            )

        if kind == "progress":
            return (
                "mutation progress: "
                f"{event['completed']}/{event['total']} "
                f"killed={event['killed']} "
                "classified-survivors="
                f"{event['classified_survivors']} "
                "unclassified-survivors="
                f"{event['unclassified_survivors']} "
                f"elapsed={event['elapsed_seconds']:.1f}s "
                f"current-target={event['current_target']}"
            )

        if kind == "campaign_complete":
            groups = event["groups"]
            timings = event["target_timings"]

            group_text = "\n".join(
                (
                    f"  {group['target']} "
                    f"{group['mutation_kind']}: "
                    f"killed={group['killed']} "
                    "classified-survivors="
                    f"{group['classified_survivors']} "
                    "unclassified-survivors="
                    f"{group['unclassified_survivors']}"
                )
                for group in groups
            )

            timing_text = "\n".join(
                (
                    f"  {timing['target']}: "
                    f"count={timing['count']} "
                    f"total={timing['total_seconds']:.3f}s "
                    f"mean={timing['mean_seconds']:.3f}s "
                    f"min={timing['min_seconds']:.3f}s "
                    f"max={timing['max_seconds']:.3f}s"
                )
                for timing in timings
            )

            return (
                "mutation campaign complete: "
                f"{event['completed']}/{event['total']} "
                f"killed={event['killed']} "
                "classified-survivors="
                f"{event['classified_survivors']} "
                "unclassified-survivors="
                f"{event['unclassified_survivors']} "
                f"elapsed={event['elapsed_seconds']:.1f}s\n"
                "outcomes by target and mutation kind:\n"
                f"{group_text}\n"
                "per-target timings:\n"
                f"{timing_text}"
            )

        if kind == "campaign_error":
            return (
                "mutation campaign error: "
                f"{event['error']}"
            )

        return None


def _group_summary(
    counts: dict[
        tuple[str, str],
        dict[str, int],
    ],
) -> list[dict[str, object]]:
    result = []

    for (target, kind), values in sorted(
        counts.items()
    ):
        result.append({
            "target": target,
            "mutation_kind": kind,
            "killed": values["killed"],
            "classified_survivors": (
                values["classified_survivors"]
            ),
            "unclassified_survivors": (
                values["unclassified_survivors"]
            ),
        })

    return result


def _timing_summary(
    timings: dict[str, list[float]],
) -> list[dict[str, object]]:
    result = []

    for target, values in sorted(
        timings.items()
    ):
        total = sum(values)

        result.append({
            "target": target,
            "count": len(values),
            "total_seconds": total,
            "mean_seconds": total / len(values),
            "min_seconds": min(values),
            "max_seconds": max(values),
        })

    return result


def run_campaign(
    root: Path,
    work: tuple[mutation.Mutant, ...],
    command: list[str],
    classifications: dict[
        mutation.MutationKey,
        tuple[str, str],
    ],
    report_path: Path,
    inputs: dict[str, object],
    *,
    workers: int | None = None,
    progress_every: int = 25,
    progress_interval_seconds: float = 30.0,
    stream: TextIO | None = None,
) -> CampaignResult:
    """Run one already-selected shard and emit one evidence event stream."""

    if progress_every < 1:
        raise ValueError(
            "progress_every must be a positive integer"
        )

    if progress_interval_seconds <= 0:
        raise ValueError(
            "progress_interval_seconds must be positive"
        )

    if workers is None:
        workers = min(
            8,
            os.cpu_count() or 1,
        )

    if workers < 1:
        raise ValueError(
            "workers must be a positive integer"
        )

    engine_blob = _engine_blob(root)
    source_blobs = _source_blobs(
        root,
        work,
    )
    reporter = EventReporter(
        report_path,
        stream,
    )

    selected_keys = [
        list(mutant.key)
        for mutant in work
    ]

    killed = 0
    classified: list[mutation.Mutant] = []
    unclassified: list[mutation.Mutant] = []
    timings: dict[str, list[float]] = defaultdict(list)
    groups: dict[
        tuple[str, str],
        dict[str, int],
    ] = defaultdict(
        lambda: {
            "killed": 0,
            "classified_survivors": 0,
            "unclassified_survivors": 0,
        }
    )

    started = time.perf_counter()
    last_progress = started
    error_reported = False

    def emit_error(
        exc: BaseException,
    ) -> None:
        nonlocal error_reported

        if error_reported:
            return

        error_reported = True
        reporter.emit({
            "event": "campaign_error",
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
            "elapsed_seconds": (
                time.perf_counter()
                - started
            ),
        })

    try:
        reporter.emit({
            "event": "campaign_start",
            "engine_blob": engine_blob,
            "target_source_blobs": source_blobs,
            "inputs": dict(inputs),
            "selected_count": len(work),
            "selected_keys": selected_keys,
            "oracle_command": list(command),
        })

        completed = 0

        with ThreadPoolExecutor(
            max_workers=workers
        ) as pool:
            pending = {
                pool.submit(
                    _execute_one,
                    root,
                    mutant,
                    command,
                ): mutant
                for mutant in work
            }

            def current_target() -> str:
                for future, selected in pending.items():
                    if future.running():
                        return selected.target

                return next(
                    iter(pending.values())
                ).target

            def emit_progress(
                target: str,
                now: float,
            ) -> None:
                nonlocal last_progress

                reporter.emit({
                    "event": "progress",
                    "completed": completed,
                    "total": len(work),
                    "killed": killed,
                    "classified_survivors": len(
                        classified
                    ),
                    "unclassified_survivors": len(
                        unclassified
                    ),
                    "elapsed_seconds": (
                        now - started
                    ),
                    "current_target": target,
                })
                last_progress = now

            while pending:
                now = time.perf_counter()
                timeout = max(
                    0.0,
                    progress_interval_seconds
                    - (now - last_progress),
                )

                done, _ = wait(
                    pending,
                    timeout=timeout,
                    return_when=FIRST_COMPLETED,
                )
                now = time.perf_counter()

                if not done:
                    emit_progress(
                        current_target(),
                        now,
                    )
                    continue

                last_selected = None

                for future in done:
                    selected = pending.pop(
                        future
                    )
                    last_selected = selected

                    try:
                        mutant, dead, elapsed = (
                            future.result()
                        )
                    except BaseException as exc:
                        emit_error(exc)

                        for remaining in pending:
                            remaining.cancel()

                        raise

                    timings[
                        mutant.target
                    ].append(
                        elapsed
                    )
                    group = groups[
                        (
                            mutant.target,
                            mutant.kind,
                        )
                    ]

                    classification = None

                    if dead:
                        outcome = "killed"
                        killed += 1
                        group["killed"] += 1
                    else:
                        classification = (
                            classifications.get(
                                mutant.key
                            )
                        )

                        if classification is None:
                            outcome = (
                                "unclassified_survivor"
                            )
                            unclassified.append(
                                mutant
                            )
                            group[
                                "unclassified_survivors"
                            ] += 1
                        else:
                            outcome = (
                                "classified_survivor"
                            )
                            classified.append(
                                mutant
                            )
                            group[
                                "classified_survivors"
                            ] += 1

                    completed += 1
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
                        "elapsed_seconds": elapsed,
                        "source_blob": source_blobs[
                            mutant.target
                        ],
                        "engine_blob": engine_blob,
                    }

                    if classification is not None:
                        event["classification"] = (
                            classification[0]
                        )
                        event["reason"] = (
                            classification[1]
                        )

                    reporter.emit(event)

                    if (
                        completed
                        % progress_every
                        == 0
                        or completed == len(work)
                    ):
                        target = (
                            current_target()
                            if pending
                            else selected.target
                        )
                        emit_progress(
                            target,
                            time.perf_counter(),
                        )

                now = time.perf_counter()

                if (
                    pending
                    and (
                        now - last_progress
                        >= progress_interval_seconds
                    )
                ):
                    emit_progress(
                        current_target(),
                        now,
                    )

        elapsed_total = (
            time.perf_counter()
            - started
        )

        reporter.emit({
            "event": "campaign_complete",
            "completed": len(work),
            "total": len(work),
            "killed": killed,
            "classified_survivors": len(
                classified
            ),
            "unclassified_survivors": len(
                unclassified
            ),
            "elapsed_seconds": elapsed_total,
            "groups": _group_summary(groups),
            "target_timings": _timing_summary(
                timings
            ),
        })

        return CampaignResult(
            killed=killed,
            classified_survivors=tuple(
                classified
            ),
            unclassified_survivors=tuple(
                unclassified
            ),
            elapsed_seconds=elapsed_total,
        )

    except BaseException as exc:
        emit_error(exc)
        raise

    finally:
        reporter.close()
