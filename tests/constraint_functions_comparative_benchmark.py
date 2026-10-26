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
