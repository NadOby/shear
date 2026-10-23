"""Ordinary SHEAR functions for complete constraint evaluation.

The host constructs function definitions, not semantic verdicts.
Evaluation, composition and budget consumption execute as SHEAR code.

The recursive constraint dispatcher and authenticated adapter follow separately.
"""

from __future__ import annotations

from ..identity import EntityID
from ..lang import Function, links
from ..relations import Relation


SATISFIED = "satisfied"
VIOLATED = "violated"
UNKNOWN = "unknown"

LOGIC_ALL = EntityID("constraint.logic.all")
LOGIC_ANY = EntityID("constraint.logic.any")
LOGIC_NOT = EntityID("constraint.logic.not")
BUDGET_STEP = EntityID("constraint.budget.step")
IS_KIND = EntityID("constraint.primitive.is_kind")
INT_RANGE = EntityID("constraint.primitive.int_range")
LENGTH = EntityID("constraint.primitive.length")
ONE_OF = EntityID("constraint.primitive.one_of")
VALUE_EQUAL = EntityID("constraint.primitive.value_equal")
EQUAL_ITEMS = EntityID("constraint.primitive.equal_items")
ONE_OF_SCAN = EntityID("constraint.primitive.one_of_scan")


def _arg(name: str) -> tuple:
    return ("arg", name)


def _lit(value: object) -> tuple:
    return ("lit", value)


def _eq(left: tuple, right: object) -> tuple:
    return ("eq", left, _lit(right))


def _kind(value: tuple) -> tuple:
    return ("item", ("inspect", value), _lit(0))


def _select_kind(kind: tuple, allowed: tuple[str, ...]) -> tuple:
    result = _lit(False)
    for name in reversed(allowed):
        result = ("if", _eq(kind, name), _lit(True), result)
    return result


def _bounded(value: tuple, minimum: tuple, maximum: tuple) -> tuple:
    upper = (
        "if",
        _eq(maximum, None),
        _lit(SATISFIED),
        ("if", ("lt", maximum, value), _lit(VIOLATED), _lit(SATISFIED)),
    )
    return (
        "if",
        _eq(minimum, None),
        upper,
        ("if", ("lt", value, minimum), _lit(VIOLATED), upper),
    )


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


def _is_kind() -> tuple:
    return (
        "if",
        ("eq", _kind(_arg("subject")), _arg("kind")),
        _lit(SATISFIED),
        _lit(VIOLATED),
    )


def _int_range() -> tuple:
    subject = _arg("subject")
    return (
        "if",
        _eq(_kind(subject), "int"),
        _bounded(subject, _arg("minimum"), _arg("maximum")),
        _lit(VIOLATED),
    )


def _length() -> tuple:
    subject = _arg("subject")
    return (
        "let",
        "kind",
        _kind(subject),
        (
            "if",
            _select_kind(
                _arg("kind"), ("str", "bytes", "tuple", "list", "map")
            ),
            _bounded(("len", subject), _arg("minimum"), _arg("maximum")),
            _lit(VIOLATED),
        ),
    )


def _value_equal() -> tuple:
    """Type-preserving recursive equality, using generic inspection."""
    left = _arg("left")
    right = _arg("right")
    return (
        "let",
        "kind",
        _kind(left),
        (
            "if",
            ("eq", _arg("kind"), _kind(right)),
            (
                "if",
                _select_kind(
                    _arg("kind"),
                    ("tuple", "list", "map", "cell", "constraint", "relation"),
                ),
                (
                    "if",
                    ("eq", ("len", left), ("len", right)),
                    ("call", "items", left, right, _lit(0)),
                    _lit(False),
                ),
                ("eq", left, right),
            ),
            _lit(False),
        ),
    )


def _equal_items() -> tuple:
    """Compare the indexed children of equally sized semantic containers."""
    left = _arg("left")
    right = _arg("right")
    index = _arg("index")
    return (
        "if",
        ("lt", index, ("len", left)),
        (
            "if",
            (
                "call", "equal", ("item", left, index),
                ("item", right, index),
            ),
            ("call", "next", left, right, ("add", index, _lit(1))),
            _lit(False),
        ),
        _lit(True),
    )


def _one_of() -> tuple:
    return (
        "call", "scan", _arg("subject"), _arg("values"), _lit(0),
    )


def _one_of_scan() -> tuple:
    subject = _arg("subject")
    values = _arg("values")
    index = _arg("index")
    return (
        "if",
        ("lt", index, ("len", values)),
        (
            "if",
            ("call", "equal", subject, ("item", values, index)),
            _lit(SATISFIED),
            ("call", "next", subject, values, ("add", index, _lit(1))),
        ),
        _lit(VIOLATED),
    )


def evaluator_entities() -> dict[EntityID, Function | Relation]:
    """Pure SHEAR definitions and explicit static recursive call links."""
    return {
        LOGIC_ALL: Function(("left", "right"), _logic_all()),
        LOGIC_ANY: Function(("left", "right"), _logic_any()),
        LOGIC_NOT: Function(("value",), _logic_not()),
        BUDGET_STEP: Function(("remaining",), _budget_step()),
        IS_KIND: Function(("subject", "kind"), _is_kind()),
        INT_RANGE: Function(
            ("subject", "minimum", "maximum"), _int_range(),
        ),
        LENGTH: Function(("subject", "minimum", "maximum"), _length()),
        ONE_OF: Function(("subject", "values"), _one_of()),
        VALUE_EQUAL: Function(("left", "right"), _value_equal()),
        EQUAL_ITEMS: Function(("left", "right", "index"), _equal_items()),
        ONE_OF_SCAN: Function(
            ("subject", "values", "index"), _one_of_scan(),
        ),
        EntityID(f"{ONE_OF.value}.links"): links(ONE_OF, scan=ONE_OF_SCAN),
        EntityID(f"{ONE_OF_SCAN.value}.links"): links(
            ONE_OF_SCAN, equal=VALUE_EQUAL, next=ONE_OF_SCAN,
        ),
        EntityID(f"{VALUE_EQUAL.value}.links"): links(
            VALUE_EQUAL, items=EQUAL_ITEMS,
        ),
        EntityID(f"{EQUAL_ITEMS.value}.links"): links(
            EQUAL_ITEMS, equal=VALUE_EQUAL, next=EQUAL_ITEMS,
        ),
    }
