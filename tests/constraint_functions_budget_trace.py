"""Admitted SHEAR budget-trace helpers for GH-123 candidate evaluation.

The trace is computed from VM-returned remaining budget, never from Python
shadow evaluation or an incumbent's accounting. A SHEAR-only tree count
supplies a finite upper bound for otherwise unbounded evaluations.
"""

from __future__ import annotations

from collections.abc import Mapping

from shear import EntityID, Relation
from shear.lang import Function, links


TRACE_ENTRY = EntityID("constraint.trace.entry")
TRACE_COUNT = EntityID("constraint.trace.count")
TRACE_PARTS = EntityID("constraint.trace.parts")


def _arg(name: str) -> tuple:
    return ("arg", name)


def _lit(value: object) -> tuple:
    return ("lit", value)


def _item(value: tuple, key: int | str) -> tuple:
    return ("item", value, _lit(key))


def _call(name: str, *arguments: tuple) -> tuple:
    return ("call", name, *arguments)


def _count_body() -> tuple:
    """Count canonical semantic constraint nodes, not VM instructions."""
    constraint = _arg("constraint")
    form = _arg("form")
    arguments = _arg("arguments")
    children = _item(arguments, 0)
    unary = (
        "add", _lit(1), _call("count", children),
    )
    role = (
        "add", _lit(1), _call("count", _item(arguments, 1)),
    )
    composite = _call("parts", children, _lit(0), _lit(1))
    return (
        "let", "form", _item(constraint, "form"),
        (
            "let", "arguments", _item(constraint, "arguments"),
            (
                "if", ("eq", form, _lit("all_of")), composite,
                (
                    "if", ("eq", form, _lit("any_of")), composite,
                    (
                        "if", ("eq", form, _lit("not")), unary,
                        (
                            "if", ("eq", form, _lit("role")), role,
                            _lit(1),
                        ),
                    ),
                ),
            ),
        ),
    )


def _parts_body() -> tuple:
    parts = _arg("parts")
    index = _arg("index")
    count = _arg("count")
    return (
        "if", ("lt", index, ("len", parts)),
        _call(
            "next", parts, ("add", index, _lit(1)),
            ("add", count, _call("count", ("item", parts, index))),
        ),
        count,
    )


def _entry_body() -> tuple:
    requested = _arg("budget")
    constraint = _arg("constraint")
    total = _arg("total")
    result = _arg("result")
    return (
        "let", "total",
        (
            "if", ("eq", requested, _lit(None)),
            _call("count", constraint), requested,
        ),
        (
            "let", "result",
            _call(
                "evaluate", _arg("subject"), constraint,
                total, _arg("registrations"),
            ),
            (
                "tuple", _item(result, 0),
                ("sub", total, _item(result, 1)),
            ),
        ),
    )


def add_budget_trace_entities(
    existing: Mapping[EntityID, Function | Relation],
    evaluator: EntityID,
) -> dict[EntityID, Function | Relation]:
    """Extend authenticated evaluator source with VM-only visit counting.

    The evaluator must return (verdict, remaining_budget) and must apply
    the standard one-unit-per-visited-constraint budget discipline.
    This function creates source definitions, not semantic observations.
    """
    if not isinstance(evaluator, EntityID):
        raise TypeError("evaluator must be an EntityID")
    if evaluator not in existing:
        raise ValueError("evaluator function absent from source")
    extensions = {
        TRACE_ENTRY: Function(
            ("subject", "constraint", "budget", "registrations"),
            _entry_body(),
        ),
        TRACE_COUNT: Function(("constraint",), _count_body()),
        TRACE_PARTS: Function(("parts", "index", "count"), _parts_body()),
        EntityID(f"{TRACE_ENTRY.value}.links"): links(
            TRACE_ENTRY, evaluate=evaluator, count=TRACE_COUNT,
        ),
        EntityID(f"{TRACE_COUNT.value}.links"): links(
            TRACE_COUNT, count=TRACE_COUNT, parts=TRACE_PARTS,
        ),
        EntityID(f"{TRACE_PARTS.value}.links"): links(
            TRACE_PARTS, next=TRACE_PARTS, count=TRACE_COUNT,
        ),
    }
    if any(entity in existing for entity in extensions):
        raise ValueError("trace definitions collide with evaluator source")
    return {**existing, **extensions}
