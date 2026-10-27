"""GH-123 experimental detached executable snapshot and security contract audit.

This is NOT a production proof-cache implementation. It intentionally uses a
SEPARATE runtime and detached authenticated copies, to ask whether preflight
and per-node validation can be amortized without executing forged code.
It does NOT claim to preserve the existing RestrictedExecutor.run boundary:
mutating an original admitted artifact may cause the original runner to REJECT,
while the detached runner continues to execute the original sealed artifact.
That contract divergence is a BLOCKER, not a successful security acceptance.

No production class, preflight, authentication, resolver or VM implementation
is patched. The experiment does not cover host callbacks or mutable effects.
An untrusted actor with arbitrary host Python reflection can modify private
runtime objects, including this prototype: Python dataclass freezing is NOT
an adversarial immutability guarantee. A production design needs an actual
encapsulation and revocation boundary rather than this experimental copy.

Run via the existing opt-in .github/workflows/experiments.yml:
    python -m tests.constraint_functions_sealed_snapshot_experiment \\
        --output-dir experiment-output --suite smoke
    python -m tests.constraint_functions_sealed_snapshot_experiment \\
        --output-dir experiment-output --suite representative
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
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

from shear.canonical import canonicalize
from shear.hosted_bootstrap import AdmissionRejected, restricted
from shear.hosted_bootstrap.artifacts import artifact_id
from shear.hosted_bootstrap.restricted_policy import RestrictionPolicy, preflight
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from shear.lang import _definition_of, load, program
from shear.machine import run as machine_run
from shear.runtime import Runtime
from shear.state import State
from shear.values import Value
from tests import constraint_functions_size_experiment as size
from tests.test_restricted_execution import PRED, PURE_POLICY, evaluator_source


class _SealedResolver:
    """No lowering fallback; only explicitly proved node/version/owner keys."""
    def __init__(self, runtime, state, approved, chunks):
        self.runtime = runtime
        self.version = runtime.active
        self.state = state
        self.approved = approved
        self.chunks = chunks

    def __call__(self, state, entity, owner):
        raise AdmissionRejected('sealed invocation must request pinned version')

    def for_version(self, version, entity, owner):
        if (version is not self.version or self.runtime.active is not self.version
                or version.state is not self.state):
            raise AdmissionRejected('sealed invocation changed its version')
        value = version.state.values.get(entity)
        if value is None:
            raise AdmissionRejected('sealed source node is missing')
        key = (entity, value.version_id)
        if key not in self.approved:
            raise AdmissionRejected('sealed invocation opened an unproved node')
        selected = self.chunks.get(key)
        if selected is None or selected[0] != owner:
            raise AdmissionRejected('sealed invocation changed admitted code owner')
        return selected[1]


class _SealedSnapshot:
    """Separate version/bytecode view with live O(1) *partial* revocation.

    This is a prospective shape only, not a fully qualified guard: undetected
    original mapping/decoded-cache mutation can change rejection behavior.
    """
    def __init__(self, executor, deployment, entry, policy):
        if policy.allowed_effects:
            raise ValueError('experimental sealed runner only supports PURE policy')
        executor._check_deployment(deployment)
        original_state = deployment._target.state
        original_approved = preflight(original_state, deployment.artifacts, entry, policy)
        issued = executor._issued.get(deployment)
        if issued is None:
            raise AdmissionRejected('not an issued deployment')
        self.executor, self.deployment = executor, deployment
        self.issued = issued
        self.session, self.target, self.artifact_set, self.authenticated = issued
        self.active = self.target.runtime.active
        self.generation = self.session._chain._sets.get(deployment.compiler_generation)
        if self.generation is None or not self.generation.valid:
            raise AdmissionRejected('missing compiler generation')
        self.owner = executor._identity
        self.entry = deepcopy(entry)
        self.policy_effects = policy.allowed_effects

        # Recreate all canonical source values from semantic CONTENT, not from
        # Value's decoded relation/definition memo fields. Copy nested IDs.
        detached_values = {}
        for key, value in original_state.values.items():
            new_key = deepcopy(key)
            detached_values[new_key] = Value.create(new_key, deepcopy(value.content))
        detached = State.create(detached_values, deepcopy(dict(original_state.ownership)))
        if detached.id != original_state.id or detached.semantic_digest != original_state.semantic_digest:
            raise AssertionError('detached source differs from authenticated semantic source')
        if any(detached.values[key] is original_state.values[key] for key in original_state.values):
            raise AssertionError('shared source value object in detached view')

        detached_artifacts = {}
        for old_key, artifact in deployment.artifacts.items():
            from dataclasses import replace
            copied = replace(deepcopy(artifact), chunk=tuple(
                deepcopy(item) for item in artifact.chunk
            ))
            copied.verify()
            new_key = (copied.entity, copied.version)
            if new_key != old_key or new_key in detached_artifacts:
                raise AssertionError('detached admitted identity differs')
            if copied is artifact or copied.chunk is artifact.chunk:
                raise AssertionError('shared artifact or chunk in detached view')
            detached_artifacts[new_key] = copied
        approved = preflight(detached, MappingProxyType(detached_artifacts), self.entry, policy)
        if approved != original_approved:
            raise AssertionError('detached preflight differs from original proof')

        self.runtime = Runtime(detached)
        self.sealed_version = self.runtime.active
        self.approved = approved
        self.chunks = MappingProxyType({
            key: (artifact.owner, artifact.chunk)
            for key, artifact in detached_artifacts.items()
            if key in approved
        })
        self.resolver = _SealedResolver(self.runtime, detached, approved, self.chunks)
        self.artifact_count = len(detached_artifacts)
        self.proved_count = len(approved)
        self.state_id = detached.id

    def _guard(self):
        """Constant-time lifetime checks; NOT complete mutation detection."""
        d = self.deployment
        if self.executor._issued.get(d) is not self.issued or d._owner is not self.owner:
            raise AdmissionRejected('seal lost original issuance')
        if (d._session is not self.session or d._target is not self.target
                or d._artifact_set is not self.artifact_set
                or d.artifacts is not self.authenticated
                or self.target._artifacts is not self.artifact_set
                or self.target._sets.get(self.target.runtime.active) is not self.artifact_set):
            raise AdmissionRejected('seal lost original admitted binding')
        if self.target.runtime.active is not self.active:
            raise AdmissionRejected('seal runtime activated another version')
        if (self.active.state.id != self.state_id
                or d.source_state_id != self.state_id
                or d.compiler_generation != self.target.compiler_generation):
            raise AdmissionRejected('seal source/compiler version changed')
        if self.runtime.active is not self.sealed_version:
            raise AdmissionRejected('sealed runtime activated another version')
        if not self.artifact_set.valid:
            raise AdmissionRejected('seal artifact set invalidated')
        if (self.session._chain._sets.get(d.compiler_generation) is not self.generation
                or not self.generation.valid):
            raise AdmissionRejected('seal compiler generation revoked')

    def run(self, *args):
        self._guard()
        # No call to production run: deliberately a distinct prototype with
        # different trace/admission behavior. Arguments match its VM boundary.
        return machine_run(self.runtime, self.entry, *(canonicalize(x) for x in args),
                           resolver=self.resolver, may_activate=False)


def _baseline_case():
    source = evaluator_source()
    executor = RestrictedExecutor()
    deployment = executor.deploy(source, compiler_generation=1)
    return executor, deployment, PRED, PURE_POLICY, (3,), 'satisfied'


def _gh123_case(name, cache):
    rows = {row['name']: row for row in size._cases('representative-scaling')}
    row = rows[name]
    expression = row['expression']
    constraint = size.candidate._constraint(expression)
    subject = size.candidate._materialize_subject(row['subject'])
    registrations = tuple(row['externals'])
    params = (subject, constraint, row['budget'], registrations)
    if name not in cache:
        generic_e, generic_d, generic_entry = size.candidate._generic_registered_deployment(
            registrations, size.GENERATION, size.candidate._PRIVATE_SEMANTIC_AUTHORITY,
        )
        forms = size._forms(expression)
        source = load(program(size._minimal_entities(forms)))
        special_e = RestrictedExecutor()
        special_d = special_e.deploy(source, compiler_generation=size.GENERATION)
        cache[name] = (
            (generic_e, generic_d, generic_entry),
            (special_e, special_d, size.candidate.REGISTERED_ENTRY),
        )
    return row, cache[name], params


def _measure(label, executor, deployment, entry, params, expected, reps):
    # Full original preflight is used to admit EVERY sealed view once.
    reference = lambda: executor.run(deployment, entry, *params)
    seal_started = perf_counter_ns()
    seal = _SealedSnapshot(executor, deployment, entry, RestrictionPolicy())
    seal_ns = perf_counter_ns()-seal_started
    speculative = lambda: seal.run(*params)
    for f in (reference, speculative):
        if f() != expected or f() != expected:
            raise AssertionError('original vs detached semantic mismatch')
    original_ns=[]
    sealed_ns=[]
    for i in range(reps):
        if i%2:
            first=[('sealed',speculative),('original',reference)]
        else:
            first=[('original',reference),('sealed',speculative)]
        for mode, operation in first:
            t=perf_counter_ns()
            observed=operation()
            d=perf_counter_ns()-t
            if observed!=expected:
                raise AssertionError(f'{label} {mode} divergent value {observed!r}')
            (sealed_ns if mode=='sealed' else original_ns).append(d)
    original_med=statistics.median(original_ns)
    sealed_med=statistics.median(sealed_ns)
    return {
        'label':label,
        'observations_per_path':reps,
        'original_median_ns':original_med,
        'sealed_median_ns':sealed_med,
        'potential_speedup':original_med/sealed_med,
        'seal_prepare_ns':seal_ns,
        'seal_break_even_calls_estimate':(
            seal_ns/(original_med-sealed_med) if original_med>sealed_med else None
        ),
        'original_min_ns':min(original_ns),
        'sealed_min_ns':min(sealed_ns),
        'original_max_ns':max(original_ns),
        'sealed_max_ns':max(sealed_ns),
        'admitted_artifacts':seal.artifact_count,
        'approved_nodes':seal.proved_count,
        'note':'NOT production-equivalent; no artifact-set mutation detection / trace parity',
    }


def _require_original_rejects(executor, deployment, entry, args, policy):
    with patch.object(restricted.machine, 'run', side_effect=AssertionError('VM reached')) as vm:
        try:
            executor.run(deployment, entry, *args, policy=policy)
        except AdmissionRejected:
            if vm.called:
                raise AssertionError('original rejected only after entering VM')
            return True
    raise AssertionError('original unexpectedly admitted altered security state')


def _adversarial_cases():
    results=[]
    def record(name, run):
        try:
            result=run()
            results.append({'name':name,'status':'passed', **result})
        except BaseException as exc:
            results.append({'name':name,'status':'failed',
                'exception':type(exc).__name__,'error':str(exc),
                'traceback':traceback.format_exc()})

    def stable_baseline():
        ex,d,e,p,args,expected=_baseline_case()
        seal=_SealedSnapshot(ex,d,e,p)
        for subject in (3,12,-3):
            if ex.run(d,e,subject,policy=p)!=seal.run(subject):
                raise AssertionError('detached semantics differ')
        return {'detached_matches_original':True}
    record('authentic_reuse',stable_baseline)

    def mut_artifact():
        ex,d,e,p,args,expected=_baseline_case()
        seal=_SealedSnapshot(ex,d,e,p)
        key=next(key for key,a in d.artifacts.items() if a.owner==e)
        original=d._artifact_set._artifacts[key]
        # Substituted self-consistent bytecode whose key remains identical.
        from dataclasses import replace
        altered=replace(original,chunk=(('LIT','violated'),('END',)))
        altered=replace(altered,artifact_id=artifact_id(
            altered.domain,altered.generation,altered.produced_by,
            altered.state_id,altered.entity,altered.version,
            altered.owner,altered.chunk,altered.reused_from))
        altered.verify()
        d._artifact_set._artifacts[key]=altered
        try:
            _require_original_rejects(ex,d,e,args,p)
            # The detached runner uses original admitted contents but DOES NOT
            # reject the altered original mapping. Record this contract gap.
            if seal.run(*args)!=expected:
                raise AssertionError('forged original code changed detached behavior')
        finally:
            d._artifact_set._artifacts[key]=original
        return {'forged_code_executed':False,'original_rejected':True,
                'sealed_rejected':False,'production_equivalent':False,
                'blocker':'artifact substitution did not revoke snapshot'}
    record('artifact_substitution_contract_gap',mut_artifact)

    def in_place_artifact():
        ex,d,e,p,args,expected=_baseline_case()
        seal=_SealedSnapshot(ex,d,e,p)
        old=next(a for a in d.artifacts.values() if a.owner==e)
        old_chunk=old.chunk
        try:
            object.__setattr__(old,'chunk',(('LIT','violated'),('END',)))
            _require_original_rejects(ex,d,e,args,p)
            if seal.run(*args)!=expected:
                raise AssertionError('modified original chunk reached sealed view')
        finally:
            object.__setattr__(old,'chunk',old_chunk)
        return {'forged_code_executed':False,'original_rejected':True,
                'sealed_rejected':False,'production_equivalent':False,
                'blocker':'in-place original artifact mutation did not revoke snapshot'}
    record('in_place_artifact_contract_gap',in_place_artifact)

    def mut_definition():
        ex,d,e,p,args,expected=_baseline_case()
        seal=_SealedSnapshot(ex,d,e,p)
        from dataclasses import replace
        value=d._target.state.values[e]
        definition=_definition_of(value)
        try:
            object.__setattr__(value,'_definition',replace(
                definition,links={'bad':(e,)}))
            _require_original_rejects(ex,d,e,args,p)
            if seal.run(*args)!=expected:
                raise AssertionError('forged decoded metadata changed detached behavior')
        finally:
            object.__setattr__(value,'_definition',definition)
        return {'forged_code_executed':False,'original_rejected':True,
                'sealed_rejected':False,'production_equivalent':False,
                'blocker':'decoded metadata mutation did not revoke snapshot'}
    record('decoded_metadata_contract_gap',mut_definition)

    def removed_gen():
        ex,d,e,p,args,expected=_baseline_case()
        seal=_SealedSnapshot(ex,d,e,p)
        generations=d._session._chain._sets
        saved=generations.pop(1)
        try:
            _require_original_rejects(ex,d,e,args,p)
            try:
                seal.run(*args)
            except AdmissionRejected:
                pass
            else:
                raise AssertionError('revoked generation admitted by seal')
        finally:
            generations[1]=saved
        return {'revocation_rejected':True}
    record('compiler_generation_revocation',removed_gen)

    def invalid_generation():
        ex,d,e,p,args,expected=_baseline_case()
        seal=_SealedSnapshot(ex,d,e,p)
        d._session._chain._sets[1].invalidate()
        _require_original_rejects(ex,d,e,args,p)
        try:
            seal.run(*args)
        except AdmissionRejected:
            return {'revocation_rejected':True}
        raise AssertionError('invalid compiler generation admitted by seal')
    record('compiler_generation_invalidated',invalid_generation)

    def invalidation():
        ex,d,e,p,args,expected=_baseline_case()
        seal=_SealedSnapshot(ex,d,e,p)
        d._artifact_set.invalidate()
        _require_original_rejects(ex,d,e,args,p)
        try:
            seal.run(*args)
        except AdmissionRejected:
            return {'revocation_rejected':True}
        raise AssertionError('invalidated artifact set admitted by seal')
    record('artifact_set_invalidation',invalidation)

    def issuer():
        ex,d,e,p,args,expected=_baseline_case()
        seal=_SealedSnapshot(ex,d,e,p)
        old=d._session
        try:
            object.__setattr__(d,'_session',object())
            _require_original_rejects(ex,d,e,args,p)
            try:
                seal.run(*args)
            except AdmissionRejected:
                return {'revocation_rejected':True}
            raise AssertionError('rebound issuer admitted by seal')
        finally:
            object.__setattr__(d,'_session',old)
    record('issuer_rebinding',issuer)

    def wrong_policy():
        ex,d,e,p,args,expected=_baseline_case()
        seal=_SealedSnapshot(ex,d,e,p)
        if seal.run(*args)!=expected:
            raise AssertionError('pure case changed')
        try:
            _SealedSnapshot(ex,d,e,RestrictionPolicy(frozenset({'read'})))
        except ValueError:
            return {'effectful_proof_forbidden':True}
        raise AssertionError('effectful snapshot admitted')
    record('effectful_policy_rejected',wrong_policy)
    return results


def _git_head():
    return subprocess.run(['git','rev-parse','HEAD'],capture_output=True,check=True,text=True).stdout.strip()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',required=True)
    p.add_argument('--suite',choices=('smoke','representative','scaling'),default='smoke')
    p.add_argument('--samples',type=int,default=12)
    args=p.parse_args(argv)
    if args.samples<1:
        p.error('--samples must be positive')
    out=Path(args.output_dir)
    out.mkdir(parents=True,exist_ok=True)
    metadata={'head':_git_head(),'python':sys.version,'platform':platform.platform(),
              'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
              'suite':args.suite,'samples':args.samples,
              'production_code_modified':False,'production_acceptance_ready':False,
              'security_threat_model':'trusted host Python; reflective mutation deliberately tested as boundary mismatch',
              'unmeasured':'dynamic External callbacks; effectful operations; full adapter; trace fidelity'}
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2,sort_keys=True)+'\n')
    security=_adversarial_cases()
    (out/'security-cases.json').write_text(json.dumps(security,indent=2,sort_keys=True)+'\n')
    performance=[]
    failures=[]
    try:
        ex,d,e,p,params,expected=_baseline_case()
        performance.append(_measure('task32_fixture',ex,d,e,params,expected,args.samples))
        names=(('int_kind',) if args.suite=='smoke' else (
            ('int_kind','one_of_present','pair_three') if args.suite=='representative'
            else ('all_of_nodes_8','all_of_nodes_64','all_of_nodes_256')))
        cache={}
        for name in names:
            row,deployments,parameters=_gh123_case(name,cache)
            for label,(executor,deployment,entry) in zip(('generic','specialized'),deployments):
                performance.append(_measure(f'{name}:{label}',executor,deployment,
                  entry,parameters,row['expected'],args.samples))
    except BaseException as exc:
        failures.append({'exception':type(exc).__name__,'error':str(exc),
                         'traceback':traceback.format_exc()})
    (out/'performance.json').write_text(json.dumps(performance,indent=2,sort_keys=True)+'\n')
    all_pass=not failures and all(row['status']=='passed' for row in security)
    summary={**metadata,'complete':all_pass,'failures':failures,'adversarial_cases':security,
             'performance':performance,
             'decision':'NOT_PRODUCTION_ACCEPTABLE_REJECTION_PARITY_GAP',
             'why':'verified detached executable can ignore mutations that the existing executor must reject',
             'next_requirement':'enforced immutability or mutation-complete revocation before fast path'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'head':metadata['head'],'complete':all_pass,
      'adversarial_cases':{r['name']:r['status'] for r in security},
      'performance':[{'case':r['label'],'speedup':round(r['potential_speedup'],3),
        'seal_prepare_ms':round(r['seal_prepare_ns']/1e6,2)} for r in performance],
      'failures':failures,'decision':summary['decision']},indent=2))
    return 0 if all_pass else 1


if __name__=='__main__':
    raise SystemExit(main())
