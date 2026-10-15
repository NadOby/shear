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

    for lane
