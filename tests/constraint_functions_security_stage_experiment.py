"""GH-123 authenticated execution stage profiling, with no security bypass.

Place at tests/constraint_functions_security_stage_experiment.py and run:

    python -m tests.constraint_functions_security_stage_experiment \
        --output-dir /tmp/gh123-security-stages

Each observation is ONE complete invocation of the unchanged
RestrictedExecutor.run. The same generic and form-set-specialized admitted
programs from constraint_functions_size_experiment are used. Spies call the
original methods exactly once, propagate their exceptions, and do not cache
or skip a check. Preparation and initial authenticated first use are outside
the sampled warm boundary. The uninstrumented control estimates the overhead
added by instrumentation; it is not an independently calibrated benchmark.

Times are inclusive unless explicitly called residual. In particular,
'machine_run' contains 'resolver', and 'verify'/'validate_chunk' are nested
within the parent stage. Therefore they must NOT all be added together.
This is exploratory security-cost attribution, NOT GH-123 acceptance evidence.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager, ExitStack
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import traceback
from time import perf_counter_ns, process_time_ns
from unittest.mock import patch

from shear.hosted_bootstrap import restricted, restricted_policy
from shear.hosted_bootstrap.artifacts import Artifact
from tests.constraint_functions_comparative_benchmark import (
    _git_head, _percentile,
)
from tests import constraint_functions_size_experiment as size


# Pin discriminating cases before inspecting profiling results. Exact 8/64/256
# total-node cases are imported from the corrected size experiment.
DEFAULT_CASES = (
    "int_kind", "external_absent", "one_of_present", "pair_three",
    "role_present",
)
SCALING_CASES = ("all_of_nodes_8", "all_of_nodes_64", "all_of_nodes_256")
STAGES = ("deployment_check", "preflight", "machine_run", "resolver")
MEASURES = (
    "total_wall_ns", "total_cpu_ns", "deployment_check_wall_ns",
    "preflight_wall_ns", "machine_run_wall_ns", "resolver_wall_ns",
    "vm_without_resolver_wall_ns", "outside_major_stages_wall_ns",
    "verify_wall_ns", "validate_chunk_wall_ns",
)


def _cases(suite: str, requested: tuple[str, ...]) -> list[dict]:
    full = size._cases("representative-scaling")
    by_name = {row["name"]: row for row in full}
    if len(by_name) != len(full):
        raise RuntimeError("duplicate experimental workload")
    if requested:
        names = requested
    elif suite == "smoke":
        names = DEFAULT_CASES[:1]
    elif suite == "representative":
        names = DEFAULT_CASES
    elif suite == "scaling":
        names = SCALING_CASES
    elif suite == "all":
        names = DEFAULT_CASES + SCALING_CASES
    else:
        raise ValueError(f"unknown suite: {suite}")
    unknown = set(names) - set(by_name)
    if unknown:
        raise ValueError(f"unknown workloads: {sorted(unknown)!r}")
    if len(names) != len(set(names)):
        raise ValueError("duplicate --case")
    return [by_name[name] for name in names]


class _StageProbe:
    """Instrumentation only; every patched function calls original once."""

    def __init__(self):
        self.elapsed_wall = Counter()
        self.elapsed_cpu = Counter()
        self.calls = Counter()
        self.verify_by_phase = Counter()
        self.validate_by_phase = Counter()
        self.permitted_count = None
        self.phase = "outside"

    @contextmanager
    def _stage(self, name: str):
        parent = self.phase
        self.phase = name
        started_wall, started_cpu = perf_counter_ns(), process_time_ns()
        self.calls[name] += 1
        try:
            yield
        finally:
            self.elapsed_wall[name] += perf_counter_ns() - started_wall
            self.elapsed_cpu[name] += process_time_ns() - started_cpu
            self.phase = parent

    def run(self, operation, expected: str) -> dict:
        original_check = restricted.RestrictedExecutor._check_deployment
        original_preflight = restricted.preflight
        original_machine_run = restricted.machine.run
        original_resolve = restricted._PinnedResolver.for_version
        original_verify = Artifact.verify
        original_validate = restricted.validate_chunk
        original_policy_validate = restricted_policy.validate_chunk

        def check(executor, deployment):
            with self._stage("deployment_check"):
                return original_check(executor, deployment)

        def preflight(*args, **kwargs):
            with self._stage("preflight"):
                result = original_preflight(*args, **kwargs)
                self.permitted_count = len(result)
                return result

        def machine_run(*args, **kwargs):
            with self._stage("machine_run"):
                return original_machine_run(*args, **kwargs)

        def resolve(resolver, version, entity, owner):
            with self._stage("resolver"):
                return original_resolve(resolver, version, entity, owner)

        def verify(artifact):
            phase = self.phase
            started_wall, started_cpu = perf_counter_ns(), process_time_ns()
            try:
                return original_verify(artifact)
            finally:
                self.verify_by_phase[phase] += 1
                self.elapsed_wall["verify"] += perf_counter_ns() - started_wall
                self.elapsed_cpu["verify"] += process_time_ns() - started_cpu

        def validate_chunk(*args, **kwargs):
            phase = self.phase
            started_wall, started_cpu = perf_counter_ns(), process_time_ns()
            try:
                return original_validate(*args, **kwargs)
            finally:
                self.validate_by_phase[phase] += 1
                self.elapsed_wall["validate_chunk"] += (
                    perf_counter_ns() - started_wall
                )
                self.elapsed_cpu["validate_chunk"] += (
                    process_time_ns() - started_cpu
                )

        def policy_validate_chunk(*args, **kwargs):
            phase = self.phase
            started_wall, started_cpu = perf_counter_ns(), process_time_ns()
            try:
                return original_policy_validate(*args, **kwargs)
            finally:
                self.validate_by_phase[phase] += 1
                self.elapsed_wall["validate_chunk"] += (
                    perf_counter_ns() - started_wall
                )
                self.elapsed_cpu["validate_chunk"] += (
                    process_time_ns() - started_cpu
                )

        # All patches are observer wrappers, NOT mock return values. Avoid
        # patching RestrictedExecutor.run or artifact/policy data structures.
        with ExitStack() as stack:
            stack.enter_context(patch.object(
                restricted.RestrictedExecutor, "_check_deployment", check,
            ))
            stack.enter_context(patch.object(restricted, "preflight", preflight))
            stack.enter_context(patch.object(
                restricted.machine, "run", machine_run,
            ))
            stack.enter_context(patch.object(
                restricted._PinnedResolver, "for_version", resolve,
            ))
            stack.enter_context(patch.object(Artifact, "verify", verify))
            stack.enter_context(patch.object(
                restricted, "validate_chunk", validate_chunk,
            ))
            stack.enter_context(patch.object(
                restricted_policy, "validate_chunk", policy_validate_chunk,
            ))
            started_wall, started_cpu = perf_counter_ns(), process_time_ns()
            result = operation()
            total_wall = perf_counter_ns() - started_wall
            total_cpu = process_time_ns() - started_cpu

        if result != expected:
            raise AssertionError(
                f"instrumented semantic divergence: {result!r} != {expected!r}"
            )
        if any(self.calls[name] != 1 for name in STAGES[:3]):
            raise AssertionError(f"missing/duplicate major stages: {self.calls}")
        if self.calls["resolver"] < 1:
            raise AssertionError("instrumented VM never resolved admitted code")
        if self.permitted_count is None or self.permitted_count < 1:
            raise AssertionError("preflight returned no reachable permitted nodes")
        if self.verify_by_phase["deployment_check"] < 1:
            raise AssertionError("deployment verification was not observed")
        if self.validate_by_phase["preflight"] < 1:
            raise AssertionError("preflight did not validate actual emitted code")
        if self.validate_by_phase["resolver"] < 1:
            raise AssertionError("pinned resolver did not validate actual code")

        def residual(total, subtract):
            return total - sum(subtract)

        timings = {
            "total_wall_ns": total_wall,
            "total_cpu_ns": total_cpu,
            "verify_wall_ns": self.elapsed_wall["verify"],
            "verify_cpu_ns": self.elapsed_cpu["verify"],
            "validate_chunk_wall_ns": self.elapsed_wall["validate_chunk"],
            "validate_chunk_cpu_ns": self.elapsed_cpu["validate_chunk"],
        }
        for stage in STAGES:
            timings[f"{stage}_wall_ns"] = self.elapsed_wall[stage]
            timings[f"{stage}_cpu_ns"] = self.elapsed_cpu[stage]
        for unit in ("wall", "cpu"):
            timings[f"vm_without_resolver_{unit}_ns"] = residual(
                self.elapsed_wall["machine_run"] if unit == "wall"
                else self.elapsed_cpu["machine_run"],
                [self.elapsed_wall["resolver"] if unit == "wall"
                 else self.elapsed_cpu["resolver"]],
            )
            elapsed = self.elapsed_wall if unit == "wall" else self.elapsed_cpu
            timings[f"outside_major_stages_{unit}_ns"] = residual(
                timings[f"total_{unit}_ns"],
                [elapsed[x] for x in STAGES[:3]],
            )
        return {
            **timings,
            "stage_calls": dict(self.calls),
            "artifact_verify_calls": sum(self.verify_by_phase.values()),
            "verify_by_phase": dict(self.verify_by_phase),
            "chunk_validation_calls": sum(self.validate_by_phase.values()),
            "validate_by_phase": dict(self.validate_by_phase),
            "preflight_permitted_nodes": self.permitted_count,
        }


def _untraced(operation, expected: str) -> dict:
    started_wall, started_cpu = perf_counter_ns(), process_time_ns()
    outcome = operation()
    wall = perf_counter_ns() - started_wall
    cpu = process_time_ns() - started_cpu
    if outcome != expected:
        raise AssertionError("untraced semantic divergence")
    return {"wall_ns": wall, "cpu_ns": cpu}


def _observe_pair(index: int, rng, functions, expected: str) -> dict:
    labels = ["generic", "specialized"]
    rng.shuffle(labels)
    observations = {}
    for label in labels:
        function = functions[label]
        if index % 2:
            profile = _StageProbe().run(function, expected)
            control = _untraced(function, expected)
        else:
            control = _untraced(function, expected)
            profile = _StageProbe().run(function, expected)
        observations[label] = {
            "untraced_control": control,
            "instrumented": profile,
        }
    return {
        "execution_order": labels,
        "instrumentation_control_order": (
            "profiled_then_untraced" if index % 2 else
            "untraced_then_profiled"
        ),
        **observations,
    }


def _worker(args) -> int:
    if _git_head() != args.pinned_head:
        raise RuntimeError("HEAD changed between controller and worker")
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / f"environment-{args.worker}.json").write_text(
        json.dumps({
            "head": args.pinned_head,
            "worker": args.worker,
            "pid": os.getpid(),
            "python": sys.version,
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "hash_seed": os.getenv("PYTHONHASHSEED"),
            "experiment_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    rng = random.Random(args.seed + args.worker * 104729)
    specialized_cache = {}
    failed = False
    with (destination / f"samples-process-{args.worker}.jsonl").open(
        "w", encoding="utf-8"
    ) as sink:
        for row in _cases(args.suite, tuple(args.case)):
            try:
                generic, specialized, info = size._prepare(
                    row, specialized_cache,
                )
                functions = {"generic": generic, "specialized": specialized}
                for _ in range(args.warmups):
                    for function in functions.values():
                        if function() != row["expected"]:
                            raise RuntimeError("untraced warmup semantic mismatch")
                for index in range(args.samples):
                    sample = _observe_pair(
                        index, rng, functions, row["expected"],
                    )
                    sink.write(json.dumps({
                        "kind": "sample", "process": args.worker,
                        "workload": row["name"], "index": index,
                        "expected": row["expected"], **info, **sample,
                    }, sort_keys=True) + "\n")
                    sink.flush()
            except BaseException as exc:
                failed = True
                sink.write(json.dumps({
                    "kind": "failure", "process": args.worker,
                    "workload": row["name"],
                    "error_type": type(exc).__name__,
                    "error": str(exc), "traceback": traceback.format_exc(),
                }, sort_keys=True) + "\n")
                sink.flush()
    return 1 if failed else 0


def _statistic(rows, label: str, key: str, *, profiled=True):
    source = "instrumented" if profiled else "untraced_control"
    values = [r[label][source][key] for r in rows]
    return {
        "median_ns": statistics.median(values),
        "p95_individual_call_ns": _percentile(values, .95),
        "minimum_ns": min(values),
        "maximum_ns": max(values),
    }


def _bootstrap_ratio(rows, field: str, replicates: int, seed: int) -> dict:
    """Resample individual paired observations within their process strata."""
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["process"]].append(row)

    def ratio(picked):
        generic = statistics.median([
            r["generic"]["instrumented"][field] for r in picked
        ])
        narrowed = statistics.median([
            r["specialized"]["instrumented"][field] for r in picked
        ])
        return narrowed / generic if generic > 0 else None

    rng = random.Random(seed)
    point = ratio(rows)
    draws = []
    for _ in range(replicates):
        sampled = []
        for process in sorted(grouped):
            cases = grouped[process]
            sampled.extend(cases[rng.randrange(len(cases))]
                           for _ in cases)
        value = ratio(sampled)
        if value is not None:
            draws.append(value)
    if point is None or not draws:
        return {"specialized_over_generic": None, "ci95": None}
    draws.sort()
    return {
        "specialized_over_generic": point,
        "ci95": [draws[int(.025 * (len(draws) - 1))],
                 draws[int(.975 * (len(draws) - 1))]],
    }


def _summarize(rows, bootstrap: int, seed: int) -> dict:
    metrics = {}
    for label in ("generic", "specialized"):
        metrics[label] = {
            "artifact_count": rows[0][f"{label}_artifacts"],
            "control": _statistic(
                rows, label, "wall_ns", profiled=False,
            ),
            "instrumented": {
                field: _statistic(rows, label, field)
                for field in MEASURES
            },
            "counts": {
                name: {
                    "median": statistics.median(
                        r[label]["instrumented"][name] for r in rows
                    ),
                    "range": [
                        min(r[label]["instrumented"][name] for r in rows),
                        max(r[label]["instrumented"][name] for r in rows),
                    ],
                }
                for name in (
                    "artifact_verify_calls", "chunk_validation_calls",
                    "preflight_permitted_nodes",
                )
            },
            "verify_by_phase_median": {
                phase: statistics.median(
                    r[label]["instrumented"]["verify_by_phase"].get(phase, 0)
                    for r in rows
                ) for phase in ("deployment_check", "preflight", "resolver")
            },
            "validation_by_phase_median": {
                phase: statistics.median(
                    r[label]["instrumented"]["validate_by_phase"].get(phase, 0)
                    for r in rows
                ) for phase in ("deployment_check", "preflight", "resolver")
            },
            "resolver_calls_median": statistics.median(
                r[label]["instrumented"]["stage_calls"].get("resolver", 0)
                for r in rows
            ),
            "process_variation": {
                str(process): {
                    "median_instrumented_total_wall_ns": statistics.median(
                        r[label]["instrumented"]["total_wall_ns"]
                        for r in rows if r["process"] == process
                    ),
                    "median_untraced_wall_ns": statistics.median(
                        r[label]["untraced_control"]["wall_ns"]
                        for r in rows if r["process"] == process
                    ),
                } for process in sorted({r["process"] for r in rows})
            },
        }
    ratios = {}
    for field in (
        "total_wall_ns", "deployment_check_wall_ns", "preflight_wall_ns",
        "resolver_wall_ns", "vm_without_resolver_wall_ns",
    ):
        ratios[field] = _bootstrap_ratio(
            rows, field, bootstrap,
            seed ^ int(hashlib.sha256(field.encode()).hexdigest()[:8], 16),
        )
    return {
        "observations": len(rows),
        "input_digest": rows[0]["input_digest"],
        "forms": rows[0]["forms"],
        "metrics": metrics,
        "ratios": ratios,
        "interpretation": (
            "instrumented individual complete invocations; inclusive times; "
            "machine_run includes resolver; vm_without_resolver is a "
            "difference, not an independently timed VM kernel"
        ),
    }


def _controller(args) -> int:
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    head = _git_head()
    workload_list = _cases(args.suite, tuple(args.case))
    (destination / "metadata.json").write_text(json.dumps({
        "head": head,
        "experiment_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        "invocation": {k: v for k, v in vars(args).items()},
        "workloads": [{"name": row["name"], "expression": repr(row["expression"]),
                       "budget": row["budget"], "expected": row["expected"]}
                      for row in workload_list],
        "scope": "warm prepared authenticated RestrictedExecutor.run only",
        "limitations": [
            "not a full candidate.semantic comparison with preparation costs",
            "instrumentation wrappers add time within measured stages",
            "per-call stage times are inclusive and not all additive",
            "VM-exclusive-resolver is a subtraction, not direct kernel timing",
            "not GH-123 warm timing-block acceptance evidence",
            "static registered Externals, not live host continuations",
        ],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return_codes = []
    for worker in range(args.processes):
        cmd = [
            sys.executable, "-m",
            "tests.constraint_functions_security_stage_experiment",
            "--output-dir", str(destination),
            "--pinned-head", head, "--worker", str(worker),
            "--suite", args.suite, "--processes", str(args.processes),
            "--samples", str(args.samples), "--warmups", str(args.warmups),
            "--bootstrap", str(args.bootstrap), "--seed", str(args.seed),
        ]
        for name in args.case:
            cmd.extend(("--case", name))
        proc = subprocess.run(cmd, check=False, env={
            **os.environ, "PYTHONHASHSEED": "0",
        })
        return_codes.append(proc.returncode)

    grouped = defaultdict(list)
    failures = []
    for worker in range(args.processes):
        file = destination / f"samples-process-{worker}.jsonl"
        if not file.exists():
            failures.append({"worker": worker, "error": "missing worker output"})
            continue
        for line in file.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record["kind"] == "sample":
                grouped[record["workload"]].append(record)
            else:
                failures.append(record)

    summary = {
        "head": head, "complete": not failures and all(
            code == 0 for code in return_codes
        ), "worker_return_codes": return_codes,
        "failures": failures, "workloads": {},
    }
    for row in workload_list:
        name = row["name"]
        observations = grouped[name]
        valid = (
            len(observations) == args.processes * args.samples
            and all(sum(r["process"] == p for r in observations) == args.samples
                    for p in range(args.processes))
            and len({r["input_digest"] for r in observations}) == 1
            and len({r["generic_artifacts"] for r in observations}) == 1
            and len({r["specialized_artifacts"] for r in observations}) == 1
        )
        if not valid:
            summary["complete"] = False
            summary["workloads"][name] = {
                "status": "incomplete_or_inconsistent",
                "observations": len(observations),
            }
            continue
        seed = args.seed ^ int(hashlib.sha256(name.encode()).hexdigest()[:8], 16)
        summary["workloads"][name] = _summarize(
            observations, args.bootstrap, seed,
        )
    (destination / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "head": head, "complete": summary["complete"],
        "failures": len(summary["failures"]),
        "workloads": {name: data.get("status", "profiled")
                      for name, data in summary["workloads"].items()},
        "output_dir": str(destination),
    }, indent=2, sort_keys=True))
    return 0 if summary["complete"] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--suite", choices=("smoke", "representative", "scaling", "all"),
        default="representative",
    )
    parser.add_argument("--case", action="append", default=[],
                        help="named workload; repeat for multiple cases")
    parser.add_argument("--processes", type=int, default=3)
    parser.add_argument("--samples", type=int, default=12)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--worker", type=int, default=None,
                        help=argparse.SUPPRESS)
    parser.add_argument("--pinned-head", default=None,
                        help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not (args.processes > 0 and args.samples > 0
            and args.warmups >= 0 and args.bootstrap > 0):
        parser.error("invalid profiling parameters")
    if args.worker is None:
        return _controller(args)
    if not args.pinned_head or not 0 <= args.worker < args.processes:
        parser.error("worker requires valid --pinned-head and --worker")
    return _worker(args)


if __name__ == "__main__":
    raise SystemExit(main())
