"""Authenticated SHEAR constraint authority for GH-123 runtime admission.

Used by actual Runtime operations, not by a host-side verdict interpreter.
The existing ordinary EvaluationContext remains untouched.
"""

from __future__ import annotations

from contextlib import nullcontext

from shear import ConstraintResult, EvaluationContext, Runtime, canonicalize
from shear.constraints import Constraint


class CandidateAdmissionContext(EvaluationContext):
    """Bind Runtime admission to the candidate's authenticated SHEAR VM.

    Externals, budget and any underlying operation-scope pinning remain
    attached to the supplied context. A VM failure cannot fall back to
    Constraint.evaluate().
    """

    def __init__(self, original: EvaluationContext | None = None) -> None:
        if original is None:
            original = EvaluationContext()
        if not isinstance(original, EvaluationContext):
            raise TypeError("expected EvaluationContext")
        super().__init__(original.externals, budget=original.budget)
        object.__setattr__(self, "_original", original)

    def operation_scope(self, target_state_id, operation):
        original_scope = getattr(self._original, "operation_scope", None)
        if original_scope is None:
            return nullcontext()
        return original_scope(target_state_id, operation)

    def evaluate_constraint(
        self, constraint: Constraint, subject: object,
    ) -> ConstraintResult:
        """Use a live admitted invocation for every runtime verdict."""
        # Late import avoids a cycle when the candidate adapter exposes
        # this context and preserves fresh-import poisoning coverage.
        from tests import constraint_functions_complete_candidate as candidate

        subject = canonicalize(subject)
        if self.externals:
            callbacks = {
                name: evaluator.evaluate
                for name, evaluator in self.externals.items()
            }
            verdict = candidate._run_external_continuation(
                constraint, subject, self.budget, callbacks,
            ).outcome
        else:
            executor, deployment, entry = (
                candidate._generic_ordinary_deployment(
                    candidate._PRIVATE_COMPILER_GENERATION,
                    candidate._PRIVATE_SEMANTIC_AUTHORITY,
                )
            )
            verdict = executor.run(
                deployment, entry, subject, constraint, self.budget, (),
            )

        if type(verdict) is not str or verdict not in candidate._VERDICTS:
            raise TypeError("authenticated evaluator returned invalid verdict")
        return ConstraintResult(verdict)


def open_candidate_runtime(state, context: EvaluationContext | None = None):
    """Load a real Runtime with authenticated admission in every operation."""
    return Runtime(state, CandidateAdmissionContext(context))
