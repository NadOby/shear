"""Semantic partitions of the ordinary deterministic test suite.

CI runs every lane in one job, each lane as its own process
(``python -m tests.lanes --all``).  The partition is deliberately explicit:
adding a new ordinary test module without assigning it to exactly one lane is
an error rather than silently reducing CI coverage.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable
import unittest


LANES: dict[str, tuple[str, ...]] = {
    "core-model": (
        "test_canonical",
        "test_cells",
        "test_constraint_function_acceptance",
        "test_constraint_function_boundaries",
        "test_constraint_function_boundary_acceptance",
        "test_constraint_function_oracle",
        "test_constraint_relations",
        "test_constraints",
        "test_evaluators",
        "test_generation",
        "test_identity",
        "test_lanes",
        "test_ledger",
        "test_lifecycle",
        "test_mutation_regressions_semantics",
        "test_ownership",
        "test_ownership_lifetime",
        "test_ownership_lifetime_regressions",
        "test_references",
        "test_relations",
        "test_state",
        "test_state_identity_cost",
    ),
    "language-runtime": (
        "test_activation",
        "test_bytecode",
        "test_bytecode_regressions",
        "test_closures",
        "test_data_graph_form",
        "test_data_is_opaque",
        "test_data_ops",
        "test_data_regressions",
        "test_error_handling",
        "test_error_provenance",
        "test_error_values",
        "test_first_program",
        "test_graph_form",
        "test_instruction_table",
        "test_lang",
        "test_language_trials",
        "test_metaprogramming",
        "test_runtime",
        "test_trial_runs",
    ),
    "transform-continuity": (
        "test_bounded_exhaustive",
        "test_continuity_corpus",
        "test_continuity_inference",
        "test_continuity_units",
        "test_fold",
        "test_matching",
        "test_metamorphic",
        "test_mutation_regressions_continuity",
        "test_node_edits",
        "test_reference_transfer",
        "test_transform_composition",
        "test_transform_mapping",
        "test_transformation_definition",
        "test_transforms",
    ),
    "syntax-reconcile": (
        "test_mutation_regressions_rendering",
        "test_mutation_regressions_syntax",
        "test_reconcile",
        "test_syntax",
        "test_syntax_links",
        "test_syntax_review",
        "test_syntax_units",
    ),
    "compiler-self-hosting": (
        "test_closure_differential",
        "test_closure_self_hosting",
        "test_self_hosting",
    ),
    "vm-bootstrap": (
        "test_rebuild",
        "test_vm",
    ),
    "cross-boundary": (
        "test_bootstrap_boundary",
        "test_constraint_evaluator",
        "test_constraint_functions_complete",
        "test_constraint_functions_preparation_cache",
        "test_constraint_functions_projection_closure",
        "test_constraint_functions_recursive_reconstruction",
        "test_content_baseline",
        "test_corpus",
        "test_docs",
        "test_endpoint_arity",
        "test_golden",
        # Reject broken G0 bookkeeping before expensive hosted tests.
        "test_mutation_regressions_records",
        "test_hosted_bootstrap",
        "test_hosted_corpus",
        "test_hosted_pipeline",
        "test_hosted_safety",
        "test_live_artifacts",
        "test_live_evolution",
        "test_operations",
        "test_malformed_generation",
        "test_mutation_regressions_boundaries",
        "test_properties",
        "test_reference_version",
        "test_restricted_execution",
        "test_restricted_execution_boundaries",
        "test_restricted_execution_lifecycle",
        "test_stateful_sequences",
    ),
    "mutation": (
        "test_mutation",
        "test_mutation_campaign",
        "test_mutation_catalog",
        "test_mutation_catalog_loader",
        "test_mutation_coverage",
        "test_mutation_outcomes",
        "test_mutation_performance",
        "test_mutation_reporting",
        "test_mutation_verdict",
    ),
}


def _ordinary_modules() -> set[str]:
    directory = Path(__file__).parent

    return {
        path.stem
        for path in directory.glob("test_*.py")
    }


def validate_partition() -> None:
    assigned: dict[str, str] = {}

    for lane, modules in LANES.items():
        for module in modules:
            previous = assigned.get(module)

            if previous is not None:
                raise RuntimeError(
                    f"{module} belongs to both {previous!r} and {lane!r}"
                )

            assigned[module] = lane

    ordinary = _ordinary_modules()
    configured = set(assigned)

    missing = ordinary - configured
    stale = configured - ordinary

    if missing or stale:
        problems = []

        if missing:
            problems.append(
                "unassigned: " + ", ".join(sorted(missing))
            )

        if stale:
            problems.append(
                "missing files: " + ", ".join(sorted(stale))
            )

        raise RuntimeError(
            "invalid test-lane partition; " + "; ".join(problems)
        )


def suite_for(lane: str) -> unittest.TestSuite:
    try:
        modules = LANES[lane]
    except KeyError as exc:
        raise RuntimeError(
            f"unknown test lane {lane!r}; choose from "
            + ", ".join(sorted(LANES))
        ) from exc

    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()

    for module in modules:
        suite.addTests(
            loader.loadTestsFromName(f"tests.{module}")
        )

    return suite


def lane_command(lane: str) -> list[str]:
    """The command that runs one lane on its own."""

    return [sys.executable, "-m", "tests.lanes", lane]


def _run_lane(lane: str) -> tuple[int, str]:
    done = subprocess.run(
        lane_command(lane),
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
    )
    return done.returncode, done.stdout + done.stderr


def run_all(
    jobs: int | None = None,
    run: Callable[[str], tuple[int, str]] = _run_lane,
) -> int:
    """Run every lane as a separate process, ``jobs`` at a time.

    Each lane runs exactly the command it runs alone, so this executes the
    same tests as running the lanes one by one. Each lane's output is printed
    as soon as it finishes, grouped in GitHub Actions, then a timing table in
    ``LANES`` order; the result fails if any lane fails.
    """

    lanes = list(LANES)
    workers = jobs or os.cpu_count() or 1
    grouped = os.environ.get("GITHUB_ACTIONS") == "true"

    def timed(lane: str) -> tuple[int, str, float]:
        start = time.monotonic()
        code, output = run(lane)
        return code, output, time.monotonic() - start

    finished: dict[str, tuple[int, str, float]] = {}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(timed, lane): lane for lane in lanes}

        # Print each lane as soon as it finishes, so a lane that hangs until
        # the job times out does not hide the output of the others.
        for future in as_completed(pending):
            lane = pending[future]
            code, output, seconds = future.result()
            finished[lane] = (code, output, seconds)
            status = "ok" if code == 0 else "FAILED"
            if grouped and code == 0:
                print(f"::group::{lane} ({status})")
                print(output, end="")
                print("::endgroup::", flush=True)
            else:
                print(f"===== {lane} ({status}) =====")
                print(output, end="", flush=True)

    results = [finished[lane] for lane in lanes]
    print(f"lanes run {workers} at a time:")

    for lane, (code, _, seconds) in zip(lanes, results):
        status = "ok" if code == 0 else "FAILED"
        print(f"  {lane:<24} {status:<6} {seconds:6.1f}s")

    return 0 if all(code == 0 for code, _, seconds in results) else 1


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv

    validate_partition()

    if args == ["--all"]:
        return run_all()

    if len(args) != 1:
        print(
            "usage: python -m tests.lanes <lane> | --all",
            file=sys.stderr,
        )
        print(
            "lanes: " + ", ".join(sorted(LANES)),
            file=sys.stderr,
        )
        return 2

    try:
        suite = suite_for(args[0])
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    result = unittest.TextTestRunner(
        verbosity=2,
    ).run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
