"""GH-123: experimental revocable admission record, with explicit threat boundary.

This is a SECURITY-CONTRACT EXPERIMENT, not an accepted proof cache.
It reuses the previously committed sealed-snapshot prototype, which copies
source/artifacts and runs real SHEAR VM bytecode. Its principal question is
whether a constant-time admission epoch reproduces Task 32 rejection semantics.

The record rejects tracked mutations and native lifetime revocations before
entering the sealed VM. A raw mutation of mutable host-private objects is not
instrumented; those intentional strict-parity differences are reported, never called security passes.

Production code, frozen acceptance tests and existing checks are unchanged.
The prototype is pure-only, detached from production trace/admission execution,
and does not support dynamic External callbacks.

Usage:
  python -m tests.constraint_functions_admission_record_experiment \\
    --output-dir experiment-output --suite smoke
  python -m tests.constraint_functions_admission_record_experiment \\
    --output-dir experiment-output --suite full --samples 8
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from time import perf_counter_ns
import traceback
from unittest.mock import patch

from shear.hosted_bootstrap import AdmissionRejected, restricted
from shear.hosted_bootstrap.artifacts import artifact_id
from shear.lang import _definition_of
from tests import constraint_functions_sealed_snapshot_experiment as previous


@dataclass(frozen=True)
class _Grant:
    """Non-transferable in the *trusted host API* model, not Python security."""
    epoch: int
    issuer_label: str


class _AdmissionRecord:
    """Controlled issuer: O(1) epoch check plus existing snapshot lifetime guard.

    A record is issued only after the previous prototype authenticates and
    preflights a detached copy. The source and chunks are never replaced in
    this record. Changing a managed original invalidates the entire grant.
    Direct access to _snapshot or original private Python objects BYPASSES
    this contract, and is deliberately exercised below.
    """
    def __init__(self, executor, deployment, entry, policy):
        self._snapshot = previous._SealedSnapshot(
            executor, deployment, entry, policy,
        )
        self._epoch = 0
        self._revoked = False
        self._reason = None
        self._grant = _Grant(self._epoch, 'experiment-only')

    def issue(self):
        if self._revoked:
            raise AdmissionRejected('cannot issue from a revoked admission')
        self._snapshot._guard()
        return self._grant

    def revoke(self, reason: str) -> None:
        if not self._revoked:
            self._revoked = True
            self._epoch += 1
            self._reason = reason

    def _authorize(self, grant) -> None:
        if (
            self._revoked or grant is not self._grant
            or not isinstance(grant, _Grant)
            or grant.epoch != self._epoch
        ):
            raise AdmissionRejected('expired, foreign or revoked admission grant')
        # Native lifetime checks: issuer, active state, compiler generation,
        # artifact-set validity, etc. No repeated artifact hash iteration.
        self._snapshot._guard()

    def run(self, grant, *args):
        self._authorize(grant)
        return self._snapshot.run(*args)

    def managed_artifact_replacement(self, key, replacement):
        """Cooperative host mutation API; intentionally revokes FIRST."""
        self.revoke('artifact replacement')
        artset = self._snapshot.artifact_set
        artset._artifacts[key] = replacement
        artset._chunks[key] = replacement.chunk

    def managed_definition_replacement(self, value, definition):
        """Another cooperative API. Python reflection can bypass it."""
        self.revoke('source/definition replacement')
        object.__setattr__(value, '_definition', definition)


def _fixture():
    executor, deployment, entry, policy, args, expected = previous._baseline_case()
    record = _AdmissionRecord(executor, deployment, entry, policy)
    grant = record.issue()
    if record.run(grant, *args) != expected:
        raise AssertionError('issued record failed baseline execution')
    return executor, deployment, entry, policy, args, expected, record, grant


def _rejected_before_sealed_vm(record, grant, args):
    """A refusal cannot invoke the sealed runner, even once."""
    with patch.object(record._snapshot, 'run',
                      side_effect=AssertionError('sealed VM entered')) as opened:
        try:
            record.run(grant, *args)
        except AdmissionRejected as exc:
            if opened.called:
                raise AssertionError('revocation reached sealed VM')
            return {'rejected': type(exc).__name__, 'before_sealed_vm': True}
    raise AssertionError('record did not reject a revoked or invalid invocation')


def _original_rejected(executor, deployment, entry, args, policy):
    """Original Task 32 refusal must precede machine.run."""
    with patch.object(restricted.machine, 'run',
                      side_effect=AssertionError('original VM entered')) as opened:
        try:
            executor.run(deployment, entry, *args, policy=policy)
        except AdmissionRejected:
            if opened.called:
                raise AssertionError('original VM entered despite rejection')
            return True
    raise AssertionError('original runner accepted a changed deployment')


def _owner_artifact(deployment, entry):
    for key, art in deployment.artifacts.items():
        if art.owner == entry:
            return key, art
    raise AssertionError('no admitted entry artifact')


def _substituted(artifact):
    """A self-consistent rehash, not an ordinary broken-integrity fixture."""
    replacement = replace(artifact, chunk=(('LIT', 'violated'), ('END',)))
    replacement = replace(replacement, artifact_id=artifact_id(
        replacement.domain, replacement.generation, replacement.produced_by,
        replacement.state_id, replacement.entity, replacement.version,
        replacement.owner, replacement.chunk, replacement.reused_from,
    ))
    replacement.verify()
    return replacement


def _safe_case(name, callback, results):
    try:
        result = callback()
        if result.pop('classification') not in ('managed_rejection', 'contract_gap'):
            raise AssertionError('unknown result classification')
        classification = ('observed_parity_gap' if result.pop('gap', False) else 'passed')
        results.append({'case': name, 'status': classification, **result})
    except BaseException as exc:
        results.append({
            'case': name, 'status': 'failed', 'error_type': type(exc).__name__,
            'error': str(exc), 'traceback': traceback.format_exc(),
        })


def _cases(suite: str):
    output = []

    def pristine():
        ex,d,e,p,a,expected,record,grant = _fixture()
        for subject in (3,12,-3):
            actual = ex.run(d,e,subject,policy=p)
            if record.run(grant,subject) != actual:
                raise AssertionError('pristine original/record results differ')
        return {'classification':'managed_rejection','checks':3,
                'semantic_match':True}
    _safe_case('pristine_equivalence', pristine, output)

    def foreign():
        _,_,_,_,args,_,record,grant = _fixture()
        other = _Grant(grant.epoch, grant.issuer_label)
        if other == grant and other is grant:
            raise AssertionError('different grant unexpectedly has same identity')
        return {'classification':'managed_rejection',
                **_rejected_before_sealed_vm(record,other,args)}
    _safe_case('foreign_grant_refusal', foreign, output)

    def explicit():
        _,_,_,_,args,_,record,grant = _fixture()
        record.revoke('requested retirement')
        return {'classification':'managed_rejection',
                **_rejected_before_sealed_vm(record,grant,args)}
    _safe_case('explicit_epoch_revocation', explicit, output)

    def managed_artifact():
        ex,d,e,p,args,_,record,grant = _fixture()
        key,authentic = _owner_artifact(d,e)
        record.managed_artifact_replacement(key,_substituted(authentic))
        _original_rejected(ex,d,e,args,p)
        return {'classification':'managed_rejection',
                **_rejected_before_sealed_vm(record,grant,args)}
    _safe_case('managed_artifact_replacement', managed_artifact, output)

    def managed_metadata():
        ex,d,e,p,args,_,record,grant = _fixture()
        value=d._target.state.values[e]
        old=_definition_of(value)
        record.managed_definition_replacement(value,replace(
            old,links={'corrupted':(e,)}))
        _original_rejected(ex,d,e,args,p)
        return {'classification':'managed_rejection',
                **_rejected_before_sealed_vm(record,grant,args)}
    _safe_case('managed_definition_replacement', managed_metadata, output)

    def invalidated():
        ex,d,e,p,args,_,record,grant = _fixture()
        d._artifact_set.invalidate()  # Native Task 32 API, no epoch call.
        _original_rejected(ex,d,e,args,p)
        return {'classification':'managed_rejection',
                **_rejected_before_sealed_vm(record,grant,args)}
    _safe_case('native_artifact_set_invalidation', invalidated, output)

    def generation():
        ex,d,e,p,args,_,record,grant = _fixture()
        gen=d._session._chain._sets[d.compiler_generation]
        gen.invalidate()  # Native generation lifetime API, no epoch call.
        _original_rejected(ex,d,e,args,p)
        return {'classification':'managed_rejection',
                **_rejected_before_sealed_vm(record,grant,args)}
    _safe_case('native_compiler_generation_invalidation', generation, output)

    def issuer():
        ex,d,e,p,args,_,record,grant = _fixture()
        original=d._session
        try:
            object.__setattr__(d,'_session',object())
            _original_rejected(ex,d,e,args,p)
            observation=_rejected_before_sealed_vm(record,grant,args)
        finally:
            object.__setattr__(d,'_session',original)
        return {'classification':'managed_rejection',**observation}
    _safe_case('native_issuer_rebinding_guard', issuer, output)

    def unrelated():
        _,_,_,_,args,expected,first,first_grant=_fixture()
        _,_,_,_,otherargs,otherexpected,second,second_grant=_fixture()
        first.revoke('replaced in registry')
        _rejected_before_sealed_vm(first,first_grant,args)
        if second.run(second_grant,*otherargs)!=otherexpected:
            raise AssertionError('unrelated grant revoked by another issuer')
        return {'classification':'managed_rejection',
                'unrelated_new_issuer_unaffected':True}
    _safe_case('unrelated_replacement_stays_live', unrelated, output)

    if suite == 'full':
        # These must remain visible BLOCKERS: stable epoch and native lifetime
        # do not detect untracked Python mutation. There is no way to claim
        # compliance merely because the copied bytecode stays authentic.
        def untracked_artifact():
            ex,d,e,p,args,expected,record,grant=_fixture()
            key,authentic=_owner_artifact(d,e)
            d._artifact_set._artifacts[key]=_substituted(authentic)
            try:
                _original_rejected(ex,d,e,args,p)
                if record.run(grant,*args)!=expected:
                    raise AssertionError('detached result changed')
            finally:
                d._artifact_set._artifacts[key]=authentic
            return {'classification':'contract_gap','gap':True,
                    'original_rejects':True,'record_rejects':False,
                    'forged_chunk_executed':False,
                    'reason':'untracked admitted map mutation does not increment epoch'}
        _safe_case('UNTRACKED_artifact_rehash_gap',untracked_artifact,output)

        def untracked_chunk():
            ex,d,e,p,args,expected,record,grant=_fixture()
            _,original=_owner_artifact(d,e)
            old=original.chunk
            try:
                object.__setattr__(original,'chunk',(('LIT','violated'),('END',)))
                _original_rejected(ex,d,e,args,p)
                if record.run(grant,*args)!=expected:
                    raise AssertionError('detached result changed')
            finally:
                object.__setattr__(original,'chunk',old)
            return {'classification':'contract_gap','gap':True,
                    'original_rejects':True,'record_rejects':False,
                    'reason':'raw object.__setattr__ is invisible to issuer'}
        _safe_case('UNTRACKED_in_place_chunk_gap',untracked_chunk,output)

        def untracked_metadata():
            ex,d,e,p,args,expected,record,grant=_fixture()
            value=d._target.state.values[e]
            old=_definition_of(value)
            try:
                object.__setattr__(value,'_definition',replace(
                    old,links={'corrupted':(e,)}))
                _original_rejected(ex,d,e,args,p)
                if record.run(grant,*args)!=expected:
                    raise AssertionError('detached result changed')
            finally:
                object.__setattr__(value,'_definition',old)
            return {'classification':'contract_gap','gap':True,
                    'original_rejects':True,'record_rejects':False,
                    'reason':'raw decoded-function memo mutation is invisible to issuer'}
        _safe_case('UNTRACKED_decoded_metadata_gap',untracked_metadata,output)

    return output


def _timing(samples):
    """Illustrative marginal cost; NOT an absolute or acceptance benchmark."""
    _,_,_,_,args,expected,record,grant = _fixture()
    for _ in range(3):
        if record.run(grant,*args)!=expected:
            raise AssertionError('warmup result differed')
    observed = {'issuer_plus_snapshot_ns':[], 'snapshot_only_ns':[]}
    for i in range(samples):
        for label in ('issuer_plus_snapshot_ns','snapshot_only_ns') if i%2 else (
            'snapshot_only_ns','issuer_plus_snapshot_ns'
        ):
            before=perf_counter_ns()
            value=(record.run(grant,*args) if label=='issuer_plus_snapshot_ns'
                   else record._snapshot.run(*args))
            observed[label].append(perf_counter_ns()-before)
            if value != expected:
                raise AssertionError('timing case diverged')
    return {'samples':samples,'medians_ns':{k:statistics.median(v)
                                            for k,v in observed.items()},
            'limitation':'tiny paired sample; compares only two prototype paths, not production'}


def _head():
    return subprocess.run(['git','rev-parse','HEAD'],check=True,capture_output=True,
                          text=True).stdout.strip()


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',required=True)
    ap.add_argument('--suite',choices=('smoke','full'),default='smoke')
    ap.add_argument('--samples',type=int,default=6)
    args=ap.parse_args(argv)
    if args.samples<1:
        ap.error('--samples must be positive')
    path=Path(args.output_dir)
    path.mkdir(parents=True,exist_ok=True)
    metadata={
        'head':_head(), 'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
        'python':sys.version,'platform':platform.platform(), 'suite':args.suite,
        'production_changes':False,'optimizes_existing_restricted_executor':False,
        'immutable_host_python_proven':False,
        'preflight_proof_from':'tests.constraint_functions_sealed_snapshot_experiment._SealedSnapshot',
        'mutation_model':'tracked API vs untracked private Python reflection',
        'unmeasured':'dynamic External, effectful execution, complete adapter, trace parity',
    }
    (path/'metadata.json').write_text(json.dumps(metadata,indent=2,sort_keys=True)+'\n')
    results=_cases(args.suite)
    timing=None
    if not any(r['status']=='failed' for r in results):
        try:
            timing=_timing(args.samples)
        except BaseException as exc:
            results.append({'case':'illustrative_timing','status':'failed',
                            'error_type':type(exc).__name__,'error':str(exc),
                            'traceback':traceback.format_exc()})
    hard_fail=any(x['status']=='failed' for x in results)
    gaps=[x['case'] for x in results if x['status']=='observed_parity_gap']
    if args.suite=='full' and len(gaps)!=3 and not hard_fail:
        hard_fail=True
        results.append({'case':'gap_completeness','status':'failed',
                        'error':'expected three reflective-mutation parity gaps'})
    summary={'metadata':metadata,'executed':not hard_fail,'cases':results,
             'timing':timing,'strict_original_runner_parity_gaps':gaps,
             'production_acceptance':False,
             'decision':('EXPERIMENT_FAILED' if hard_fail else
               'MANAGED_REVOCATION_WORKS_DETACHED_SNAPSHOT_CONTRACT_UNQUALIFIED'),
             'rejection_parity_on_untracked_host_mutations':False,
             'authentic_detached_view_remains_unchanged_in_tested_cases':True if not hard_fail else None,
             'normative_status_of_strict_rejection_parity':'UNRESOLVED: Task 32 explicitly permits some detached immutable views',
             'required_boundary':'prove detached view is uniquely authoritative and immutable, plus explicit lifetime revocation; otherwise retain O(N) checks',
             'note':'A green experiment means its assertions ran, NOT Task 32 production acceptance'}
    (path/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    (path/'cases.jsonl').write_text(''.join(json.dumps(x,sort_keys=True)+'\n'
                                           for x in results))
    print(json.dumps({'head':metadata['head'],'executed':summary['executed'],
                      'decision':summary['decision'],
                      'statuses':{r['case']:r['status'] for r in results},
                      'strict_parity_differences':gaps,'timing':timing},indent=2,sort_keys=True),flush=True)
    return 1 if hard_fail else 0


if __name__=='__main__':
    raise SystemExit(main())
