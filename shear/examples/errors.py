"""Error-handling canary programs (docs/error_handling.md section 11).

``catch`` turns a failure into ``("ok", value)`` or ``("failed", error)``,
and ``raise`` fails with a program's own error. An error is
``(origin, kind, detail, where)``; these programs read only its origin, kind
and detail, since ``where`` names graph-form nodes.
"""

from __future__ import annotations

from .. import CellDeclaration, EntityID, IntRange
from ..lang import Function, LanguageError, links
from . import Example, Raises, Step
from ._support import program


def _ok(result: tuple) -> tuple:
    """``item(r, 0) == "ok"`` for a catch result ``r``."""

    return ("eq", ("item", result, ("lit", 0)), ("lit", "ok"))


def _fn(param: str, body: tuple) -> tuple:
    """``fn(param): body``, the input form the syntax gives a fn literal."""

    return ("function", ("lit", (param,)), ("quote", body))


def _safe_install() -> Example:
    # Unprefixed names, as in checked_compile: a name inside quoted code is
    # data, so its link name must be the entity's name to survive text.
    power = EntityID("power")
    verdict = EntityID("verdict")
    install_if = EntityID("install_if")
    candidates = {
        # Each candidate replaces power(y); only square gives 9 for 3.
        "crash": ("item", ("tuple",), ("arg", "y")),
        "runaway": ("add", ("lit", 1), ("call", "power", ("arg", "y"))),
        "double": ("add", ("arg", "y"), ("arg", "y")),
        "square": ("mul", ("arg", "y"), ("arg", "y")),
    }
    installers = {
        name: EntityID(f"install_{name}") for name in candidates
    }
    result = ("arg", "r")
    entities = {
        power: Function(("x",), ("lit", 1)),
        # The runaway candidate calls power, so power links itself.
        EntityID("power.links"): links(power, power=power),
        verdict: Function(
            ("r", "expected"),
            (
                "if",
                _ok(result),
                (
                    "if",
                    ("eq", ("item", result, ("lit", 1)), ("arg", "expected")),
                    ("lit", "passed"),
                    ("lit", "wrong"),
                ),
                # The kind of the failure: the error is item(r, 1).
                ("item", ("item", result, ("lit", 1)), ("lit", 1)),
            ),
        ),
        install_if: Function(
            ("v", "f"),
            (
                "if",
                ("eq", ("arg", "v"), ("lit", "passed")),
                ("seq", ("activate", "power", ("arg", "f")), ("lit", "installed")),
                ("arg", "v"),
            ),
        ),
        EntityID("install_if.links"): links(install_if, power=power),
    }

    for name, body in candidates.items():
        installer = installers[name]
        entities[installer] = Function(
            ("x", "expected"),
            (
                "call",
                "install_if",
                (
                    "call",
                    "verdict",
                    (
                        "catch",
                        (
                            "trial",
                            ("call", "power", ("arg", "x")),
                            "power",
                            _fn("y", body),
                        ),
                    ),
                    ("arg", "expected"),
                ),
                _fn("y", body),
            ),
        )
        entities[EntityID(f"{installer.value}.links")] = links(
            installer,
            power=power,
            verdict=verdict,
            install_if=install_if,
        )

    return Example(
        name="safe_install",
        tags=frozenset({"self-modification", "errors"}),
        program=program(entities),
        scenarios=(
            (
                Step(installers["crash"], (2, 4), "out_of_range", may_activate=True),
                Step(power, (2,), 1),
                Step(installers["runaway"], (2, 4), "depth_limit", may_activate=True),
                Step(power, (2,), 1),
                Step(installers["double"], (3, 9), "wrong", may_activate=True),
                Step(power, (3,), 1),
                Step(installers["square"], (3, 9), "installed", may_activate=True),
                Step(power, (3,), 9),
            ),
        ),
        description=(
            "Each install_* trials a candidate for power under catch and "
            "installs it only if it returns the expected value. A candidate "
            "that indexes an empty tuple and one that recurses without end "
            "are reported by the kind of their failure and never installed; "
            "a wrong answer is reported as wrong."
        ),
    )


