"""GH-123 experimental audit: is deployment identity a safe reusable proof key?

Usage:
    python -m tests.constraint_functions_seal_audit \
        --output-dir experiment-output --suite smoke
    python -m tests.constraint_functions_seal_audit \
        --output-dir experiment-output --suite full

This is a fail-closed *eligibility* test, not a proof-cache implementation.
It does not patch authentication, preflight, resolver checks, or VM execution.
Every negative case asserts that the original RestrictedExecutor.run refuses
changed authority/source/artifacts before machine.run is entered. Meanwhile
the putative cache key remains unchanged. An unchanged key is therefore NOT
proof of unchanged authority. No fast path is authorized by this experiment.

Only host-private mutations in isolated disposable deployments are used; no
production SHEAR code, frozen oracles, or acceptance expectations are changed.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback
from unittest.mock import patch

from shear import EntityID
from shear.hosted_bootstrap import AdmissionRejected
from shear.hosted_bootstrap import restricted
from shear.hosted_bootstrap.artifacts import artifact_id
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from shear.hosted_bootstrap.restricted_policy import preflight
from shear.hosted_bootstrap.validation import validate_chunk
from shear.lang import _definition_of
from tests.test_restricted_execution import (
    DEAD_WRITE, PRED, PURE_POLICY, READ, READ_POLICY,
    evaluator_source,
)


@dataclass(frozen=True)
class _ProofSnapshot:
    """Untampered preflight result. Does NOT imply immutable deployment."""

    entry: EntityID
    policy: object
    permitted: frozenset
    artifact_count: int
    state_id: object
    compiler_generation: int


def _key(deployment, entry: EntityID, policy) -> tuple:
    """A tempting O(1) cache key which this audit demonstrates is UNSAFE."""
    return (
        id(deployment), deployment.source_state_id,
        deployment.compiler_generation, entry, policy.allowed_effects,
    )


def _prepare():
    state = evaluator_source()
    executor = RestrictedExecutor()
    deployment = executor.deploy(state, compiler_generation=1)
    if executor.run(deployment, PRED, 3, policy=PURE_POLICY) != 'satisfied':
        raise AssertionError('unmodified restricted evaluator diverged')
    executor._check_deployment(deployment)
    permitted = preflight(state, deployment.artifacts, PRED, PURE_POLICY)
    if not permitted:
        raise AssertionError('preflight returned no executable nodes')
    snapshot = _ProofSnapshot(
        PRED, PURE_POLICY, permitted, len(deployment.artifacts),
        state.id, deployment.compiler_generation,
    )
    return state, executor, deployment, snapshot


def _guarded_revalidate(state, executor, deployment, proof) -> None:
    """Conservative reference guard. Intentionally still O(program size)."""
    executor._check_deployment(deployment)
    actual = preflight(state, deployment.artifacts, proof.entry, proof.policy)
    if actual != proof.permitted:
        raise AdmissionRejected('verified call graph differs from prepared proof')


def _expect_rejected_before_vm(executor, deployment, entry=PRED, policy=PURE_POLICY):
    """A rejected operation must never execute any admitted VM instruction."""
    with patch.object(
        restricted.machine, 'run',
        side_effect=AssertionError('VM reached before security rejection'),
    ) as machine_run:
        try:
            executor.run(deployment, entry, 3, policy=policy)
        except AdmissionRejected as exc:
            if machine_run.called:
                raise AssertionError('rejection happened after machine.run')
            return type(exc).__name__, str(exc)
    raise AssertionError('changed authority unexpectedly reached the VM')


def _case(name: str):
    state, executor, deployment, proof = _prepare()
    original_key = _key(deployment, proof.entry, proof.policy)
    start = time.perf_counter_ns()
    detail = {}

    def assert_stale_key():
        if _key(deployment, proof.entry, proof.policy) != original_key:
            raise AssertionError('tampering changed cache key; witness is invalid')

    if name == 'authentic_reuse':
        for subject, expected in ((3, 'satisfied'), (12, 'violated'), (-3, 'unknown')):
            actual = executor.run(deployment, PRED, subject, policy=PURE_POLICY)
            if actual != expected:
                raise AssertionError(f'predicate {subject!r}: {actual!r} != {expected!r}')
        _guarded_revalidate(state, executor, deployment, proof)
        detail['result'] = 'original path works; exhaustive proof recheck works'

    elif name == 'rehashed_artifact_substitution':
        root = _definition_of(state.values[PRED]).body
        key = (root, state.values[root].version_id)
        admitted = deployment._artifact_set._artifacts
        chunks = deployment._artifact_set._chunks
        original = admitted[key]
        new_chunk = (('LIT', 'violated'), ('END',))
        validate_chunk(state, root, PRED, new_chunk)
        forged = replace(original, chunk=new_chunk)
        forged = replace(forged, artifact_id=artifact_id(
            forged.domain, forged.generation, forged.produced_by,
            forged.state_id, forged.entity, forged.version, forged.owner,
            forged.chunk, forged.reused_from,
        ))
        forged.verify()  # The forged replacement is internally self-consistent.
        try:
            admitted[key] = forged  # Same authentic lookup key.
            chunks[key] = forged.chunk
            assert_stale_key()
            detail['rejection'] = _expect_rejected_before_vm(executor, deployment)
            try:
                _guarded_revalidate(state, executor, deployment, proof)
            except AdmissionRejected:
                detail['exhaustive_guard_rejects'] = True
            else:
                raise AssertionError('exhaustive guard accepted substituted artifact')
        finally:
            admitted[key] = original
            chunks[key] = original.chunk
        detail['forged_artifact_was_self_consistent'] = True

    elif name == 'in_place_artifact_mutation':
        root = _definition_of(state.values[PRED]).body
        key = (root, state.values[root].version_id)
        original = deployment.artifacts[key]
        saved_chunk = original.chunk
        try:
            object.__setattr__(original, 'chunk', (('LIT', 'violated'), ('END',)))
            assert_stale_key()
            detail['rejection'] = _expect_rejected_before_vm(executor, deployment)
        finally:
            object.__setattr__(original, 'chunk', saved_chunk)

    elif name == 'decoded_function_mutation':
        value = state.values[PRED]
        definition = _definition_of(value)
        # The private decoded-definition memo is not part of StateID.
        try:
            object.__setattr__(value, '_definition', replace(
                definition, links={'unproven': (PRED,)},
            ))
            assert_stale_key()
            detail['rejection'] = _expect_rejected_before_vm(executor, deployment)
        finally:
            object.__setattr__(value, '_definition', definition)

    elif name == 'issuer_binding_replacement':
        session = deployment._session
        try:
            object.__setattr__(deployment, '_session', object())
            assert_stale_key()
            detail['rejection'] = _expect_rejected_before_vm(executor, deployment)
        finally:
            object.__setattr__(deployment, '_session', session)

    elif name == 'compiler_generation_removed':
        registry = deployment._session._chain._sets
        generation = registry.pop(proof.compiler_generation)
        try:
            assert_stale_key()
            detail['rejection'] = _expect_rejected_before_vm(executor, deployment)
        finally:
            registry[proof.compiler_generation] = generation

    elif name == 'artifact_set_invalidation':
        deployment._artifact_set.invalidate()
        assert_stale_key()
        detail['rejection'] = _expect_rejected_before_vm(executor, deployment)

    elif name == 'pure_policy_rejects_effects':
        # Static transitive effects must reject before VM entry, including
        # forbidden WRITE in a dead branch. Policy is part of the proof key.
        for entry in (READ, DEAD_WRITE):
            try:
                preflight(state, deployment.artifacts, entry, PURE_POLICY)
            except AdmissionRejected:
                pass
            else:
                raise AssertionError(f'pure preflight admitted {entry.value}')
        if _key(deployment, READ, PURE_POLICY) == _key(deployment, READ, READ_POLICY):
            raise AssertionError('effect-policy distinction missing in proof key')
        permitted_read = preflight(state, deployment.artifacts, READ, READ_POLICY)
        if not permitted_read:
            raise AssertionError('explicitly authorized read preflight failed')
        detail['result'] = 'static effects and policy distinctions enforced'

    else:
        raise ValueError(f'unknown audit case {name!r}')

    if _key(deployment, proof.entry, proof.policy) != original_key:
        raise AssertionError('test ineffective: supposedly stale key changed')
    detail.update({
        'kind': 'case', 'name': name, 'status': 'passed',
        'naive_cache_key_unchanged': True,
        'artifact_count': proof.artifact_count,
        'proved_node_count': len(proof.permitted),
        'elapsed_ns': time.perf_counter_ns() - start,
    })
    return detail


SMOKE = ('authentic_reuse', 'rehashed_artifact_substitution', 'decoded_function_mutation')
FULL = SMOKE + (
    'in_place_artifact_mutation', 'issuer_binding_replacement',
    'compiler_generation_removed', 'artifact_set_invalidation',
    'pure_policy_rejects_effects',
)


def _git_head() -> str:
    return subprocess.run(
        ['git', 'rev-parse', 'HEAD'],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--suite', choices=('smoke', 'full'), default='smoke')
    args = parser.parse_args(argv)
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    source_hash = sha256(Path(__file__).read_bytes()).hexdigest()
    metadata = {
        'head': _git_head(), 'script_sha256': source_hash,
        'python': sys.version, 'suite': args.suite,
        'security_checks_modified': False,
        'cached_proof_executed': False,
        'purpose': 'audit whether stable deployment/entry/policy identity establishes proof immutability',
        'limitation': 'host-private adversarial mutations; no optimized production invocation implemented',
    }
    (destination / 'metadata.json').write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    suite = SMOKE if args.suite == 'smoke' else FULL
    results = []
    failed = False
    with (destination / 'cases.jsonl').open('w', encoding='utf-8') as log:
        for name in suite:
            try:
                record = _case(name)
            except BaseException as exc:
                failed = True
                record = {
                    'kind': 'failure', 'name': name, 'status': 'failed',
                    'exception': type(exc).__name__, 'error': str(exc),
                    'traceback': traceback.format_exc(),
                }
            results.append(record)
            log.write(json.dumps(record, sort_keys=True) + '\n')
            log.flush()
            print(f'{name}: {record["status"]}', flush=True)
    summary = {
        'head': metadata['head'], 'script_sha256': source_hash,
        'complete': not failed, 'cases': results,
        'verdict': (
            'stable_identity_is_not_an_immutable_proof' if not failed
            else 'audit_failed_investigate_before_proof_reuse'
        ),
        'required_next_invariant': (
            'immutable authenticated artifacts AND graph/definition snapshots, '
            'with revocation for generation, deployment and artifact-set lifetime'
        ),
    }
    (destination / 'summary.json').write_text(
        json.dumps(summary, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    print(json.dumps({
        'head': metadata['head'], 'complete': not failed,
        'cases': {x['name']: x['status'] for x in results},
        'verdict': summary['verdict'],
        'output': str(destination),
    }, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
