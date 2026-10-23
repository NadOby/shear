"""Discover all 18 frozen GH-123 acceptance modules through unittest.

The acceptance modules remain unchanged and independently maintained.
The complete frozen inventory is loaded without skips or filtering.
"""

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


def load_tests(loader, standard_tests, pattern):
    """Load every frozen test and enforce the approved inventory."""
    if len(ACCEPTANCE_MODULES) != 18:
        raise AssertionError("GH-123 requires 18 acceptance modules")

    suite = unittest.TestSuite()

    for module in ACCEPTANCE_MODULES:
        suite.addTests(loader.loadTestsFromModule(module))

    count = suite.countTestCases()
    if count != 78:
        raise AssertionError(
            f"GH-123 requires 78 frozen tests, discovered {count}"
        )

    return suite