def _account_report() -> Example:
    balance = EntityID("account_report.balance")
    attempts = EntityID("account_report.attempts")
    withdraw = EntityID("account_report.withdraw")
    withdraw_or_refuse = EntityID("account_report.withdraw_or_refuse")
    result = ("arg", "r")
    # item(item(detail, 1), 1) of the error item(r, 1): its constraint result,
    # since the detail is (("cell", c), ("constraint", k), ("operation", o)).
    constraint = (
        "item",
        ("item", ("item", ("item", result, ("lit", 1)), ("lit", 2)), ("lit", 1)),
        ("lit", 1),
    )
    entities = {
        balance: CellDeclaration(IntRange(0, None), 100),
        attempts: CellDeclaration(IntRange(0, None), 0),
        withdraw: Function(
            ("n",),
            (
                "seq",
                ("write", "attempts", ("add", ("read", "attempts"), ("lit", 1))),
                ("write", "balance", ("sub", ("read", "balance"), ("arg", "n"))),
            ),
        ),
        EntityID("account_report.withdraw.links"): links(
            withdraw,
            attempts=attempts,
            balance=balance,
        ),
        withdraw_or_refuse: Function(
            ("n",),
            (
                "let",
                "r",
                ("catch", ("call", "withdraw", ("arg", "n")), ("cell_rejected",)),
                (
                    "if",
                    _ok(result),
                    ("item", result, ("lit", 1)),
                    ("tuple", ("lit", "refused"), constraint),
                ),
            ),
        ),
        EntityID("account_report.withdraw_or_refuse.links"): links(
            withdraw_or_refuse,
            withdraw=withdraw,
        ),
    }

    return Example(
        name="account_report",
        tags=frozenset({"side effects", "errors"}),
        program=program(entities),
        scenarios=(
            (
                Step(withdraw_or_refuse, (30,), 70, cells={balance: 70, attempts: 1}),
                Step(
                    withdraw_or_refuse,
                    (1000,),
                    ("refused", "violated"),
                    cells={balance: 70, attempts: 2},
                ),
                Step(
                    withdraw_or_refuse,
                    ("ten",),
                    Raises(LanguageError),
                    cells={balance: 70, attempts: 3},
                ),
                Step(withdraw_or_refuse, (70,), 0, cells={balance: 0, attempts: 4}),
            ),
        ),
        description=(
            "withdraw counts the attempt, then writes the balance, whose "
            "IntRange(0, None) constraint refuses an overdraft. "
            "withdraw_or_refuse catches only cell_rejected: an overdraft is "
            "reported as refused with its constraint result and the count it "
            "wrote first stays (no rollback), while withdrawing a string "
            "passes through as the language error it is."
        ),
    )


def _lookup() -> Example:
    find = EntityID("lookup.find")
    find_or = EntityID("lookup.find_or")
    why = EntityID("lookup.why")
    pairs = ("arg", "pairs")
    key = ("arg", "key")
    result = ("arg", "r")
    first = ("item", pairs, ("lit", 0))
    entities = {
        find: Function(
            ("key", "pairs"),
            (
                "if",
                ("eq", ("len", pairs), ("lit", 0)),
                (
                    "raise",
                    ("lit", "missing"),
                    ("tuple", ("tuple", ("lit", "key"), key)),
                ),
                (
                    "if",
                    ("eq", ("item", first, ("lit", 0)), key),
                    ("item", first, ("lit", 1)),
                    (
                        "call",
                        "find",
                        key,
                        ("slice", pairs, ("lit", 1), ("len", pairs)),
                    ),
                ),
            ),
        ),
        EntityID("lookup.find.links"): links(find, find=find),
        find_or: Function(
            ("key", "pairs", "default"),
            (
                "let",
                "r",
                ("catch", ("call", "find", key, pairs), ("missing",)),
                (
                    "if",
                    _ok(result),
                    ("item", result, ("lit", 1)),
                    ("arg", "default"),
                ),
            ),
        ),
        EntityID("lookup.find_or.links"): links(find_or, find=find),
        why: Function(
            ("key", "pairs"),
            (
                "let",
                "r",
                ("catch", ("call", "find", key, pairs)),
                # origin, kind and detail of the error; not where.
                ("slice", ("item", result, ("lit", 1)), ("lit", 0), ("lit", 3)),
            ),
        ),
        EntityID("lookup.why.links"): links(why, find=find),
    }
    table = (("a", 1), ("b", 2))
    malformed_pair = (("a",),)

    return Example(
        name="lookup",
        tags=frozenset({"data", "errors"}),
        program=program(entities),
        scenarios=(
            (
                Step(find, ("b", table), 2),
                Step(find, ("z", table), Raises(LanguageError)),
                Step(find_or, ("z", table, 0), 0),
                Step(find_or, ("b", table, 0), 2),
                Step(
                    find_or,
                    ("a", malformed_pair, 0),
                    Raises(LanguageError),
                ),
                Step(
                    find_or,
                    ("a", (7,), 0),
                    Raises(LanguageError),
                ),
                Step(
                    why,
                    ("z", table),
                    ("program", "missing", (("key", "z"),)),
                ),
                Step(
                    why,
                    ("a", malformed_pair),
                    (
                        "language",
                        "out_of_range",
                        (
                            ("index", 1),
                            ("length", 1),
                            ("operation", "item"),
                        ),
                    ),
                ),
                Step(
                    why,
                    ("a", (7,)),
                    (
                        "language",
                        "wrong_kind",
                        (
                            ("expected", "indexable"),
                            ("got", "int"),
                            ("operation", "item"),
                        ),
                    ),
                ),
            ),
        ),
        description=(
            "find raises its own missing error with the key as detail. "
            "find_or catches only missing and falls back to a default. "
            "A pair missing its value produces out_of_range; a scalar "
            "used as a pair produces wrong_kind. Neither failure is "
            "silently converted into the default. why preserves the "
            "origin, kind, and structured detail of each failure."
        ),
    )


EXAMPLES: tuple[Example, ...] = (
    _safe_install(),
    _account_report(),
    _lookup(),
)
