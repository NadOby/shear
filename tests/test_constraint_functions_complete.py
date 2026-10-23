"""Discover and shard all 18 frozen GH-123 acceptance modules.

Ordinary discovery verifies inventory integrity. Dedicated CI shards
execute all 78 frozen tests. No acceptance assertion is modified,
skipped or replaced.
"""

from __future__ import annotations

import argparse
import sys
import time
import unittest

from tests import (
    constraint_functions_authority_acceptance,
    constraint_functions_binding_acceptance,
    constraint_functions_candidate_effect_acceptance,
    constraint_functions_complete_acceptance,
    constraint_functions_complete_projection,
    constraint_functions_corpus_acceptance,
    constraint_functions_direct_result_acceptance,
    constraint_functions_external_acceptance,
    constraint_functions_failure_acceptance,
    constraint_functions_identity_acceptance,
    constraint_functions_import_acceptance,
    constraint_functions_nested_record_acceptance,
    constraint_functions_projection_adversarial,
    constraint_functions_resource_acceptance,
    constraint_functions_runtime_acceptance,
    constraint_functions_semantic_adversarial,
    constraint_functions_sequence_acceptance,
    constraint_functions_t2_t3_acceptance,
)


ACCEPTANCE_MODULES = (
    constraint_functions_authority_acceptance,
    constraint_functions_binding_acceptance,
    constraint_functions_candidate_effect_acceptance,
    constraint_functions_complete_acceptance,
    constraint_functions_complete_projection,
    constraint_functions_corpus_acceptance,
    constraint_functions_direct_result_acceptance,
    constraint_functions_external_acceptance,
    constraint_functions_failure_acceptance,
    constraint_functions_identity_acceptance,
    constraint_functions_import_acceptance,
    constraint_functions_nested_record_acceptance,
    constraint_functions_projection_adversarial,
    constraint_functions_resource_acceptance,
    constraint_functions_runtime_acceptance,
    constraint_functions_semantic_adversarial,
    constraint_functions_sequence_acceptance,
    constraint_functions_t2_t3_acceptance,
)


EXPECTED_MODULES = 18
EXPECTED_TESTS = 78
MAX_SHARDS = 16


def _flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten(item)
        else:
            yield item


def inventory(loader):
    """Return the complete, unique and deterministic frozen inventory."""
    if len(ACCEPTANCE_MODULES) != EXPECTED_MODULES:
        raise AssertionError(
            f"expected {EXPECTED_MODULES} frozen acceptance modules"
        )

    suite = unittest.TestSuite()

    for module in ACCEPTANCE_MODULES:
        suite.addTests(loader.loadTestsFromModule(module))

    cases = tuple(sorted(_flatten(suite), key=lambda test: test.id()))
    identifiers = tuple(test.id() for test in cases)

    if len(cases) != EXPECTED_TESTS:
        raise AssertionError(
            f"expected {EXPECTED_TESTS} frozen tests, got {len(cases)}"
        )

    if len(set(identifiers)) != EXPECTED_TESTS:
        raise AssertionError("duplicate frozen acceptance test identity")

    return cases


class FrozenInventoryTests(unittest.TestCase):
    """Ordinary CI checks registration, not the full acceptance workload."""

    def test_complete_frozen_inventory(self):
        cases = inventory(unittest.defaultTestLoader)
        self.assertEqual(len(cases), EXPECTED_TESTS)
        self.assertEqual(len(ACCEPTANCE_MODULES), EXPECTED_MODULES)


def load_tests(loader, standard_tests, pattern):
    """Keep the ordinary and mutation lanes independent of frozen execution."""
    return loader.loadTestsFromTestCase(FrozenInventoryTests)


def partition(cases, shards):
    """Assign every frozen method exactly once, without changing its body."""
    if not 1 <= shards <= MAX_SHARDS:
        raise ValueError(
            f"shard count must be between 1 and {MAX_SHARDS}"
        )

    groups = tuple(
        cases[index::shards]
        for index in range(shards)
    )

    original = {test.id() for test in cases}
    assigned = [
        test.id()
        for group in groups
        for test in group
    ]

    if len(assigned) != len(cases) or set(assigned) != original:
        raise AssertionError("frozen acceptance sharding lost a test")

    if len(set(assigned)) != len(assigned):
        raise AssertionError("frozen acceptance sharding duplicated a test")

    return groups


class TimedResult(unittest.TextTestResult):
    """Report each active test and its body execution duration."""

    def startTest(self, test):
        self._started = time.perf_counter()
        self.stream.writeln(f"START {test.id()}")
        self.stream.flush()
        super().startTest(test)

    def stopTest(self, test):
        elapsed = time.perf_counter() - self._started
        super().stopTest(test)
        self.stream.writeln(
            f"DURATION {elapsed:.3f}s {test.id()}"
        )
        self.stream.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run one deterministic GH-123 acceptance shard"
    )
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--shards", type=int, required=True)
    arguments = parser.parse_args(argv)

    if not 1 <= arguments.shards <= MAX_SHARDS:
        parser.error(
            f"--shards must be between 1 and {MAX_SHARDS}"
        )

    if not 0 <= arguments.shard < arguments.shards:
        parser.error("--shard must be a zero-based valid shard index")

    cases = inventory(unittest.defaultTestLoader)
    groups = partition(cases, arguments.shards)
    selected = groups[arguments.shard]

    print(
        f"GH-123 frozen inventory: {len(ACCEPTANCE_MODULES)} modules, "
        f"{len(cases)} methods",
        flush=True,
    )
    print(
        f"SHARD {arguments.shard + 1}/{arguments.shards}: "
        f"{len(selected)} methods",
        flush=True,
    )

    for test in selected:
        print(f"ASSIGNED {test.id()}", flush=True)

    started = time.perf_counter()

    result = unittest.TextTestRunner(
        stream=sys.stdout,
        verbosity=2,
        resultclass=TimedResult,
    ).run(unittest.TestSuite(selected))

    elapsed = time.perf_counter() - started

    print(
        f"SHARD COMPLETE {arguments.shard + 1}/{arguments.shards}: "
        f"executed={result.testsRun}/{len(selected)}, "
        f"failures={len(result.failures)}, "
        f"errors={len(result.errors)}, "
        f"skipped={len(result.skipped)}, "
        f"elapsed={elapsed:.3f}s",
        flush=True,
    )

    if result.testsRun != len(selected) or result.skipped:
        return 1

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
