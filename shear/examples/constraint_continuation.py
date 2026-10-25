"""Authenticated SHEAR continuation for named External constraints.

A suspended evaluation returns ("external", name, subject, continuation).
Only the callback crosses the host boundary; SHEAR owns traversal, budget,
strong-Kleene composition, short circuiting, and resumed verdicts.

The continuation contains only immutable, canonicalizable data. Resuming it
never re-evaluates an earlier constraint node or repeats an External call.
"""

from __future__ import annotations

from ..constraints import Constraint
from ..identity import EntityID
from ..lang import Function, links
from ..relations import Relation
from .constraint_evaluator import (
    BUDGET_STEP,
    INT_RANGE,
    IS_KIND,
    LENGTH,
    LOGIC_NOT,
    ONE_OF,
    UNKNOWN,
    SATISFIED,
    VIOLATED,
    evaluator_entities,
)


START = EntityID("constraint.continuation.start")
RESUME = EntityID("constraint.continuation.resume")
EVALUATE = EntityID("constraint.continuation.evaluate")
EVAL_NODE = EntityID("constraint.continuation.node")
FOLD_START = EntityID("constraint.continuation.fold.start")
FINISH = EntityID("constraint.continuation.finish")
EVAL_ROLE = EntityID("constraint.continuation.role")
FIND_ROLE = EntityID("constraint.continuation.role.find")


def _arg(name: str) -> tuple:
    return ("arg", name)


def _lit(value: object) -> tuple:
    return ("lit", value)


def _item(value: tuple, index: int) -> tuple:
    return ("item", value, _lit(index))


def _call(target: str, *args: tuple) -> tuple:
    return ("call", target, *args)


def _frame(*parts: tuple) -> tuple:
    return ("tuple", *parts)


def _finish(verdict: tuple, remaining: tuple, frames: tuple) -> tuple:
    return _call("finish", verdict, remaining, frames)


def _evaluate() -> tuple:
    remaining = _arg("remaining")
    frames = _arg("frames")
    return (
        "let", "step", _call("budget", remaining),
        (
            "if", _item(_arg("step"), 0),
            _call(
                "node", _arg("subject"), _arg("constraint"),
                _item(_arg("step"), 1), frames,
            ),
            _finish(_lit(UNKNOWN), _item(_arg("step"), 1), frames),
        ),
    )


def _eval_node() -> tuple:
    subject = _arg("subject")
    remaining = _arg("remaining")
    frames = _arg("frames")
    args = _arg("arguments")

    def at(index: int) -> tuple:
        return _item(args, index)

    cases = (
        "raise", _lit("constraint_form"),
        _lit("unknown constraint form"),
    )
    alternatives = (
        ("is_kind", _finish(
            _call("is_kind", subject, at(0)), remaining, frames,
        )),
        ("int_range", _finish(
            _call("int_range", subject, at(0), at(1)), remaining, frames,
        )),
        ("length", _finish(
            _call("length", subject, at(0), at(1)), remaining, frames,
        )),
        ("one_of", _finish(
            _call("one_of", subject, at(0)), remaining, frames,
        )),
        ("all_of", _call(
            "fold", subject, at(0), remaining, frames,
            _lit(VIOLATED), _lit(SATISFIED),
        )),
        ("any_of", _call(
            "fold", subject, at(0), remaining, frames,
            _lit(SATISFIED), _lit(VIOLATED),
        )),
        ("not", _call(
            "evaluate", subject, at(0), remaining,
            _frame(_lit("not"), frames),
        )),
        ("role", _call(
            "role", subject, at(0), at(1), remaining, frames,
        )),
        ("external", _frame(
            _lit("external"), at(0), subject,
            _frame(remaining, frames),
        )),
    )
    for form, body in reversed(alternatives):
        cases = (
            "if", ("eq", _arg("form"), _lit(form)), body, cases,
        )
    return (
        "let", "form", ("item", _arg("constraint"), _lit("form")),
        (
            "let", "arguments",
            ("item", _arg("constraint"), _lit("arguments")),
            cases,
        ),
    )


def _fold_start() -> tuple:
    subject = _arg("subject")
    parts = _arg("parts")
    remaining = _arg("remaining")
    frames = _arg("frames")
    decisive = _arg("decisive")
    empty = _arg("empty")
    return (
        "if", ("lt", _lit(0), ("len", parts)),
        _call(
            "evaluate", subject, _item(parts, 0), remaining,
            _frame(
                _lit("fold"), subject, parts, _lit(1),
                _lit(False), decisive, empty, frames,
            ),
        ),
        _finish(empty, remaining, frames),
    )


