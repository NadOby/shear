"""GH-123 – authenticated function definitions within the existing SHEAR VM.

Experimental proof consumer; not a production proof-cache authorization.
Requires the optional `for_definition` resolver hook in shear/machine.py.
The original runner is unchanged when its resolver has no such hook.

CI:
  python -m tests.constraint_functions_definition_snapshot_experiment \
      --output-dir experiment-output --suite smoke --samples 4
  python -m tests.constraint_functions_definition_snapshot_experiment \
      --output-dir experiment-output --suite representative --samples 8
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import statistics
import subprocess
import sys
from time import perf_counter_ns
import traceback
from types import MappingProxyType
from unittest.mock import patch

from shear import AllOf, ConstraintResult, External
from shear.canonical import canonicalize
from shear.hosted_bootstrap import AdmissionRejected, restricted
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from shear.hosted_bootstrap.restricted_policy import RestrictionPolicy
from shear.lang import _definition_of, _read_definition
from shear.values import Value
from tests import constraint_functions_complete_candidate as candidate
from tests import constraint_functions_live_admission_spike as live
from tests import constraint_functions_sealed_snapshot_experiment as previous
from tests.test_restricted_execution import (
    DEAD_WRITE, PRED, PURE, PURE_CALL, PURE_POLICY, READ_POLICY,
    evaluator_source,
)


class _DefinitionResolver(live._LivePinnedResolver):
    """Supply definitions from verified canonical content, never decoded memos."""

    def for_definition(self, version, entity):
        grant = self.grant
        grant._guard()
        if version is not grant.active or version.state is not grant.state:
            raise AdmissionRejected('definition opened a different runtime version')
        value = version.state.values.get(entity)
        if value is None:
            raise AdmissionRejected('definition source entity is missing')
        if grant.definition_versions.get(entity) != value.version_id:
            raise AdmissionRejected('function definition was not preflighted')
        result = grant.definitions.get(entity)
        if result is None:
            raise AdmissionRejected('no authenticated function definition')
        grant.definition_opens += 1
        return result


class _DefinitionAdmission(live._LiveAdmission):
    """Pinned bytecode plus detached source definitions, original runtime/VM.

    The proof is issued only after existing authentication and full preflight.
    Reconstruct each executable owner's definition from canonical Value.content
    and verify that it agrees with the definition consulted during preflight.
    The snapshot is an authority candidate, not a Python isolation primitive.
    """

    def __init__(self, executor, deployment, entry, policy):
        super().__init__(executor, deployment, entry, policy)
        owners = {entry}
        owners.update(owner for owner, _chunk in self.chunks.values())
        pinned = {}
        versions = {}
        for owner in owners:
            value = self.state.values.get(owner)
            if value is None:
                raise AdmissionRejected('proved function owner disappeared')

            # Fresh Value means neither _definition nor _relation memo is copied.
            clean = Value.create(owner, value.content)
            original = _definition_of(value)
            canonical = _read_definition(clean)
            if original is None or canonical is None or original != canonical:
                raise AdmissionRejected(
                    'preflight function definition differs from canonical source'
                )

            # Freeze the nested link/label maps as well as the dataclass.
            frozen = replace(
                canonical,
                params=tuple(canonical.params),
                links=MappingProxyType(dict(canonical.links)),
                labels=MappingProxyType(dict(canonical.labels)),
            )
            pinned[owner] = frozen
            versions[owner] = value.version_id

        self.definitions = MappingProxyType(pinned)
        self.definition_versions = MappingProxyType(versions)
        self.definition_opens = 0
        self.resolver = _DefinitionResolver(self)


def _fixture(entry=PRED, policy=PURE_POLICY):
    executor = RestrictedExecutor()
    deployment = executor.deploy(evaluator_source(), compiler_generation=1)
    grant = _DefinitionAdmission(executor, deployment, entry, policy)
    return executor, deployment, grant


def _no_vm_on_rejection(operation):
    with patch.object(
        restricted.machine,
        'run',
        side_effect=AssertionError('VM entered before security rejection'),
    ) as run:
        try:
            operation()
        except AdmissionRejected:
            if run.called:
                raise AssertionError('VM entered on refused proof')
            return
    raise AssertionError('expected AdmissionRejected')


def _baseline():
    executor, deployment, grant = _fixture()

    for subject in (3, 12, -3):
        reference = executor.run(
            deployment, PRED, subject, policy=PURE_POLICY,
        )
        baseline_trace = executor.trace()[-1].as_json()

        with patch.object(
            restricted.machine,
            '_definition_of',
            side_effect=AssertionError(
                'machine consulted the mutable decoded definition'
            ),
        ):
            actual = grant.run(subject)

        if actual != reference or executor.trace()[-1].as_json() != baseline_trace:
            raise AssertionError('definition snapshot changed semantics or trace')

    if grant.definition_opens < 3:
        raise AssertionError('VM did not consult authenticated definitions')

    return {
        'same_runtime': grant.runtime is deployment._target.runtime,
        'definition_opens': grant.definition_opens,
        'trace_parity': True,
    }


def _mutated_after_issuance():
    executor, deployment, grant = _fixture()
    value = deployment._target.state.values[PRED]
    original = _definition_of(value)

    candidates = (
        ('invalid_links', replace(original, links={'invalid': (PRED,)})),
        ('wrong_arity', replace(original, params=('x', 'extra'))),
        ('wrong_body', replace(original, body=PURE)),
    )

    observed = {}

    for label, forged in candidates:
        try:
            object.__setattr__(value, '_definition', forged)

            if label == 'invalid_links':
                _no_vm_on_rejection(
                    lambda: executor.run(
                        deployment, PRED, 3, policy=PURE_POLICY,
                    )
                )

            with patch.object(
                restricted.machine,
                '_definition_of',
                side_effect=AssertionError('mutable definition read'),
            ):
                outcome = grant.run(3)

            if outcome != 'satisfied':
                raise AssertionError(f'{label}: different result {outcome!r}')

            observed[label] = outcome
        finally:
            object.__setattr__(value, '_definition', original)

    return {
        'canonical_definition_pinned': True,
        'mutations': observed,
        'note': 'mutated obsolete decoded memos; forged definition not executed',
    }


def _mutated_before_issuance():
    executor = RestrictedExecutor()
    deployment = executor.deploy(evaluator_source(), compiler_generation=1)
    value = deployment._target.state.values[PRED]
    original = _definition_of(value)

    try:
        object.__setattr__(
            value,
            '_definition',
            replace(original, links={'invalid': (PRED,)}),
        )
        _no_vm_on_rejection(
            lambda: _DefinitionAdmission(
                executor, deployment, PRED, PURE_POLICY,
            )
        )
    finally:
        object.__setattr__(value, '_definition', original)

    return {'pre_issuance_forgery_rejected_before_vm': True}


def _transitive():
    executor, deployment, grant = _fixture(PURE_CALL)
    reference = executor.run(
        deployment, PURE_CALL, 3, policy=PURE_POLICY,
    )

    callee_value = deployment._target.state.values[PURE]
    callee_original = _definition_of(callee_value)

    try:
        object.__setattr__(
            callee_value,
            '_definition',
            replace(
                callee_original,
                params=('unexpected', 'parameters'),
            ),
        )

        with patch.object(
            restricted.machine,
            '_definition_of',
            side_effect=AssertionError(
                'transitive call consulted mutable definition'
            ),
        ):
            actual = grant.run(3)

    finally:
        object.__setattr__(
            callee_value,
            '_definition',
            callee_original,
        )

    if actual != reference or grant.definition_opens < 2:
        raise AssertionError('authenticated transitive call failed')

    return {
        'transitive_call': True,
        'definition_opens': grant.definition_opens,
    }


def _revocation_and_effects():
    ex, deployment, proof = _fixture()
    proof.revoke()
    _no_vm_on_rejection(lambda: proof.run(3))

    ex, deployment, proof = _fixture()
    deployment._artifact_set.invalidate()
    _no_vm_on_rejection(lambda: proof.run(3))

    ex, deployment, proof = _fixture()
    deployment._session._chain._sets[1].invalidate()
    _no_vm_on_rejection(lambda: proof.run(3))

    ex = RestrictedExecutor()
    dep = ex.deploy(evaluator_source())

    _no_vm_on_rejection(
        lambda: _DefinitionAdmission(
            ex, dep, DEAD_WRITE, READ_POLICY,
        )
    )

    return {
        'explicit_and_native_revocation': True,
        'forbidden_dead_branch_rejected_before_vm': True,
    }


def _multi_external():
    constraint = AllOf(
        External('audit.a'),
        External('audit.b'),
    )

    def callbacks(events):
        def callback(label):
            def invoke(subject):
                events.append((label, canonicalize(subject)))
                return ConstraintResult.SATISFIED
            return invoke

        return {
            'audit.a': callback('a'),
            'audit.b': callback('b'),
        }

    before = []
    expected = candidate._run_external_continuation(
        constraint, 3, 16, callbacks(before),
    )

    after = []
    original_prepare = candidate._private_dynamic_preparation
    issued = []

    with ExitStack() as stack:

        def installed_prepare(*args, **kwargs):
            executor, deployment, entry = original_prepare(
                *args, **kwargs,
            )
            original_run = executor.run
            grants = {}

            def substitute(selected, function, *arguments, policy=None):
                if selected is not deployment:
                    return original_run(
                        selected,
                        function,
                        *arguments,
                        policy=policy,
                    )

                permitted = (
                    RestrictionPolicy()
                    if policy is None
                    else policy
                )
                key = (function, permitted.allowed_effects)

                if key not in grants:
                    grants[key] = _DefinitionAdmission(
                        executor,
                        deployment,
                        function,
                        permitted,
                    )

                issued.append(function.value)
                return grants[key].run(*arguments)

            stack.enter_context(
                patch.object(
                    executor,
                    'run',
                    side_effect=substitute,
                )
            )
            return executor, deployment, entry

        stack.enter_context(
            patch.object(
                candidate,
                '_private_dynamic_preparation',
                side_effect=installed_prepare,
            )
        )

        actual = candidate._run_external_continuation(
            constraint, 3, 16, callbacks(after),
        )

    if (
        actual != expected
        or after != before
        or len(after) != 2
        or len(issued) < 2
    ):
        raise AssertionError(
            'External continuation/result/callback parity lost'
        )

    return {
        'callback_count': len(after),
        'authenticated_entries': len(issued),
        'callback_order_and_subjects_equal': True,
    }


def _performance(samples):
    cache = {}
    row, pairs, params = previous._gh123_case(
        'int_kind', cache,
    )
    output = []

    for label, (executor, deployment, entry) in zip(
        ('generic', 'specialized'), pairs,
    ):
        started = perf_counter_ns()

        grant = _DefinitionAdmission(
            executor,
            deployment,
            entry,
            RestrictionPolicy(),
        )
        prepare_ns = perf_counter_ns() - started

        def original():
            return executor.run(
                deployment, entry, *params,
            )

        def pinned():
            return grant.run(*params)

        if (
            original() != row['expected']
            or pinned() != row['expected']
        ):
            raise AssertionError('candidate result divergence')

        timings = {
            'original': [],
            'pinned': [],
        }

        for n in range(samples):
            order = (
                (('original', original), ('pinned', pinned))
                if n % 2
                else (('pinned', pinned), ('original', original))
            )

            for key, fn in order:
                begin = perf_counter_ns()
                result = fn()
                timings[key].append(
                    perf_counter_ns() - begin
                )
                if result != row['expected']:
                    raise AssertionError(
                        'timed candidate divergence'
                    )

        original_ns = statistics.median(
            timings['original']
        )
        pinned_ns = statistics.median(
            timings['pinned']
        )

        output.append({
            'variant': label,
            'sample_count': samples,
            'original_median_ns': original_ns,
            'pinned_median_ns': pinned_ns,
            'speedup': original_ns / pinned_ns,
            'prepare_ns': prepare_ns,
            'definition_openings': grant.definition_opens,
            'admitted_artifacts': len(deployment.artifacts),
            'authoritative_snapshot_physically_immutable': False,
        })

    return output


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
    )
    parser.add_argument(
        '--output-dir',
        required=True,
    )
    parser.add_argument(
        '--suite',
        choices=('smoke', 'representative'),
        default='smoke',
    )
    parser.add_argument(
        '--samples',
        type=int,
        default=4,
    )

    args = parser.parse_args(argv)

    if args.samples < 1:
        parser.error('--samples must be positive')

    folder = Path(args.output_dir)
    folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    tests = [
        (
            'baseline_runtime_trace_and_definition_provenance',
            _baseline,
        ),
        (
            'decoded_definition_mutation_after_issuance',
            _mutated_after_issuance,
        ),
        (
            'decoded_definition_mutation_before_issuance',
            _mutated_before_issuance,
        ),
        (
            'authenticated_transitive_definition',
            _transitive,
        ),
        (
            'revocation_and_denied_effects',
            _revocation_and_effects,
        ),
    ]

    if args.suite == 'representative':
        tests.extend([
            (
                'multi_external',
                _multi_external,
            ),
            (
                'gh123_int_kind_performance',
                lambda: _performance(args.samples),
            ),
        ])

    meta = {
        'head': subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        'sha256': sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        'suite': args.suite,
        'samples': args.samples,
        'security_acceptance': False,
        'limitations': [
            'No formal immutable Python object boundary',
            'Source content not physically sealed from privileged host reflection',
            'Original artifact backing substitutions may remain undetected',
            'No full Task 32 or GH-123 frozen suite in this experiment',
        ],
    }

    (folder / 'metadata.json').write_text(
        json.dumps(
            meta,
            indent=2,
            sort_keys=True,
        ) + '\n'
    )

    records = []

    for name, fn in tests:
        try:
            result = fn()
            status = 'passed'
        except BaseException as exc:
            status = 'failed'
            result = {
                'exception': type(exc).__name__,
                'error': str(exc),
                'traceback': traceback.format_exc(),
            }

        record = {
            'name': name,
            'status': status,
            'result': result,
        }

        records.append(record)
        print(
            f'{name}: {status}',
            flush=True,
        )

    complete = all(
        r['status'] == 'passed'
        for r in records
    )

    summary = {
        'head': meta['head'],
        'complete': complete,
        'cases': records,
        'production_acceptance': False,
        'decision': (
            'EXPERIMENTAL_DEFINITION_SEAL'
            if complete
            else 'EXPERIMENT_FAILED'
        ),
    }

    (folder / 'summary.json').write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        ) + '\n'
    )

    print(
        json.dumps(
            {
                'complete': complete,
                'cases': {
                    r['name']: r['status']
                    for r in records
                },
                'decision': summary['decision'],
            },
            indent=2,
        ),
        flush=True,
    )

    return 0 if complete else 1


if __name__ == '__main__':
    raise SystemExit(main())
