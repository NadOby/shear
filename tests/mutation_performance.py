"""Where a mutation campaign spent its time, from its JSON Lines reports.

A diagnostic over the reports one or more shards wrote
(``mutation-report-batch-<b>-shard-<s>.jsonl``); it never gates anything.
Several reports are read as the shards of one campaign: the campaign's
wall time is that of its slowest shard and its CPU time is the sum of all.
Reports from before the verdict protocol carry no CPU, ``killed_by`` or
``stage`` fields; those are then reported as unknown, not guessed.

    python -m tests.mutation_performance mutation-report-*.jsonl
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path


def read(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)

    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def summarize(
    reports: dict[str, list[dict[str, object]]],
    slowest: int = 5,
) -> dict[str, object]:
    """Wall, CPU, outcomes and kill times over the given shard reports."""

    outcomes: Counter[str] = Counter()
    stages: Counter[str] = Counter()
    killers: Counter[str] = Counter()
    kill_times: list[float] = []
    every: list[tuple[float, str, str]] = []
    shards = []
    cpu_total = 0.0
    cpu_known = True
    not_run = 0
    incomplete = []

    for name, events in reports.items():
        done = [e for e in events if e.get("event") == "campaign_complete"]
        wall = float(done[-1]["elapsed_seconds"]) if done else None

        if not done:
            incomplete.append(name)

        shard_cpu = 0.0

        for event in events:
            if event.get("event") != "mutant_outcome":
                continue

            outcome = str(event["outcome"])
            seconds = float(event["elapsed_seconds"])  # type: ignore[arg-type]
            outcomes[outcome] += 1

            if event.get("executed") is False:
                not_run += 1
                continue

            every.append((seconds, outcome, "/".join(
                str(part) for part in event["key"][:2]  # type: ignore[index]
            )))

            if "cpu_seconds" in event:
                shard_cpu += float(event["cpu_seconds"])  # type: ignore[arg-type]
            else:
                cpu_known = False

            if outcome == "killed":
                kill_times.append(seconds)
                stages[str(event.get("stage", "unknown"))] += 1
                killers[str(event.get("killed_by", "unknown"))] += 1

        cpu_total += shard_cpu
        shards.append({
            "report": name,
            "wall_seconds": wall,
            "mutant_cpu_seconds": shard_cpu,
        })

    walls = [s["wall_seconds"] for s in shards if s["wall_seconds"]]
    result: dict[str, object] = {
        "shards": shards,
        "incomplete_reports": incomplete,
        "campaign_wall_seconds": max(walls) if walls else None,
        "sum_of_shard_wall_seconds": sum(walls) if walls else None,
        "mutant_cpu_seconds": cpu_total if cpu_known else None,
        "outcomes": dict(sorted(outcomes.items())),
        "not_run_pinned": not_run,
        "slowest": [
            {"seconds": s, "outcome": o, "mutant": m}
            for s, o, m in sorted(every, reverse=True)[:slowest]
        ],
        "kill_stage": dict(stages),
        "killed_by": dict(killers.most_common(10)),
    }

    if kill_times:
        result["kill_seconds"] = {
            "count": len(kill_times),
            "mean": statistics.fmean(kill_times),
            "median": statistics.median(kill_times),
            "p90": _percentile(kill_times, 0.9),
            "max": max(kill_times),
            "total": sum(kill_times),
        }

    return result


def render(result: dict[str, object]) -> str:
    wall = result["campaign_wall_seconds"]
    cpu = result["mutant_cpu_seconds"]
    out = [
        "mutation performance (diagnostic)",
        f"campaign wall (slowest shard): "
        f"{'unknown' if wall is None else f'{wall:.1f}s'}; "
        f"sum of shard walls: "
        f"{result['sum_of_shard_wall_seconds'] or 0:.1f}s; "
        f"mutant CPU: {'unknown' if cpu is None else f'{cpu:.1f}s'}",
        "outcomes: "
        + ", ".join(f"{k}={v}" for k, v in result["outcomes"].items()),  # type: ignore[attr-defined]
    ]

    if result["not_run_pinned"]:
        out.append(
            f"reviewed survivors not re-run: {result['not_run_pinned']}"
        )

    for name in result["incomplete_reports"]:  # type: ignore[attr-defined]
        out.append(f"INCOMPLETE report (no campaign_complete): {name}")

    kills = result.get("kill_seconds")

    if kills:
        out.append(
            "kill time: "
            f"mean {kills['mean']:.1f}s, median {kills['median']:.1f}s, "
            f"p90 {kills['p90']:.1f}s, max {kills['max']:.1f}s "
            f"over {kills['count']} kills"
        )

    if result["kill_stage"]:
        out.append(
            "killed in: "
            + ", ".join(
                f"{k}={v}" for k, v in result["kill_stage"].items()  # type: ignore[attr-defined]
            )
        )

    out.append("slowest mutants:")

    for entry in result["slowest"]:  # type: ignore[attr-defined]
        out.append(
            f"  {entry['seconds']:8.1f}s {entry['outcome']:<22} "
            f"{entry['mutant']}"
        )

    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tests.mutation_performance",
        description="Summarize mutation campaign reports (a diagnostic).",
    )
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    result = summarize({str(p): read(p) for p in args.reports})
    print(render(result))

    if args.json is not None:
        args.json.write_text(json.dumps(result, indent=1), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