def _finish_body() -> tuple:
    verdict = _arg("verdict")
    remaining = _arg("remaining")
    frames = _arg("frames")
    parts = _item(frames, 2)
    index = _item(frames, 3)
    seen = _item(frames, 4)
    decisive = _item(frames, 5)
    empty = _item(frames, 6)
    parent = _item(frames, 7)
    next_seen = (
        "if", ("eq", verdict, _lit(UNKNOWN)), _lit(True), seen,
    )
    final = (
        "if", next_seen, _lit(UNKNOWN), empty,
    )
    fold = (
        "if", ("eq", verdict, decisive),
        _finish(verdict, remaining, parent),
        (
            "if", ("lt", index, ("len", parts)),
            _call(
                "evaluate", _item(frames, 1),
                ("item", parts, index), remaining,
                _frame(
                    _lit("fold"), _item(frames, 1), parts,
                    ("add", index, _lit(1)), next_seen,
                    decisive, empty, parent,
                ),
            ),
            _finish(final, remaining, parent),
        ),
    )
    return (
        "if", ("eq", frames, _lit(None)), verdict,
        (
            "if", ("eq", _item(frames, 0), _lit("not")),
            _finish(
                _call("negate", verdict), remaining,
                _item(frames, 1),
            ),
            fold,
        ),
    )


def _eval_role() -> tuple:
    subject = _arg("subject")
    remaining = _arg("remaining")
    frames = _arg("frames")
    return (
        "if",
        (
            "eq", _item(("inspect", subject), 0), _lit("map"),
        ),
        _call(
            "find", subject, _arg("name"), _arg("part"),
            _lit(0), remaining, frames,
        ),
        _finish(_lit(VIOLATED), remaining, frames),
    )


def _find_role() -> tuple:
    subject = _arg("subject")
    index = _arg("index")
    remaining = _arg("remaining")
    frames = _arg("frames")
    entry = _arg("entry")
    return (
        "if", ("lt", index, ("len", subject)),
        (
            "let", "entry", ("item", subject, index),
            (
                "if", ("eq", _item(entry, 0), _arg("name")),
                _call(
                    "evaluate", _item(entry, 1), _arg("part"),
                    remaining, frames,
                ),
                _call(
                    "next", subject, _arg("name"), _arg("part"),
                    ("add", index, _lit(1)), remaining, frames,
                ),
            ),
        ),
        _finish(_lit(VIOLATED), remaining, frames),
    )


def continuation_entities(
    constraint: Constraint, budget: int | None = None,
) -> dict[EntityID, Function | Relation]:
    """Bind declarations to independently admitted resumable SHEAR code."""
    if not isinstance(constraint, Constraint):
        raise TypeError("expected a semantic Constraint")
    if budget is not None and (type(budget) is not int or budget < 0):
        raise ValueError("budget must be a non-negative integer")

    entities = evaluator_entities()
    entities.update({
        START: Function(("subject",), _call(
            "evaluate", _arg("subject"), _lit(constraint),
            _lit(budget), _lit(None),
        )),
        RESUME: Function(("continuation", "verdict"), _call(
            "finish", _arg("verdict"),
            _item(_arg("continuation"), 0),
            _item(_arg("continuation"), 1),
        )),
        EVALUATE: Function(
            ("subject", "constraint", "remaining", "frames"),
            _evaluate(),
        ),
        EVAL_NODE: Function(
            ("subject", "constraint", "remaining", "frames"),
            _eval_node(),
        ),
        FOLD_START: Function(
            ("subject", "parts", "remaining", "frames", "decisive", "empty"),
            _fold_start(),
        ),
        FINISH: Function(("verdict", "remaining", "frames"), _finish_body()),
        EVAL_ROLE: Function(
            ("subject", "name", "part", "remaining", "frames"),
            _eval_role(),
        ),
        FIND_ROLE: Function(
            ("subject", "name", "part", "index", "remaining", "frames"),
            _find_role(),
        ),
        EntityID(f"{START.value}.links"): links(
            START, evaluate=EVALUATE,
        ),
        EntityID(f"{RESUME.value}.links"): links(
            RESUME, finish=FINISH,
        ),
        EntityID(f"{EVALUATE.value}.links"): links(
            EVALUATE, budget=BUDGET_STEP, node=EVAL_NODE, finish=FINISH,
        ),
        EntityID(f"{EVAL_NODE.value}.links"): links(
            EVAL_NODE, is_kind=IS_KIND, int_range=INT_RANGE,
            length=LENGTH, one_of=ONE_OF, evaluate=EVALUATE,
            fold=FOLD_START, role=EVAL_ROLE, finish=FINISH,
        ),
        EntityID(f"{FOLD_START.value}.links"): links(
            FOLD_START, evaluate=EVALUATE, finish=FINISH,
        ),
        EntityID(f"{FINISH.value}.links"): links(
            FINISH, finish=FINISH, negate=LOGIC_NOT, evaluate=EVALUATE,
        ),
        EntityID(f"{EVAL_ROLE.value}.links"): links(
            EVAL_ROLE, find=FIND_ROLE, finish=FINISH,
        ),
        EntityID(f"{FIND_ROLE.value}.links"): links(
            FIND_ROLE, evaluate=EVALUATE, next=FIND_ROLE, finish=FINISH,
        ),
    })
    return entities
