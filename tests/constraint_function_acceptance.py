"""Candidate acceptance harness for the Task 24 experiment.

The oracle is frozen independently of candidate implementations.
Execute supplies an adapter to a real SHEAR execution path.

Candidate adapters receive inputs only. Expected outcomes remain
inside the grader, never in the adapter argument.

A passing vector report is necessary but not sufficient for adoption:
boundary integration, effects, source-path independence and mechanism
elimination require separate evidence and independent Review.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from tests.constraint_function_oracle import (
    Vector,
    all_fixed_vectors,
    generated_budget_vector,
    generated_vector,
)


ROUTES = frozenset(("callable", "interpreted", "compiled"))


@dataclass(frozen=True)
class CandidateInput:
    """Only information the candidate is authorized to receive.

    Neither the expected result, fixture name nor replay seed is
    available to a candidate through this interface.
    """

    expression: tuple[Any, ...]
    subject: Any
    budget: int | None
    externals: tuple[tuple[str, str], ...]


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


Candidate = Callable[[CandidateInput], Observation]


def candidate_input(vector: Vector) -> CandidateInput:
    """Construct detached input without any oracle expectation."""
    return CandidateInput(
        expression=deepcopy(vector.expression),
        subject=deepcopy(vector.subject),
        budget=vector.budget,
        externals=deepcopy(vector.externals),
    )


def acceptance_vectors(
    generated_seeds: Iterable[int] = range(100),
) -> tuple[tuple[Vector, int | None], ...]:
    """Return fixed and both generated families for private grading.

    Fixed cases cover all kinds, primitives, logical operators,
    deduplication, short circuits and explicit budgets.

    For each seed, require an unbudgeted logical tree and a
    budget-sensitive primitive/composite case. The seed is retained
    for replay but is never passed to the candidate adapter.
    """
    fixed = tuple(
        (vector, None)
        for vector in all_fixed_vectors()
    )

    seeds = tuple(generated_seeds)

    generated = tuple(
        (generated_vector(seed), seed)
        for seed in seeds
    )

    budgeted = tuple(
        (generated_budget_vector(seed), seed)
        for seed in seeds
    )

    return fixed + generated + budgeted


def assess(
    name: str,
    evaluate: Candidate,
    generated_seeds: Iterable[int] = range(100),
) -> Report:
    """Grade all cases while keeping expectations out of adapters.

    The adapter must execute the candidate implementation and return
    an Observation. Unsupported operations and unexpected exceptions
    are failures, never equivalent to Unknown.

    Route and fallback fields are claims requiring independent
    instrumentation and execution-path audit.
    """
    if not name:
        raise ValueError("candidate name must not be empty")

    failures: list[Failure] = []
    cases = acceptance_vectors(generated_seeds)

    for vector, seed in cases:
        inputs = candidate_input(vector)

        try:
            observed = evaluate(inputs)
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


# Additional Execute obligations:
#
# 1. Supply separate candidate adapters for the attempted designs.
# 2. Exercise the frozen candidate-facing boundary contract.
# 3. Run existing corpora through every new execution layer.
# 4. Preserve admission, atomicity, host failures and effects.
# 5. Test versions, budgets and non-termination separately.
# 6. Instrument incumbent calls independently of adapter reports.
# 7. Audit complete execution paths for hidden Python fallbacks.
# 8. Count retained, removed and added fixed mechanisms.
# 9. Record the observed predictions and adopt-or-kill verdict.
#
# A semantic vector PASS does not establish these obligations.
