"""Candidate acceptance harness for the Task 24 experiment.

The oracle is frozen independently of candidate implementations.
Execute supplies an adapter to a real SHEAR execution path.

A passing vector report is necessary but not sufficient for adoption:
boundary integration, effects, source-path independence and mechanism
elimination require separate evidence and independent Review.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from tests.constraint_function_oracle import (
    Vector,
    all_fixed_vectors,
    generated_vector,
)


# A candidate must use ordinary SHEAR computation, not the dedicated
# constraint evaluator hidden behind a function-looking wrapper.
ROUTES = frozenset(("callable", "interpreted", "compiled"))


@dataclass(frozen=True)
class Observation:
    outcome: str
    route: str
    incumbent_calls: int


@dataclass(frozen=True)
class Failure:
    name: str
    expected: str
    actual: str
    reason: str
    expression: tuple
    seed: int | None = None

    @property
    def replay(self) -> str:
        if self.seed is None:
            return self.name
        return f"SHEAR_SEED={self.seed}"


@dataclass(frozen=True)
class Report:
    candidate: str
    checked: int
    failures: tuple[Failure, ...]

    @property
    def vector_passed(self) -> bool:
        return self.checked > 0 and not self.failures


Candidate = Callable[[Vector], Observation]


def acceptance_vectors(
    generated_seeds: Iterable[int] = range(100),
) -> tuple[tuple[Vector, int | None], ...]:
    """Freeze case order and retain seeds for exact replay."""
    fixed = tuple(
        (vector, None)
        for vector in all_fixed_vectors()
    )
    generated = tuple(
        (generated_vector(seed), seed)
        for seed in generated_seeds
    )
    return fixed + generated


def assess(
    name: str,
    evaluate: Candidate,
    generated_seeds: Iterable[int] = range(100),
) -> Report:
    """Grade every fixed and generated vector without silent skips.

    An adapter must run the candidate implementation, returning its
    observed semantic outcome and measured route evidence.

    Unexpected exceptions and unsupported operations are failures,
    not equivalent to Unknown.
    """
    if not name:
        raise ValueError("candidate name must not be empty")

    failures: list[Failure] = []
    cases = acceptance_vectors(generated_seeds)

    for vector, seed in cases:
        try:
            observed = evaluate(vector)
        except Exception as exc:
            failures.append(Failure(
                vector.name,
                vector.expected,
                type(exc).__name__,
                "candidate raised instead of returning a result",
                vector.expression,
                seed,
            ))
            continue

        if not isinstance(observed, Observation):
            failures.append(Failure(
                vector.name,
                vector.expected,
                repr(observed),
                "candidate did not return an Observation",
                vector.expression,
                seed,
            ))
            continue

        if observed.route not in ROUTES:
            failures.append(Failure(
                vector.name,
                vector.expected,
                observed.outcome,
                f"unapproved execution route: {observed.route!r}",
                vector.expression,
                seed,
            ))

        if (
            type(observed.incumbent_calls) is not int
            or observed.incumbent_calls != 0
        ):
            failures.append(Failure(
                vector.name,
                vector.expected,
                observed.outcome,
                "dedicated evaluator fallback reported",
                vector.expression,
                seed,
            ))

        if observed.outcome != vector.expected:
            failures.append(Failure(
                vector.name,
                vector.expected,
                observed.outcome,
                "semantic result differs from independent oracle",
                vector.expression,
                seed,
            ))

    return Report(
        candidate=name,
        checked=len(cases),
        failures=tuple(failures),
    )


def summarize(report: Report) -> str:
    """Deterministic output suitable for an Execute evidence record."""
    status = "PASS" if report.vector_passed else "FAIL"

    lines = [
        f"{report.candidate}: {status}",
        f"vectors checked: {report.checked}",
        f"failures: {len(report.failures)}",
    ]

    for failure in report.failures:
        lines.extend((
            f"- {failure.name}: {failure.reason}",
            f"  expected={failure.expected!r}",
            f"  actual={failure.actual!r}",
            f"  replay={failure.replay}",
            f"  expression={failure.expression!r}",
        ))

    return "\n".join(lines)


# Execute obligations beyond this unit-vector harness:
#
# 1. Supply a separate adapter for each attempted design A, B or C.
# 2. Run existing corpora through every newly introduced execution layer.
# 3. Exercise all boundary witnesses in constraint_function_oracle.py.
# 4. Test initial load, writes, activation, trial and owned-subtree roles.
# 5. Preserve host-failure provenance, catch distinctions and atomicity.
# 6. Test effects, versions, budgets and non-termination separately.
# 7. Prove incumbent_calls with instrumentation, not self-report alone.
# 8. Audit the complete call path for hidden Python evaluator fallback.
# 9. Record mechanism removals and additions against the frozen ledger.
# 10. Declare adopt or kill without weakening Plan-owned expectations.
#
# A PASS here does not establish any of obligations 2–10.
