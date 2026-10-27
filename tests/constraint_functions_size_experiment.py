"""GH-123 experiment: shrink authenticated evaluator code without weakening Task 32.

This is an explicit, non-acceptance performance experiment. The same generic
SHEAR evaluator and exact RestrictedExecutor.run path are used on both sides.
Only the statically unreachable *constraint-form dispatch branches* and their
unreferenced functions are removed from the specialized deployment.

    python -m tests.constraint_functions_size_experiment \\
        --output-dir /tmp/gh123-size

The specialization is indexed by a superset of forms in the *source
constraint tree*, not by subject, verdict, budget, or external outcomes.
Different tree values with identical form sets share one deployment.
No production evaluator, artifact verifier, policy, or preflight is patched.
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
import sys
import traceback
from time import perf_counter_ns, process_time_ns

from shear.examples._support import program
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from shear.identity import EntityID
from shear.lang import Function, links, load
from tests import constraint_functions_complete_candidate as candidate
from tests.constraint_functions_comparative_benchmark import (
    _calibrate, _cases as _comparison_cases, _digest, _git_head,
    _percentile, _time_batch,
)
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
)


FORMS = frozenset({
    "is_kind", "int_range", "length", "one_of",
    "all_of", "any_of", "not", "role", "external",
})
DEFAULTS = {
    "processes": 3,
    "warmups": 30,
    "blocks": 40,
    "target_ms": 20.0,
    "bootstrap": 2000,
}
GENERATION = candidate._PRIVATE_COMPILER_GENERATION


def _cases(suite: str) -> list[dict]:
    """Retain frozen cases; correct the experimental scaling node counts.

    The shared comparison generator's ``all_of_distinct_N`` cases contain
    N leaves plus one composite node. Only this experiment changes those
    supplementary workloads; it does not edit the frozen oracle or the
    original comparative benchmark.
    """
    if suite not in ("representative-scaling", "full"):
        return _comparison_cases(suite)

    ordinary = _comparison_cases(
        "representative" if suite == "representative-scaling" else "full"
    )
    ordinary = [
        row for row in ordinary
        if row["name"] not in {
            "all_of_distinct_8", "all_of_distinct_64", "all_of_distinct_256"
        }
    ]
    for size in (8, 64, 256):
        # AllOf is one constraint node, so use exactly size - 1 leaves.
        expression = (
            "all_of",
            *(("int_range", -i, size + i) for i in range(size - 1)),
        )
        normalized = candidate._constraint(expression)
        if len(normalized.parts) + 1 != size:
            raise AssertionError("scaling workload has incorrect node count")
        ordinary.append({
            "name": f"all_of_nodes_{size}",
            "expression": expression,
            "subject": 5,
            "budget": None,
            "externals": (),
            "expected": "satisfied",
            "origin": "exact total constraint nodes (root included)",
            "constraint_nodes": size,
        })
    return ordinary


def _forms(expression: tuple) -> frozenset[str]:
    """Conservative syntactic form inventory; never evaluate a subject."""
    if not isinstance(expression, tuple) or not expression:
        raise TypeError("malformed constraint expression")
    kind = expression[0]
    if kind not in FORMS:
        raise ValueError(f"unknown constraint form: {kind!r}")
    seen = {kind}
    if kind in ("all_of", "any_of"):
        children = expression[1:]
    elif kind == "not":
        children = expression[1:2]
    elif kind == "role":
        children = expression[2:3]
    else:
        children = ()
    for child in children:
        seen.update(_forms(child))
    return frozenset(seen)


def _prune_dispatch(cases: tuple, retained: frozenset[str]) -> tuple:
    """Only remove discarded arms from the known canonical form switch.

    Reject any unexpected AST, rather than silently emitting changed logic.
    The fallback remains the original admitted SHEAR 'raise' expression.
    """
    if cases[0] == "raise" and len(cases) == 3:
        return cases
    if not (
        len(cases) == 4 and cases[0] == "if"
        and isinstance(cases[1], tuple)
        and cases[1][:2] == ("eq", ("arg", "form"))
        and isinstance(cases[1][2], tuple)
        and cases[1][2][0] == "lit"
        and len(cases[1][2]) == 2
        and cases[1][2][1] in FORMS
    ):
        raise AssertionError("candidate form dispatch layout changed")
    rest = _prune_dispatch(cases[3], retained)
    if cases[1][2][1] in retained:
        return ("if", cases[1], cases[2], rest)
    return rest


def _call_names(expression: object) -> frozenset[str]:
    """Discover exact static call labels used in a plain SHEAR AST."""
    called: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, tuple) and value:
            if value[0] == "call":
                if len(value) < 2 or not isinstance(value[1], str):
                    raise AssertionError("unresolved direct call")
                called.add(value[1])
            for child in value[1:]:
                visit(child)

    visit(expression)
    return frozenset(called)


def _minimal_entities(retained: frozenset[str]) -> dict:
    """Specialize the real evaluator's dispatch while retaining its bodies.

    All underlying primitive, budget, strong-Kleene, role, recursive and
    registration functions are the original SHEAR Function objects.
    """
    if not retained or not retained <= FORMS:
        raise ValueError("unsupported form set")

    source = candidate._registered_entities()
    node_id = candidate.REGISTERED_NODE
    original = source[node_id]
    if not isinstance(original, Function):
        raise AssertionError("registered node is no longer a SHEAR function")
    body = original.body
    if not (
        len(body) == 4 and body[:2] == ("let", "form")
        and isinstance(body[3], tuple)
        and len(body[3]) == 4 and body[3][:2] == ("let", "arguments")
    ):
        raise AssertionError("registered evaluator AST changed")

    new_body = (
        "let", "form", body[2],
        ("let", "arguments", body[3][2],
         _prune_dispatch(body[3][3], retained)),
    )
    source[node_id] = Function(original.params, new_body)

    link_id = EntityID(f"{node_id.value}.links")
    original_links = source[link_id]
    calls = _call_names(new_body)
    missing = calls.difference(original_links.roles)
    if missing:
        raise AssertionError(f"uncertified call labels: {sorted(missing)!r}")
    source[link_id] = links(
        node_id, **{name: original_links.roles[name] for name in sorted(calls)}
    )

    # The ordinary candidate's static transitive-closure construction,
    # including all recursively linked functions.
    return candidate._projection_static_closure(
        source, candidate.REGISTERED_ENTRY,
    )


def _prepare(row: dict, narrowed: dict):
    """Compile each form-set only once per process; keep all code admitted."""
    expression = row["expression"]
    constraint = candidate._constraint(expression)
    subject = candidate._materialize_subject(row["subject"])
    registrations = tuple(row["externals"])
    budget = row["budget"]
    forms = _forms(expression)

    # Original production cache and original admitted generic code.
    started = perf_counter_ns()
    generic_executor, generic_deployment, generic_entry = (
        candidate._generic_registered_deployment(
            registrations, GENERATION, candidate._PRIVATE_SEMANTIC_AUTHORITY,
        )
    )
    generic_prepare_ns = perf_counter_ns() - started

    if forms not in narrowed:
        started = perf_counter_ns()
        definitions = _minimal_entities(forms)
        source = load(program(definitions))
        executor = RestrictedExecutor()
        deployment = executor.deploy(
            source, compiler_generation=GENERATION,
        )
        prepare_ns = perf_counter_ns() - started
        narrowed[forms] = (executor, deployment, prepare_ns)
        compiled = True
    else:
        compiled = False
    executor, deployment, prepare_ns = narrowed[forms]

    args = (subject, constraint, budget, registrations)

    def generic():
        return generic_executor.run(
            generic_deployment, generic_entry, *args,
        )

    def specialized():
        return executor.run(
            deployment, candidate.REGISTERED_ENTRY, *args,
        )

    # Verify both genuinely open authenticated evaluator code, without
    # an instrumented or modified timed path.
    with candidate_execution_guard(
        frozenset({candidate.REGISTERED_ENTRY})
    ) as opened:
        first = generic()
        second = specialized()
    if len(opened) < 2 or first != row["expected"] or second != first:
        raise RuntimeError(
            f"semantic/VM mismatch: {row['name']}: "
            f"baseline={first!r}, specialized={second!r}, "
            f"expected={row['expected']!r}, opened={len(opened)}"
        )

    info = {
        "forms": sorted(forms),
        "generic_artifacts": len(generic_deployment.artifacts),
        "specialized_artifacts": len(deployment.artifacts),
        "generic_prepare_ns_observed": generic_prepare_ns,
        "specialized_prepare_ns_if_new": prepare_ns if compiled else None,
        "specialized_source_reused": not compiled,
        "input_digest": _digest((
            constraint, subject, budget, registrations,
        )),
    }
    return generic, specialized, info


def _worker(args) -> int:
    if _git_head() != args.pinned_head:
        raise RuntimeError("repository HEAD changed during experiment")
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / f"environment-{args.worker}.json").write_text(
        json.dumps({
            "process": args.worker,
            "pid": os.getpid(),
            "head": args.pinned_head,
            "python": sys.version,
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "hash_seed": os.getenv("PYTHONHASHSEED"),
            "experiment_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    rng = random.Random(args.seed + args.worker * 104729)
    cached: dict[frozenset[str], tuple] = {}
    sink_path = destination / f"blocks-process-{args.worker}.jsonl"
    with sink_path.open("w", encoding="utf-8") as sink:
        for row in _cases(args.suite):
            try:
                generic, specialized, info = _prepare(row, cached)
                expected = row["expected"]
                for _ in range(args.warmups):
                    if generic() != expected or specialized() != expected:
                        raise RuntimeError("warmup semantic mismatch")
                n_generic, calibrated_generic = _calibrate(
                    generic, expected, args.target_ns, args.max_batch,
                )
                n_specialized, calibrated_specialized = _calibrate(
                    specialized, expected, args.target_ns, args.max_batch,
                )
                for block in range(args.blocks):
                    first = ("generic" if block % 2 == 0 else "specialized")
                    if rng.randrange(2):
                        first = (
                            "specialized" if first == "generic" else "generic"
                        )
                    order = (
                        first, "specialized" if first == "generic" else "generic",
                    )
                    readings = {}
                    for label in order:
                        callable_ = (
                            generic if label == "generic" else specialized
                        )
                        count = (
                            n_generic if label == "generic" else n_specialized
                        )
                        wall, cpu = _time_batch(callable_, count, expected)
                        readings[label] = {
                            "batch": count,
                            "wall_ns": wall,
                            "cpu_ns": cpu,
                            "wall_per_call_ns": wall / count,
                            "cpu_per_call_ns": cpu / count,
                        }
                    sink.write(json.dumps({
                        "kind": "paired_block",
                        "process": args.worker,
                        "workload": row["name"],
                        "block": block,
                        "order": order,
                        "expected": expected,
                        "calibrated_ns": {
                            "generic": calibrated_generic,
                            "specialized": calibrated_specialized,
                        },
                        **info, **readings,
                    }, sort_keys=True) + "\n")
                    sink.flush()
            except BaseException as exc:
                sink.write(json.dumps({
                    "kind": "failure",
                    "process": args.worker,
                    "workload": row["name"],
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }, sort_keys=True) + "\n")
                sink.flush()
    return 0


def _ratio(rows: list[dict], measure) -> float:
    reference = measure([r["generic"]["wall_per_call_ns"] for r in rows])
    tested = measure([r["specialized"]["wall_per_call_ns"] for r in rows])
    return tested / reference


def _summarize(rows: list[dict], bootstrap: int, seed: int) -> dict:
    groups = defaultdict(list)
    for row in rows:
        groups[row["process"]].append(row)
    # Each observation is a block mean, not one invocation. In particular,
    # the 95th percentile below is NOT an individual-invocation tail p95.
    measures = {
        "median_block_mean": statistics.median,
        "p95_block_mean": lambda values: _percentile(values, .95),
    }
    rng = random.Random(seed)
    ratios = {
        name: {"ratio": _ratio(rows, fun), "ci95": None}
        for name, fun in measures.items()
    }
    replicates = {name: [] for name in measures}
    for _ in range(bootstrap):
        picked = []
        for process in sorted(groups):
            sample = groups[process]
            picked.extend(
                sample[rng.randrange(len(sample))] for _ in sample
            )
        for name, fun in measures.items():
            replicates[name].append(_ratio(picked, fun))
    for name in measures:
        draws = sorted(replicates[name])
        ratios[name]["ci95"] = [
            draws[int(.025 * (len(draws) - 1))],
            draws[int(.975 * (len(draws) - 1))],
        ]
    return {
        "latency_observation": "mean wall nanoseconds per invocation in each timed block",
        "p95_block_mean_is_individual_tail_p95": False,
        "individual_call_tail_unmeasured": True,
        "ratios_specialized_over_generic": ratios,
        "generic": {
            name + "_ns": fun(
                [r["generic"]["wall_per_call_ns"] for r in rows]
            ) for name, fun in measures.items()
        },
        "specialized": {
            name + "_ns": fun(
                [r["specialized"]["wall_per_call_ns"] for r in rows]
            ) for name, fun in measures.items()
        },
        "generic_artifacts": rows[0]["generic_artifacts"],
        "specialized_artifacts": rows[0]["specialized_artifacts"],
        "forms": rows[0]["forms"],
        "input_digest": rows[0]["input_digest"],
        "observations": len(rows),
        "process_variation": {
            str(process): {
                label: {
                    name + "_ns": fun([
                        r[label]["wall_per_call_ns"] for r in group
                    ]) for name, fun in measures.items()
                } for label in ("generic", "specialized")
            } for process, group in groups.items()
        },
    }


def _controller(args) -> int:
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    head = _git_head()
    rows = _cases(args.suite)
    protocol_ok = (
        args.processes >= 3 and args.warmups >= 30
        and args.blocks >= 40 and args.bootstrap >= 2000
        and args.target_ms >= 20
    )
    meta = {
        "head": head,
        "experiment_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        "invocation": {
            k: v for k, v in vars(args).items() if k != "target_ns"
        },
        "sampling_meets_warm_protocol": protocol_ok,
        "experiment_not_gh123_acceptance": True,
        "latency_observation": "per-block invocation-average wall time",
        "tail_latency": "individual-call p95 NOT measured; summary p95_block_mean is a percentile of block means",
        "scaling_nodes": "all_of_nodes_N has N - 1 unique leaves plus the AllOf root, exactly N nodes",
        "compare": (
            "identical four-operand RestrictedExecutor.run "
            "for original generic versus form-set specialized generic"
        ),
        "specialization": (
            "Remove only unreachable constraint-form dispatcher branches "
            "and transitive static dependencies. No semantic results "
            "or subject/budget values embedded in compiled code."
        ),
        "workloads": [{
            "name": row["name"],
            "expression": repr(row["expression"]),
            "subject": repr(row["subject"]),
            "budget": row["budget"],
            "externals": repr(row["externals"]),
            "expected": row["expected"],
            "constraint_nodes": row.get("constraint_nodes"),
        } for row in rows],
    }
    (destination / "metadata.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    for worker in range(args.processes):
        command = [
            sys.executable,
            "-m", "tests.constraint_functions_size_experiment",
            "--worker", str(worker),
            "--pinned-head", head,
            "--output-dir", str(destination),
            "--suite", args.suite,
            "--processes", str(args.processes),
            "--warmups", str(args.warmups),
            "--blocks", str(args.blocks),
            "--bootstrap", str(args.bootstrap),
            "--target-ms", str(args.target_ms),
            "--max-batch", str(args.max_batch),
            "--seed", str(args.seed),
        ]
        subprocess.run(
            command, check=True, env={**os.environ, "PYTHONHASHSEED": "0"},
        )

    grouped = defaultdict(list)
    failures = []
    for worker in range(args.processes):
        source = destination / f"blocks-process-{worker}.jsonl"
        for line in source.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry["kind"] == "failure":
                failures.append(entry)
            else:
                grouped[entry["workload"]].append(entry)

    summary = {
        "head": head,
        "experiment": "form-set deployment size",
        "complete": not failures,
        "sampling_meets_warm_protocol": protocol_ok,
        "latency_observation": "per-block invocation-average wall time",
        "individual_call_tail_unmeasured": True,
        "workloads": {},
        "failures": failures,
    }
    for row in rows:
        name = row["name"]
        blocks = grouped[name]
        valid = (
            len(blocks) == args.processes * args.blocks
            and all(
                sum(x["process"] == process for x in blocks) == args.blocks
                for process in range(args.processes)
            )
            and len({x["input_digest"] for x in blocks}) == 1
            and len({x["generic_artifacts"] for x in blocks}) == 1
            and len({x["specialized_artifacts"] for x in blocks}) == 1
        )
        if not valid:
            summary["complete"] = False
            summary["workloads"][name] = {
                "status": "missing_or_inconsistent_samples",
                "samples": len(blocks),
            }
            continue
        seed = args.seed ^ int(
            hashlib.sha256(name.encode()).hexdigest()[:8], 16
        )
        summary["workloads"][name] = _summarize(
            blocks, args.bootstrap, seed,
        )
    (destination / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "head": head,
        "complete": summary["complete"],
        "failures": len(failures),
        "ratios": {
            name: data["ratios_specialized_over_generic"]["median_block_mean"]["ratio"]
            for name, data in summary["workloads"].items()
            if "ratios_specialized_over_generic" in data
        },
        "output_dir": str(destination),
    }, indent=2, sort_keys=True))
    return 0 if summary["complete"] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--suite",
        choices=("smoke", "representative", "representative-scaling", "full"),
        default="representative",
    )
    parser.add_argument("--processes", type=int, default=DEFAULTS["processes"])
    parser.add_argument("--warmups", type=int, default=DEFAULTS["warmups"])
    parser.add_argument("--blocks", type=int, default=DEFAULTS["blocks"])
    parser.add_argument("--bootstrap", type=int, default=DEFAULTS["bootstrap"])
    parser.add_argument("--target-ms", type=float, default=DEFAULTS["target_ms"])
    parser.add_argument("--max-batch", type=int, default=1 << 20)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--worker", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--pinned-head", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not (
        args.processes > 0 and args.warmups >= 0 and args.blocks > 0
        and args.bootstrap > 0 and math.isfinite(args.target_ms)
        and args.target_ms > 0 and args.max_batch >= 1
    ):
        parser.error("invalid sampling settings")
    args.target_ns = math.ceil(args.target_ms * 1_000_000)
    if args.worker is None:
        return _controller(args)
    if not args.pinned_head or not 0 <= args.worker < args.processes:
        parser.error("worker requires valid --pinned-head and --worker")
    return _worker(args)


if __name__ == "__main__":
    raise SystemExit(main())
