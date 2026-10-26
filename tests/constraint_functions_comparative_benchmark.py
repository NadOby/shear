"""GH-123 comparative warm-latency evidence – actual candidate vs incumbent.

Run from the repository root, not from a checked-out tests directory:

    python -m tests.constraint_functions_comparative_benchmark \
        --output-dir /tmp/gh123-comparison

Produces raw, per-block JSONL data, metadata and stratified-bootstrap
summaries. This is *warm semantic evaluation* only, not the full GH-123
performance or resource contract. In particular, separate cold compilation,
first-use, memory, runtime-boundary and mechanism evidence remains required.

No benchmark run may change the frozen GH-123 acceptance expectations.
This module is not named test_*, so ordinary CI does not silently run a
multi-minute benchmark or change its explicit test-lane inventory.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import traceback
import sys
from time import perf_counter_ns, process_time_ns

from shear import ConstraintResult, EvaluationContext, Evaluator
from shear import canonical_serialize, canonicalize
from tests.constraint_function_acceptance import CandidateInput
from tests.constraint_function_oracle import all_fixed_vectors
from tests.constraint_functions_complete_acceptance import candidate_execution_guard
from tests import constraint_functions_complete_candidate as candidate


# Frozen, named cases are selected before looking at candidate latency.
# All nine forms, all three verdicts, bounded/unbounded evaluation,
# short-circuiting and registered/missing Externals are represented.
REPRESENTATIVE = (
    "int_kind", "range_outside", "length_codepoints",
    "one_of_present", "role_present", "external_absent",
    "external_satisfied", "not_two", "pair_three", "pair_two",
    "empty_and_one", "empty_or_one", "deduplicated_and",
    "and_short_circuit_first", "or_late_satisfaction_exhausted",
)

PROTOCOL = {
    "processes": 3,
    "warmups_per_path": 30,
    "blocks_per_process": 40,
    "target_block_ns": 20_000_000,
    "bootstrap_replicates": 2000,
    "ceiling": 1000,
}


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True,
        text=True, check=True,
    )
    return result.stdout.strip()


def _digest(value: object) -> str:
    return hashlib.sha256(
        canonical_serialize(canonicalize(value))
    ).hexdigest()


def _cases(suite: str) -> list[dict]:
    vectors = all_fixed_vectors()
    names = {vector.name: vector for vector in vectors}
    if len(names) != len(vectors):
        raise RuntimeError("duplicate fixed workload name")
    missing = set(REPRESENTATIVE) - set(names)
    if missing:
        raise RuntimeError(f"pinned representative workloads missing: {missing}")
    selected = [names[name] for name in REPRESENTATIVE]
    if suite == "full":
        selected = list(vectors)

    rows = [dict(
        name=v.name,
        expression=v.expression,
        subject=v.subject,
        budget=v.budget,
        externals=tuple(v.externals),
        expected=v.expected,
        origin="Task24 frozen fixed vector",
    ) for v in selected]
    if suite in ("representative-scaling", "full"):
        for count in (8, 64, 256):
            rows.append(dict(
                name=f"all_of_distinct_{count}",
                expression=("all_of", *(
                    ("int_range", -i, count + i)
                    for i in range(count)
                )),
                subject=5, budget=None, externals=(),
                expected="satisfied", origin="pinned size scaling",
            ))
    if suite == "smoke":
        rows = rows[:2]
    return rows


def _context(registrations: tuple, budget: int | None) -> EvaluationContext:
    evaluators = {
        name: Evaluator(lambda _subject, v=verdict: ConstraintResult(v))
        for name, verdict in registrations
    }
    return EvaluationContext(evaluators, budget)


def _prepare(row: dict):
    """Different interfaces, same semantic declaration and subject.

    Incumbent: public Constraint.evaluate(subject, EvaluationContext).
    Candidate: unmodified semantic(CandidateInput), including canonical
    input preparation and *actual* restricted VM invocation on each call.
    No patched prepare_semantic, bound-only evaluator or Python fallback.
    """
    expression = row["expression"]
    subject = candidate._materialize_subject(row["subject"])
    constraint = candidate._constraint(expression)
    context = _context(row["externals"], row["budget"])
    case = CandidateInput(
        expression, row["subject"], row["budget"], row["externals"]
    )

    def incumbent() -> str:
        return constraint.evaluate(subject, context).value

    def challenger() -> str:
        observation = candidate.semantic(case)
        if observation.incumbent_calls != 0:
            raise RuntimeError("candidate reported incumbent fallback")
        return observation.outcome

    row["canonical_input_digest"] = _digest((
        constraint, subject, row["budget"], row["externals"],
    ))
    return incumbent, challenger


def _checked_call(function, expected: str) -> None:
    outcome = function()
    if outcome != expected:
        raise RuntimeError(
            f"semantic mismatch: expected {expected!r}, got {outcome!r}"
        )


def _time_batch(function, count: int, expected: str) -> tuple[int, int]:
    cpu_start = process_time_ns()
    wall_start = perf_counter_ns()
    for _ in range(count):
        _checked_call(function, expected)
    elapsed = perf_counter_ns() - wall_start
    return elapsed, process_time_ns() - cpu_start


def _calibrate(function, expected, target_ns, max_batch) -> tuple[int, int]:
    count = 1
    while True:
        elapsed, _ = _time_batch(function, count, expected)
        if elapsed >= target_ns:
            return count, elapsed
        if count >= max_batch:
            raise RuntimeError(
                "timing resolution unavailable: maximum batch too short"
            )
        count = min(max_batch, count * 2)


def _worker(args) -> int:
    if _git_head() != args.pinned_head:
        raise RuntimeError("HEAD changed between controller and worker")
    randomizer = random.Random(args.seed + args.worker * 104729)
    destination = Path(args.output_dir)
    output = destination / f"blocks-process-{args.worker}.jsonl"
    environment = {
        "worker": args.worker,
        "pid": os.getpid(),
        "head": args.pinned_head,
        "python": sys.version,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "hash_seed": os.getenv("PYTHONHASHSEED"),
        "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "compiler_generation": candidate._PRIVATE_COMPILER_GENERATION,
    }
    (destination / f"environment-{args.worker}.json").write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with output.open("w", encoding="utf-8") as sink:
        for row in _cases(args.suite):
            name = row["name"]
            try:
                incumbent, challenger = _prepare(row)
                # An independent, untimed admitted-machine witness checks
                # real restricted VM execution before timing the unchanged
                # production path without instrumentation overhead.
                with candidate_execution_guard(
                    frozenset({candidate.REGISTERED_ENTRY})
                ) as opened:
                    _checked_call(challenger, row["expected"])
                if not opened:
                    raise RuntimeError("candidate failed authenticated VM witness")
                for _ in range(args.warmups):
                    _checked_call(incumbent, row["expected"])
                    _checked_call(challenger, row["expected"])
                batch_inc, measured_inc = _calibrate(
                    incumbent, row["expected"], args.target_ns,
                    args.max_batch,
                )
                batch_can, measured_can = _calibrate(
                    challenger, row["expected"], args.target_ns,
                    args.max_batch,
                )
                # Independent calibration: never use identical invocation
                # counts if one path needs more work for clock resolution.
                for block in range(args.blocks):
                    first = "incumbent" if block % 2 == 0 else "candidate"
                    if randomizer.randrange(2):
                        first = "candidate" if first == "incumbent" else "incumbent"
                    order = (first, "candidate" if first == "incumbent" else "incumbent")
                    result = {}
                    for path in order:
                        function = incumbent if path == "incumbent" else challenger
                        batch = batch_inc if path == "incumbent" else batch_can
                        wall_ns, cpu_ns = _time_batch(
                            function, batch, row["expected"]
                        )
                        result[path] = dict(
                            batch=batch, wall_ns=wall_ns, cpu_ns=cpu_ns,
                            wall_per_call_ns=wall_ns / batch,
                            cpu_per_call_ns=cpu_ns / batch,
                        )
                    sink.write(json.dumps(dict(
                        kind="paired_block", process=args.worker,
                        workload=name, block=block, order=order,
                        input_digest=row["canonical_input_digest"],
                        origin=row["origin"], expected=row["expected"],
                        budget=row["budget"],
                        static_external_count=len(row["externals"]),
                        calibrated_ns={"incumbent": measured_inc,
                                       "candidate": measured_can},
                        **result,
                    ), sort_keys=True) + "\n")
                    sink.flush()
            except BaseException as exc:
                sink.write(json.dumps(dict(
                    kind="failure", process=args.worker, workload=name,
                    error_type=type(exc).__name__, error=str(exc),
                    traceback=traceback.format_exc(),
                ), sort_keys=True) + "\n")
                sink.flush()
                # Preserve failed workload independently. Do not turn an
                # unsupported workload or model fault into a latency value.
    return 0


def _percentile(values, p: float) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * p) - 1]


def _ratio(rows: list[dict], statistic) -> float | None:
    incumbent = statistic([r["incumbent"]["wall_per_call_ns"] for r in rows])
    candidate_latency = statistic([r["candidate"]["wall_per_call_ns"] for r in rows])
    return candidate_latency / incumbent if incumbent > 0 else None


def _summary(rows, bootstrap_replicates, seed, qualifying) -> dict:
    by_process = defaultdict(list)
    for row in rows:
        by_process[row["process"]].append(row)
    samples = {path: [r[path]["wall_per_call_ns"] for r in rows]
               for path in ("candidate", "incumbent")}
    stats = {
        path: {
            "median_ns": statistics.median(v),
            "p95_ns": _percentile(v, .95),
            "min_ns": min(v), "max_ns": max(v),
            "spread_ns": max(v) - min(v),
            "observations": len(v),
            "timed_invocations": sum(r[path]["batch"] for r in rows),
        }
        for path, v in samples.items()
    }
    rng = random.Random(seed)
    replicates = {"median": [], "p95": []}
    stat_functions = {"median": statistics.median,
                      "p95": lambda v: _percentile(v, .95)}
    # Resample whole *pairs* within each process. Never pool first and
    # thereby erase the fresh-process strata or pair correlation.
    for _ in range(bootstrap_replicates):
        picked = []
        for worker in sorted(by_process):
            sample = by_process[worker]
            picked.extend(sample[rng.randrange(len(sample))]
                          for _ in sample)
        for name, function in stat_functions.items():
            ratio = _ratio(picked, function)
            if ratio is not None:
                replicates[name].append(ratio)

    ratios = {}
    for name, function in stat_functions.items():
        point = _ratio(rows, function)
        draws = sorted(replicates[name])
        if not draws or point is None:
            ratios[name] = {"ratio": None, "ci95": None}
        else:
            ratios[name] = {
                "ratio": point,
                "ci95": [draws[int(.025 * (len(draws) - 1))],
                         draws[int(.975 * (len(draws) - 1))]],
            }

    process_variation = {
        str(worker): {
            path: {
                "median_ns": statistics.median(
                    r[path]["wall_per_call_ns"] for r in blocks
                ),
                "p95_ns": _percentile(
                    [r[path]["wall_per_call_ns"] for r in blocks], .95
                ),
            } for path in ("candidate", "incumbent")
        } for worker, blocks in by_process.items()
    }
    ratios_available = all(
        ratio["ratio"] is not None for ratio in ratios.values()
    )
    ceiling_ok = ratios_available and all(
        ratio["ratio"] <= PROTOCOL["ceiling"]
        for ratio in ratios.values()
    )
    return {
        "status": (
            "nonqualifying_exploratory" if not qualifying else
            "insufficient_timing_resolution" if not ratios_available else
            "within_initial_warm_ceiling" if ceiling_ok else
            "above_initial_warm_ceiling"
        ),
        "qualifying_sampling": qualifying,
        "stats": stats, "ratios": ratios,
        "process_variation": process_variation,
        "bootstrap_replicates": bootstrap_replicates,
    }


def _controller(args) -> int:
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    head = _git_head()
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    metadata = dict(
        head=head, benchmark_sha256=script_hash,
        protocol=PROTOCOL, invocation=vars(args),
        workload_manifest=[{
            "name": row["name"],
            "expression": repr(row["expression"]),
            "subject": repr(row["subject"]),
            "budget": row["budget"],
            "externals": repr(row["externals"]),
            "expected": row["expected"],
            "origin": row["origin"],
        } for row in _cases(args.suite)],
        limitations=[
            "Warm candidate.semantic adapter versus incumbent Constraint.evaluate public path",
            "Candidate includes declaration normalization on each adapter call",
            "Separate cold preparation, first use, runtime writes, memory, and mechanism accounting unmeasured",
            "Static External verdicts; no live host callbacks measured",
            "One untimed authenticated VM entry is verified before each workload",
            "Scaling is optional unless representative-scaling/full suite selected",
        ],
    )
    (output / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for worker in range(args.processes):
        cmd = [
            sys.executable, "-m", "tests.constraint_functions_comparative_benchmark",
            "--worker", str(worker), "--pinned-head", head,
            "--output-dir", str(output), "--suite", args.suite,
            "--warmups", str(args.warmups), "--blocks", str(args.blocks),
            "--bootstrap", str(args.bootstrap), "--processes", str(args.processes),
            "--target-ms", str(args.target_ms),
            "--max-batch", str(args.max_batch),
            "--seed", str(args.seed),
        ]
        subprocess.run(cmd, check=True, env={
            **os.environ, "PYTHONHASHSEED": "0",
        })
    loaded = defaultdict(list)
    failed = []
    for worker in range(args.processes):
        for line in (output / f"blocks-process-{worker}.jsonl").read_text(
            encoding="utf-8"
        ).splitlines():
            entry = json.loads(line)
            if entry["kind"] == "failure":
                failed.append(entry)
            else:
                loaded[entry["workload"]].append(entry)

    qualifying_sampling = (
        args.processes >= 3 and args.warmups >= 30 and
        args.blocks >= 40 and args.bootstrap >= 2000 and
        args.target_ms >= 20
    )
    summary = dict(
        head=head, qualifying_sampling=qualifying_sampling,
        workloads={}, failures=failed,
        complete=True,
    )
    requested_names = [r["name"] for r in _cases(args.suite)]
    for name in requested_names:
        rows = loaded[name]
        valid = (
            len(rows) == args.processes * args.blocks
            and {r["process"] for r in rows} == set(range(args.processes))
            and all(sum(r["process"] == p for r in rows) == args.blocks
                    for p in range(args.processes))
            and len({r["input_digest"] for r in rows}) == 1
        )
        if not valid:
            summary["complete"] = False
            summary["workloads"][name] = {
                "status": "missing_or_failed_samples", "observations": len(rows),
            }
            continue
        summary["workloads"][name] = _summary(
            rows, args.bootstrap, args.seed ^ int(hashlib.sha256(
                name.encode()
            ).hexdigest()[:8], 16), qualifying_sampling,
        )
    if failed:
        summary["complete"] = False
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "head": head, "complete": summary["complete"],
        "failed": len(failed),
        "workloads": {k: v["status"]
                      for k, v in summary["workloads"].items()},
        "output": str(output),
    }, indent=2, sort_keys=True))
    return 0 if summary["complete"] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--suite", choices=(
        "smoke", "representative", "representative-scaling", "full",
    ), default="representative")
    parser.add_argument("--processes", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=30)
    parser.add_argument("--blocks", type=int, default=40)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--target-ms", type=float, default=20)
    parser.add_argument("--max-batch", type=int, default=1 << 20)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--worker", type=int, default=None,
                        help=argparse.SUPPRESS)
    parser.add_argument("--pinned-head", default=None,
                        help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not (args.processes > 0 and args.warmups >= 0 and
            args.blocks > 0 and args.bootstrap > 0 and
            args.target_ms > 0 and args.max_batch >= 1):
        parser.error("invalid sampling parameters")
    args.target_ns = math.ceil(args.target_ms * 1_000_000)
    if args.worker is None:
        return _controller(args)
    if not args.pinned_head or not 0 <= args.worker < args.processes:
        parser.error("worker requires valid --pinned-head and --worker")
    return _worker(args)


if __name__ == "__main__":
    raise SystemExit(main())
