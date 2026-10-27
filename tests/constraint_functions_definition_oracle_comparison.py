"""GH-123 experimental sealed-definition candidate versus frozen semantic oracle.

This is an exploratory adapter experiment, NOT frozen GH-123 acceptance.
The unchanged frozen execution guard additionally requires the original
admitted-chunk object identity, whereas the experimental proof copies chunks.
Do not claim resource acceptance from this single-process, small-sample run.

Example:
  python -m tests.constraint_functions_definition_oracle_comparison \
      --output-dir experiment-output --suite smoke --samples 4
  python -m tests.constraint_functions_definition_oracle_comparison \
      --output-dir experiment-output --suite representative --samples 8
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import statistics
import subprocess
from time import perf_counter_ns
import traceback
from unittest.mock import patch

from shear import bytecode
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from shear.hosted_bootstrap.restricted_policy import RestrictionPolicy
from tests import constraint_functions_complete_candidate as candidate
from tests import constraint_functions_comparative_benchmark as compare
from tests import constraint_functions_definition_snapshot_experiment as snapshot
from tests.constraint_function_acceptance import assess


class _AdmissionHarness:
    """Instrument the candidate's existing RestrictedExecutor invocation seam."""

    def __init__(self):
        self.proofs = {}
        self.preparation = {}
        self.calls = 0
        self.openings = 0
        self.check_lowering = True

    def run(self, executor, deployment, entry, *args, policy=None):
        selected = RestrictionPolicy() if policy is None else policy
        key = (executor, deployment, entry, selected.allowed_effects)
        if key not in self.proofs:
            start = perf_counter_ns()
            self.proofs[key] = snapshot._DefinitionAdmission(
                executor, deployment, entry, selected,
            )
            self.preparation[key] = perf_counter_ns() - start
        grant = self.proofs[key]
        before = grant.resolver.opened
        if self.check_lowering:
            def refuse(*_args, **_kwargs):
                raise AssertionError('host lowering inside sealed VM execution')
            with (patch.object(bytecode, 'lower_value', side_effect=refuse),
                  patch.object(bytecode, 'chunk_of', side_effect=refuse)):
                result = grant.run(*args)
        else:
            result = grant.run(*args)
        if grant.resolver.opened <= before:
            raise AssertionError('no authenticated VM node opening observed')
        self.calls += 1
        self.openings += grant.resolver.opened - before
        return result


@contextmanager
def sealed_candidate(harness):
    def intercept(executor, deployment, entry, *args, policy=None):
        return harness.run(executor, deployment, entry, *args, policy=policy)
    with patch.object(RestrictedExecutor, 'run', intercept):
        yield


def _timed(function, expected, count):
    started = perf_counter_ns()
    for _ in range(count):
        if function() != expected:
            raise AssertionError('semantic mismatch during timed invocation')
    return (perf_counter_ns() - started) / count


def _measure_one(row, samples):
    incumbent, challenger = compare._prepare(row)
    expected = row['expected']
    if incumbent() != expected or challenger() != expected:
        raise AssertionError('untimed comparison mismatch')
    inc_n, _ = compare._calibrate(incumbent, expected, 3_000_000, 1 << 20)
    sealed_n, _ = compare._calibrate(challenger, expected, 3_000_000, 1 << 20)
    data = {'incumbent': [], 'sealed': []}
    for index in range(samples):
        order = ('incumbent', 'sealed') if index % 2 else ('sealed', 'incumbent')
        for label in order:
            function = incumbent if label == 'incumbent' else challenger
            count = inc_n if label == 'incumbent' else sealed_n
            data[label].append(_timed(function, expected, count))
    base = statistics.median(data['incumbent'])
    optimized = statistics.median(data['sealed'])
    return {
        'workload': row['name'],
        'origin': row['origin'],
        'expected': expected,
        'samples_per_path': samples,
        'incumbent_median_ns': base,
        'sealed_median_ns': optimized,
        'ratio_sealed_over_incumbent': optimized / base if base else None,
        'incumbent_batch': inc_n,
        'sealed_batch': sealed_n,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--suite', choices=('smoke', 'representative', 'full'),
                        default='smoke')
    parser.add_argument('--samples', type=int, default=4)
    args = parser.parse_args(argv)
    if args.samples < 2:
        parser.error('--samples must be >= 2')
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], check=True,
                          capture_output=True, text=True).stdout.strip()
    harness = _AdmissionHarness()
    rows = compare._cases('full' if args.suite == 'full' else 'representative')
    if args.suite == 'smoke':
        names = {'int_kind', 'range_outside', 'role_present',
                 'external_absent', 'pair_three'}
        rows = [row for row in rows if row['name'] in names]
    seeds = {'smoke': 4, 'representative': 16, 'full': 128}[args.suite]
    results = []
    failure = None
    grade = None
    try:
        with sealed_candidate(harness):
            report = assess('experimental-definition-sealed', candidate.semantic,
                            generated_seeds=range(seeds))
            grade = {
                'checked': report.checked,
                'passed': report.vector_passed,
                'failures': [dict(name=f.name, reason=f.reason,
                                  expected=f.expected, actual=f.actual,
                                  seed=f.seed) for f in report.failures],
            }
            if not report.vector_passed:
                raise AssertionError('sealed candidate differs from frozen oracle')
            # Timing excludes monkeypatch safety instrumentation, but not the
            # real preparation, canonicalization, VM, or continuation work.
            harness.check_lowering = False
            for row in rows:
                item = _measure_one(row, args.samples)
                results.append(item)
                print(f"{item['workload']}: {item['ratio_sealed_over_incumbent']:.1f}x", flush=True)
    except BaseException as exc:
        failure = {'type': type(exc).__name__, 'detail': str(exc),
                   'traceback': traceback.format_exc()}

    summary = {
        'head': head, 'source_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'suite': args.suite, 'semantic_grade': grade,
        'comparison': results, 'failure': failure,
        'candidate_invocations': harness.calls,
        'authenticated_vm_openings': harness.openings,
        'proofs_issued': len(harness.proofs),
        'total_proof_prepare_ns': sum(harness.preparation.values()),
        'production_acceptance': False,
        'resource_qualification': 'NOT_ESTABLISHED',
        'warnings': [
            'proof snapshot is not physically immutable under privileged Python reflection',
            'old backing mutation rejection parity remains unqualified',
            'frozen acceptance identity witness is not substituted or weakened',
            'single-process timings without bootstrap are exploratory only',
        ],
        'decision': ('EXPERIMENT_FAILED' if failure else
                     'SEMANTIC_ORACLE_AND_EXPLORATORY_TIMING_ONLY'),
    }
    (folder / 'summary.json').write_text(json.dumps(summary, indent=2,
                                                   sort_keys=True) + '\n')
    print(json.dumps({k: summary[k] for k in
                      ('decision', 'semantic_grade', 'proofs_issued',
                       'authenticated_vm_openings', 'failure')},
                     indent=2, sort_keys=True), flush=True)
    return 1 if failure else 0


if __name__ == '__main__':
    raise SystemExit(main())
