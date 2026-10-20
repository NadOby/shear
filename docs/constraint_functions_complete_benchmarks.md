# GH-123 Performance and Mechanism Benchmark

Status: Plan-owned experimental protocol.
Applies to the complete ordinary-SHEAR constraint experiment.
Compare candidate and unchanged incumbent on identical inputs.

## 1. Workloads

Use fixed, replayable instances drawn from:
- All nine constraint-operation families.
- Satisfied, Violated and Unknown outcomes.
- Empty, duplicate, nested and reordered compositions.
- Budgets 0, 1, 2, sufficient and unbounded.
- External dispatch, including missing evaluators.
- Canonical projection and structural inspection.
- Cell and relation admission, write, activation and trial.
- Constraint graphs of 8, 64 and 256 nodes.

Measure both typical cases and costly valid cases.
Do not select cases based on favorable candidate performance.
Record exact seeds, parameters and canonical input digests.

Failures, unauthorized effects and nontermination are semantic
acceptance results, not successful timing measurements.
Maintain separate records for failed or unsupported workloads.

## 2. Comparable execution paths

The baseline uses existing public runtime entry points.

The candidate uses the actual Task 32 admitted execution path,
including runtime integration when the workload requires it.

Exclude test-harness assertions and recording overhead from
timed regions on both sides, without bypassing execution policy,
budgeting, canonical projection or required runtime checks.

Benchmark both paths in the same Python version and environment.
Record CPU, operating system, Python version, repository SHAs,
process settings and relevant resource limits.

Do not compare a warm candidate against a cold incumbent.

## 3. Preparation and cold execution

Measure separately:
- Source construction.
- Compilation and artifact admission.
- First complete operation after preparation.
- Subsequent warm operation.
- Version transition and required re-admission.

Collect at least 10 independent cold-preparation observations
per selected workload, using fresh execution contexts.

Include failure and cleanup costs where they arise naturally.
Retain raw durations, not only aggregate statistics.

## 4. Warm execution

For each workload:
1. Use at least three fresh processes.
2. Prepare both implementations independently.
3. Warm each path for at least 30 completed operations.
4. Calibrate batch sizes independently to target at least
   20 milliseconds of measured work per timing block.
5. Record at least 40 paired blocks per process, yielding
   at least 120 paired observations.
6. Alternate or deterministically randomize which path runs
   first in each pair; publish the order and seed.
7. Divide elapsed block time by its invocation count.
8. Preserve every observation and its matching workload.

Do not change source, compiler options, workload or policy
between baseline and candidate observations.

If a batch cannot achieve useful timing resolution, report
the limitation. Never replace a near-zero denominator with
an arbitrary constant to produce a favorable ratio.

## 5. Latency statistics

Calculate separately for baseline and candidate:
- Median per-invocation latency.
- Empirical p95 per-invocation latency.
- Minimum, maximum and dispersion.
- Number of observations and timed invocations.

Compute ratios as:
- Candidate median divided by incumbent median.
- Candidate p95 divided by incumbent p95.

Use the pooled observations from all measured processes.
Calculate a stratified bootstrap 95% confidence interval for
each ratio, resampling blocks within processes with a fixed
published seed and at least 2,000 replicates.

Report process-to-process variation independently.
Retain raw timings and the calculation code for reproduction.

## 6. Additional costs

Report:
- Total compiler and preparation time.
- Generated and retained artifact size.
- Admitted artifact count.
- Executed bytecode instruction counts where observable.
- Peak allocated Python memory and peak process memory,
  stating the measurement method for each.
- Cold-to-warm ratio.
- Scaling across 8, 64 and 256 constraint nodes.
- Failures, timeouts and incomplete measurements.

Do not present unsupported memory or instruction estimates
as observations. If an exact metric is unavailable, record it
as unmeasured and identify a way to measure it.

## 7. Initial acceptance threshold

The owner-approved initial ceiling is 1000x incumbent warm
median latency and 1000x incumbent warm p95 latency.

A workload exceeding either ceiling triggers investigation.
It does not automatically terminate the experiment.

A positive performance assessment requires observed ratios
within the initial ceilings or explicit owner acceptance of
a documented exception.

A negative performance conclusion requires reproducible
evidence, uncertainty analysis and owner confirmation that
the observed cost is unacceptable.

Measurement noise, resource exhaustion or absent samples
cannot be presented as evidence of architectural impossibility.

## 8. Mechanism accounting

Record each distinct mechanism with:
- Name, scope and implementation location.
- Generic or constraint-specific applicability.
- Whether it is reused, extended, added or retained.
- New fixed machinery versus ordinary SHEAR program content.
- Required language/VM/host integration changes.
- Direct verification and maintenance obligations.
- Whether removal of incumbent machinery is demonstrated.

Use Task 24 M1–M4 and N1–N5 categories consistently.
Do not count hypothetical future deletion as actual removal.

There is no fixed cap on new generic mechanisms.
Constraint-specific hidden dispatch or fallback counts as
fixed machinery even when wrapped in a generic interface.

## 9. Evidence and classification

Store:
- Exact source and test SHAs.
- Workload definitions and replay seeds.
- Raw benchmark observations.
- Benchmark calculation script.
- Environment and preparation details.
- Aggregated statistics and uncertainty intervals.
- Full mechanism ledger.
- Reproduction instructions.

Classify performance as:
- Within initial ceiling.
- Above initial ceiling, investigation required.
- Owner-approved exception.
- Inconclusive due to measurement limitations.

The full architectural conclusion also requires every frozen
semantic and security obligation to pass independently.
Benchmark results never override semantic counterexamples.
