"""Ordinary SHEAR functions for complete constraint evaluation.

The host constructs function definitions, not semantic verdicts.
Evaluation, composition and budget consumption execute as SHEAR code.

The recursive evaluator and authenticated adapter are added separately.
"""

from __future__ import annotations

from ..identity import EntityID
from ..lang import Function


SATISFIED = "satisfied"
VIOLATED = "violated"
UNKNOWN = "unknown"

LOGIC_ALL = EntityID("constraint.logic.all")
LOGIC_ANY = EntityID("constraint.logic.any")
LOGIC_NOT = EntityID("constraint.logic.not")
BUDGET_STEP = EntityID("constraint.budget.step")


def _arg(name: str) -> tuple:
    return ("arg", name)


def _lit(value: object) -> tuple:
    return ("lit", value)


def _eq(left: tuple, right: object) -> tuple:
    return ("eq", left, _lit(right))


def _logic_all() -> tuple:
    left = _arg("left")
    right = _arg("right")

    return (
        "if",
        _eq(left, VIOLATED),
        _lit(VIOLATED),
        (
            "if",
            _eq(right, VIOLATED),
            _lit(VIOLATED),
            (
                "if",
                _eq(left, UNKNOWN),
                _lit(UNKNOWN),
                (
                    "if",
                    _eq(right, UNKNOWN),
                    _lit(UNKNOWN),
                    _lit(SATISFIED),
                ),
            ),
        ),
    )


def _logic_any() -> tuple:
    left = _arg("left")
    right = _arg("right")

    return (
        "if",
        _eq(left, SATISFIED),
        _lit(SATISFIED),
        (
            "if",
            _eq(right, SATISFIED),
            _lit(SATISFIED),
            (
                "if",
                _eq(left, UNKNOWN),
                _lit(UNKNOWN),
                (
                    "if",
                    _eq(right, UNKNOWN),
                    _lit(UNKNOWN),
                    _lit(VIOLATED),
                ),
            ),
        ),
    )


def _logic_not() -> tuple:
    value = _arg("value")

    return (
        "if",
        _eq(value, SATISFIED),
        _lit(VIOLATED),
        (
            "if",
            _eq(value, VIOLATED),
            _lit(SATISFIED),
            _lit(UNKNOWN),
        ),
    )


def _budget_step() -> tuple:
    """Return (may_visit, remaining) for one constraint node.

    None is the unbounded budget. Exhaustion retains zero, so
    every subsequently visited node also receives Unknown.
    """

    remaining = _arg("remaining")

    return (
        "if",
        _eq(remaining, None),
        ("tuple", _lit(True), remaining),
        (
            "if",
            _eq(remaining, 0),
            ("tuple", _lit(False), remaining),
            (
                "tuple",
                _lit(True),
                ("sub", remaining, _lit(1)),
            ),
        ),
    )


def evaluator_entities() -> dict[EntityID, Function]:
    """Construct pure, reusable SHEAR function definitions."""

    return {
        LOGIC_ALL: Function(("left", "right"), _logic_all()),
        LOGIC_ANY: Function(("left", "right"), _logic_any()),
        LOGIC_NOT: Function(("value",), _logic_not()),
        BUDGET_STEP: Function(("remaining",), _budget_step()),
    }
