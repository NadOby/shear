"""GH-123 experimental authenticated execution in the ORIGINAL SHEAR Runtime.

NO production changes. This is not a production-acceptable proof cache.
Issuance uses the unmodified issuer check, authenticated admitted artifacts and
complete source/chunk preflight. Invocation uses a sealed resolver and existing
machine.run on the ORIGINAL target runtime, preserving ordinary VM operations.
The experiment detects deliberate parity gaps involving untracked mutable host
objects instead of claiming that a Python epoch makes them immutable.

Run through opt-in CI:
  python -m tests.constraint_functions_live_admission_spike \
      --output-dir experiment-output --suite smoke --samples 4
  python -m tests.constraint_functions_live_admission_spike \
      --output-dir experiment-output --suite representative --samples 8
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from time import perf_counter_ns
import traceback
from types import MappingProxyType
from unittest.mock import patch

from shear import AllOf, CellContentRejected, ConstraintResult, External, bytecode
from shear.canonical import canonicalize
from shear.hosted_bootstrap import AdmissionRejected, restricted
from shear.hosted_bootstrap.artifacts import artifact_id
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from shear.hosted_bootstrap.restricted_policy import RestrictionPolicy, preflight
from shear.hosted_bootstrap.trace import ADMITTED_HOST, EXECUTE
from shear.lang import _definition_of
from shear.runtime import Runtime
from tests import constraint_functions_complete_candidate as candidate
from tests import constraint_functions_sealed_snapshot_experiment as previous
from tests.test_restricted_execution import (
    CELL, DEAD_WRITE, PRED, PURE_POLICY, READ, READ_POLICY,
    cell_state, evaluator_source,
)


class _LivePinnedResolver:
    """No lowering or backing ArtifactSet lookup during VM execution."""

    def __init__(self, grant):
        self.grant = grant
        self.opened = 0

    def __call__(self, state, entity, owner):
        raise AdmissionRejected('live seal requires version-pinned resolution')

    def for_version(self, version, entity, owner):
        g = self.grant
        g._guard()  # Includes revocation between VM openings.
        if version is not g.active or version.state is not g.state:
            raise AdmissionRejected('live seal opened a different runtime version')
        value = version.state.values.get(entity)
        if value is None:
            raise AdmissionRejected('live seal opened absent source node')
        key = (entity, value.version_id)
        if key not in g.approved:
            raise AdmissionRejected('live seal opened unproved code')
        selected = g.chunks.get(key)
        if selected is None or selected[0] != owner:
            raise AdmissionRejected('live seal changed executable owner')
        self.opened += 1
        return selected[1]


class _LiveAdmission:
    """Experimentally issue a proof for existing runtime, not a new runtime.

    Authenticated chunks are copied before the first speculative invocation.
    The host-private State and its decoded caches remain live and mutable.
    This is a known obstacle to full security equivalence, not an assertion
    that the snapshot is immutable under Python reflection.
    """

    def __init__(self, executor, deployment, entry, policy):
        if not isinstance(policy, RestrictionPolicy):
            raise TypeError('expected RestrictionPolicy')
        start = perf_counter_ns()
        executor._check_deployment(deployment)
        state = deployment._target.state
        approved = preflight(state, deployment.artifacts, entry, policy)
        issued = executor._issued.get(deployment)
        if issued is None:
            raise AdmissionRejected('no authentic issuer record')
        self.executor, self.deployment, self.entry = executor, deployment, entry
        self.policy = policy
        self.issued = issued
        self.session, self.target, self.artifact_set, self.authenticated = issued
        self.runtime = self.target.runtime
        self.active = self.runtime.active
        self.state = state
        self.owner = executor._identity
        self.generation = self.session._chain._sets.get(deployment.compiler_generation)
        if self.generation is None or not self.generation.valid:
            raise AdmissionRejected('issuer generation was invalid')
        self.approved = approved
        definition = _definition_of(state.values[entry])
        if definition is None:
            raise AdmissionRejected('entry has no authenticated function')
        root = definition.body
        self.root_artifact = deployment.artifacts[(root, state.values[root].version_id)]
        # Copy only verified, reachable chunk data; retain existing *runtime*.
        copies = {}
        for key in approved:
            art = deployment.artifacts[key]
            chunk = tuple(deepcopy(opcode) for opcode in art.chunk)
            if chunk != art.chunk or chunk is art.chunk:
                raise AssertionError('sealed chunk was not independently copied')
            copies[key] = (art.owner, chunk)
        self.chunks = MappingProxyType(copies)
        self.resolver = _LivePinnedResolver(self)
        self.revoked = False
        self.preparation_ns = perf_counter_ns() - start

    def revoke(self):
        self.revoked = True

    def _guard(self):
        d = self.deployment
        if self.revoked or self.executor._issued.get(d) is not self.issued:
            raise AdmissionRejected('live admission record revoked or replaced')
        if d._owner is not self.owner:
            raise AdmissionRejected('live admission issuer changed')
        if (d._session is not self.session or d._target is not self.target
                or d._artifact_set is not self.artifact_set
                or d.artifacts is not self.authenticated
                or self.target._artifacts is not self.artifact_set
                or self.target._sets.get(self.runtime.active) is not self.artifact_set):
            raise AdmissionRejected('live admission bindings changed')
        if (self.runtime.active is not self.active
                or self.active.state is not self.state
                or self.state.id != d.source_state_id
                or d.compiler_generation != self.target.compiler_generation):
            raise AdmissionRejected('live admission version changed')
        if not self.artifact_set.valid:
            raise AdmissionRejected('live admission artifact set invalidated')
        if (self.session._chain._sets.get(d.compiler_generation) is not self.generation
                or not self.generation.valid):
            raise AdmissionRejected('live admission compiler generation retired')

    def run(self, *args):
        self._guard()  # Current RestrictedExecutor._check_deployment is outside try.
        art = self.root_artifact
        try:
            result = restricted.machine.run(
                self.runtime, self.entry,
                *(canonicalize(arg) for arg in args),
                resolver=self.resolver, may_activate=False,
            )
        except BaseException as exc:
            self.executor._trace.emit(
                restricted.RESTRICTED_FAILURE, ADMITTED_HOST,
                entity=self.entry, version=art.version,
                artifact_id=art.artifact_id,
                compiler_generation=self.deployment.compiler_generation,
                target_state_id=self.deployment.source_state_id,
                detail=(
                    'restricted invocation failed or was refused; '
                    f'evaluator_source={self.deployment.source_state_id.value}; '
                    f'failure={type(exc).__name__}'
                ),
            )
            raise
        self.executor._trace.emit(
            EXECUTE, ADMITTED_HOST, entity=self.entry, version=art.version,
            artifact_id=art.artifact_id,
            compiler_generation=self.deployment.compiler_generation,
            target_state_id=self.deployment.source_state_id,
            detail='restricted invocation',
        )
        return result


def _fixture(entry=PRED, policy=PURE_POLICY):
    executor = RestrictedExecutor()
    deployment = executor.deploy(evaluator_source(), compiler_generation=1)
    record = _LiveAdmission(executor, deployment, entry, policy)
    return executor, deployment, record


def _expect_rejected_before_vm(operation):
    with patch.object(restricted.machine, 'run', side_effect=AssertionError(
        'revoked or forbidden invocation reached VM',
    )) as opened:
        try:
            operation()
        except AdmissionRejected:
            if opened.called:
                raise AssertionError('security rejection happened after VM entry')
            return True
    raise AssertionError('forbidden invocation was accepted')


def _authentic():
    executor, deployment, record = _fixture()
    opened_before = record.resolver.opened
    for subject in (3, 12, -3):
        baseline = executor.run(deployment, PRED, subject, policy=PURE_POLICY)
        baseline_event = executor.trace()[-1].as_json()
        with patch.object(bytecode, 'lower_value', side_effect=AssertionError(
            'host lowering during sealed execution',
        )), patch.object(restricted.machine, 'run', wraps=restricted.machine.run) as observed:
            actual = record.run(subject)
        sealed_event = executor.trace()[-1].as_json()
        if actual != baseline or baseline_event != sealed_event:
            raise AssertionError('same-runtime semantic or trace divergence')
        if (len(observed.call_args_list) != 1
                or observed.call_args.args[0] is not deployment._target.runtime
                or observed.call_args.kwargs.get('may_activate') is not False
                or observed.call_args.kwargs.get('resolver') is not record.resolver):
            raise AssertionError('sealed path did not use original restricted runtime')
    if record.resolver.opened <= opened_before:
        raise AssertionError('genuine pinned VM node opening not observed')
    return {'observed_real_vm': True, 'original_runtime': True,
            'trace_parity': True, 'no_lowering_fallback': True,
            'opened_nodes': record.resolver.opened}


def _read_and_denied():
    executor, deployment, record = _fixture(READ, READ_POLICY)
    baseline = executor.run(deployment, READ, policy=READ_POLICY)
    observed = record.run()
    if baseline != 7 or observed != baseline:
        raise AssertionError('read-authorized live execution diverged')
    with patch.object(restricted.machine, 'run', side_effect=AssertionError(
        'VM entered before forbidden WRITE policy rejection',
    )) as vm:
        try:
            _LiveAdmission(executor, deployment, DEAD_WRITE, READ_POLICY)
        except AdmissionRejected:
            if vm.called:
                raise AssertionError('forbidden instruction reached VM')
        else:
            raise AssertionError('dead-branch WRITE was not preflight-rejected')
    return {'explicit_read_authority': True, 'forbidden_effect_preflight': True}


def _registry_admission():
    executor, deployment, record = _fixture()
    registry = executor.registry({'policy': (deployment, PRED)})
    original_run = executor.run
    seen = []

    def run_on_registry(depl, entry, *args, policy=None):
        if depl is deployment and entry == PRED and policy == PURE_POLICY:
            seen.append(args)
            return record.run(*args)
        return original_run(depl, entry, *args, policy=policy)

    with patch.object(executor, 'run', side_effect=run_on_registry):
        live = Runtime(cell_state(), registry.context)
        if live.read(CELL) != 3:
            raise AssertionError('initial external cell admission was not real')
        live.write(CELL, 4)
        if live.read(CELL) != 4:
            raise AssertionError('live write did not commit')
        try:
            live.write(CELL, 12)
        except CellContentRejected:
            if live.read(CELL) != 4:
                raise AssertionError('rejected write changed target state')
        else:
            raise AssertionError('invalid write was accepted')
    if len(seen) < 3:
        raise AssertionError('registry did not invoke live proof for admissions')
    return {'real_registry': True, 'initial_admission': True,
            'write_and_rollback': True, 'invocations': len(seen)}


def _revocations():
    outcomes = {}
    for name in ('explicit', 'artifact_set', 'generation', 'issuer'):
        executor, deployment, record = _fixture()
        if name == 'explicit':
            record.revoke()
        elif name == 'artifact_set':
            deployment._artifact_set.invalidate()
        elif name == 'generation':
            deployment._session._chain._sets[1].invalidate()
        else:
            object.__setattr__(deployment, '_session', object())
        _expect_rejected_before_vm(lambda: record.run(3))
        outcomes[name] = True
    return outcomes


def _forged_backing():
    executor, deployment, record = _fixture()
    key = next(key for key, art in deployment.artifacts.items() if art.owner == PRED)
    genuine = deployment._artifact_set._artifacts[key]
    altered = replace(genuine, chunk=(('LIT', 'violated'), ('END',)))
    altered = replace(altered, artifact_id=artifact_id(
        altered.domain, altered.generation, altered.produced_by,
        altered.state_id, altered.entity, altered.version,
        altered.owner, altered.chunk, altered.reused_from,
    ))
    altered.verify()
    deployment._artifact_set._artifacts[key] = altered
    try:
        _expect_rejected_before_vm(
            lambda: executor.run(deployment, PRED, 3, policy=PURE_POLICY)
        )
        if record.run(3) != 'satisfied':
            raise AssertionError('forged backing changed approved execution')
    finally:
        deployment._artifact_set._artifacts[key] = genuine
    return {'forgery_was_self_consistent': True,
            'original_rejected': True,
            'live_snapshot_accepted_authentic_code': True,
            'strict_rejection_parity': False,
            'forged_chunk_executed': False,
            'classification': 'unresolved_contract_difference'}


def _decoded_metadata():
    executor, deployment, record = _fixture()
    value = deployment._target.state.values[PRED]
    authentic = _definition_of(value)
    try:
        object.__setattr__(value, '_definition', replace(
            authentic, links={'unproven': (PRED,)},
        ))
        _expect_rejected_before_vm(
            lambda: executor.run(deployment, PRED, 3, policy=PURE_POLICY)
        )
        outcome = None
        try:
            outcome = record.run(3)
        except BaseException as exc:
            outcome = type(exc).__name__
    finally:
        object.__setattr__(value, '_definition', authentic)
    return {'original_rejected': True, 'live_proof_outcome': outcome,
            'source_definition_was_mutated': True,
            'classification': 'unresolved_source_graph_integrity'}


def _multi_external():
    first = External('audit.a')
    second = External('audit.b')
    constraint = AllOf(first, second)
    budget = 16
    observations = []

    def callbacks(log):
        def call(label):
            def inner(subject):
                log.append((label, canonicalize(subject)))
                return ConstraintResult.SATISFIED
            return inner
        return {'audit.a': call('a'), 'audit.b': call('b')}

    baseline_log = []
    original = candidate._run_external_continuation(
        constraint, 3, budget, callbacks(baseline_log),
    )
    experimental_log = []
    prepared = candidate._private_dynamic_preparation
    with ExitStack() as stack:
        def intercept_prepare(*args, **kwargs):
            executor, deployment, entry = prepared(*args, **kwargs)
            run_original = executor.run
            grants = {}

            def substitute_run(selected, function, *arguments, policy=None):
                if selected is not deployment:
                    return run_original(selected, function, *arguments, policy=policy)
                effects = (RestrictionPolicy() if policy is None else policy)
                key = (function, effects.allowed_effects)
                if key not in grants:
                    grants[key] = _LiveAdmission(executor, deployment, function, effects)
                observations.append(function.value)
                return grants[key].run(*arguments)

            # Under one operation scope, preserve the substitution throughout
            # every continuation resume. The original VM is still used.
            stack.enter_context(patch.object(executor, 'run', side_effect=substitute_run))
            return executor, deployment, entry

        stack.enter_context(patch.object(candidate, '_private_dynamic_preparation',
                                         side_effect=intercept_prepare))
        adapted = candidate._run_external_continuation(
            constraint, 3, budget, callbacks(experimental_log),
        )
    if (original != adapted or baseline_log != experimental_log
            or len(experimental_log) != 2 or not observations):
        raise AssertionError('dynamic External callback/continuation parity failed')
    return {'callbacks': len(experimental_log), 'continuation_vm_entries': len(observations),
            'callback_order_equal': True, 'observed_subjects_equal': True,
            'result_equal': True}


def _gh123(samples):
    cache = {}
    row, preparations, params = previous._gh123_case('int_kind', cache)
    evidence = []
    for variant, (executor, deployment, entry) in zip(
        ('generic', 'specialized'), preparations,
    ):
        expected = row['expected']
        start = perf_counter_ns()
        record = _LiveAdmission(executor, deployment, entry, RestrictionPolicy())
        preparation = perf_counter_ns()-start
        baseline = lambda: executor.run(deployment, entry, *params)
        quick = lambda: record.run(*params)
        for operation in (baseline, quick):
            if operation() != expected:
                raise AssertionError(f'{variant}: incorrect SHEAR result')
        observations = {'original_ns': [], 'live_ns': []}
        for i in range(samples):
            for label, fn in (
                (('original_ns', baseline), ('live_ns', quick)) if i % 2 else
                (('live_ns', quick), ('original_ns', baseline))
            ):
                started = perf_counter_ns()
                if fn() != expected:
                    raise AssertionError(f'{variant}: benchmark semantic divergence')
                observations[label].append(perf_counter_ns()-started)
        reference = statistics.median(observations['original_ns'])
        sealed = statistics.median(observations['live_ns'])
        evidence.append({
            'variant': variant, 'sample_count_per_path': samples,
            'original_median_ns': reference,
            'live_median_ns': sealed,
            'ratio_original_over_live': reference / sealed if sealed else None,
            'prepare_ns': preparation, 'approved_nodes': len(record.approved),
            'artifacts_in_deployment': len(deployment.artifacts),
            'runtime_shared_with_original': record.runtime is deployment._target.runtime,
        })
    return evidence


def _head():
    return subprocess.run(['git', 'rev-parse', 'HEAD'], check=True,
                          capture_output=True, text=True).stdout.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--suite', choices=('smoke', 'representative'), default='smoke')
    parser.add_argument('--samples', type=int, default=4)
    args = parser.parse_args(argv)
    if args.samples < 1:
        parser.error('--samples must be positive')
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    checks = [
        ('original_runtime_trace_and_no_fallback', _authentic),
        ('explicit_read_and_denied_effect', _read_and_denied),
        ('real_cell_admission_and_rollback', _registry_admission),
        ('revocation', _revocations),
        ('rehashed_backing_contract_difference', _forged_backing),
        ('decoded_source_memo_integrity', _decoded_metadata),
    ]
    if args.suite == 'representative':
        checks.extend([
            ('dynamic_multi_external_continuation', _multi_external),
            ('gh123_int_kind_performance', lambda: _gh123(args.samples)),
        ])
    metadata = {
        'head': _head(), 'source_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'python': sys.version, 'platform': platform.platform(),
        'suite': args.suite, 'samples': args.samples,
        'production_files_modified': False,
        'uses_existing_runtime_and_vm': True,
        'security_contract_approved': False,
        'current_blockers': [
            'untracked host-private mutation and mutable live decoded source',
            'no immutable authoritative source graph / write barrier',
            'one thin integration example is not frozen Task 32 / GH-123 acceptance',
        ],
    }
    (out / 'metadata.json').write_text(json.dumps(metadata, indent=2, sort_keys=True)+'\n')
    results = []
    failures = 0
    with (out / 'cases.jsonl').open('w') as stream:
        for name, check in checks:
            try:
                value = check()
                status = 'unresolved_gap' if name in (
                    'rehashed_backing_contract_difference',
                    'decoded_source_memo_integrity',
                ) else 'passed'
            except BaseException as exc:
                failures += 1
                status = 'failed'
                value = {'exception': type(exc).__name__, 'error': str(exc),
                         'traceback': traceback.format_exc()}
            event = {'name': name, 'status': status, 'observation': value}
            stream.write(json.dumps(event, sort_keys=True)+'\n')
            stream.flush()
            results.append(event)
            print(f'{name}: {status}', flush=True)
    summary = {
        'head': metadata['head'], 'complete': not failures,
        'production_acceptance': False,
        'decision': ('INTEGRATION_EXPERIMENT_FAILED' if failures else
                     'LIVE_RUNTIME_POSSIBLE_AUTHORITY_AND_SOURCE_GRAPH_UNQUALIFIED'),
        'cases': {r['name']: r['status'] for r in results},
        'observations': {r['name']: r['observation'] for r in results},
    }
    (out / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'complete': summary['complete'], 'decision': summary['decision'],
                      'cases': summary['cases']}, indent=2, sort_keys=True), flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
