"""Endpoint arity: one endpoint versus a one-element tuple (roadmap task 21).

A role holds one ``EntityID`` or an ordered tuple of them, and the two are
different records (relation_model.md §2, "Endpoint arity"). These tests pin
the observations the audit classifies:

- the record keeps the distinction;
- every relation the language builds has, per role, the arity its kind
  declares, across both corpora and the states their runs produce, so for
  language relations the distinction carries nothing the kind does not;
- a constraint sees a one-element tuple role as a tuple, so for relations
  of kinds the core does not interpret it is observable.
"""

import unittest

from shear import (
    CellDeclaration,
    EntityID,
    IsKind,
    Relation,
    RelationConstraintRejected,
    Role,
    Runtime,
    State,
    Value,
    continuity,
    examples,
)
from shear.lang import (
    BODY_ROLE,
    DEFINITION_KIND,
    LABEL_ROLE_PREFIX,
    LINK_ROLE_PREFIX,
    LINKS_KIND,
    load,
    run,
)
from shear.operations import OPERATIONS
from shear.relations import relations_of
from shear.syntax import parse

ONE = "one endpoint"
MANY = "tuple"

# operations.py declares the arity of code roles only. The other roles of
# code relations name link targets; their arity is fixed by lang._Builder.
LINK_TARGET_ROLES = {
    "call": {"target": ONE},
    "read": {"cell": ONE},
    "write": {"cell": ONE},
    "ref": {"target": ONE},
    "code": {"target": ONE},
    "linksof": {"target": ONE},
    "activate": {"targets": MANY},
    "trial": {"target": ONE, "targets": MANY},
}


def declared(relation: Relation) -> dict[str, str] | None:
    """Role name to declared arity for a language relation, else None."""

    if relation.kind in OPERATIONS:
        shape = OPERATIONS[relation.kind]
        roles = {
            role: MANY if role in shape.ordered else ONE
            for role in shape.code
        }
        roles.update(LINK_TARGET_ROLES.get(relation.kind, {}))
        return roles

    if relation.kind == DEFINITION_KIND:
        return {
            role: ONE
            for role in relation.roles
            if role == BODY_ROLE
            or role.startswith((LINK_ROLE_PREFIX, LABEL_ROLE_PREFIX))
        }

    if relation.kind == LINKS_KIND:
        return {role: ONE for role in relation.roles}

    return None


def arity_problems(state: State, label: str) -> list[str]:
    problems = []

    for entity, relation in relations_of(state).items():
        roles = declared(relation)

        if roles is None:
            problems.append(
                f"{label}: {entity.value} has relation kind "
                f"{relation.kind!r}, which declared() does not classify"
            )
            continue

        for role, endpoint in relation.roles.items():
            actual = MANY if isinstance(endpoint, tuple) else ONE

            if role not in roles:
                problems.append(
                    f"{label}: {entity.value} ({relation.kind}) has "
                    f"undeclared role {role!r}"
                )
            elif actual != roles[role]:
                problems.append(
                    f"{label}: {entity.value} ({relation.kind}) role "
                    f"{role!r} holds {actual}, declared {roles[role]}"
                )

    return problems


class RecordTests(unittest.TestCase):
    def test_one_endpoint_and_a_one_element_tuple_are_different_records(self):
        a = EntityID("a")
        one = Relation("kind", {"role": a})
        many = Relation("kind", {"role": (a,)})

        self.assertNotEqual(one, many)
        self.assertEqual(one.endpoints, many.endpoints)
        self.assertNotEqual(
            Value.create(EntityID("r"), one).version_id,
            Value.create(EntityID("r"), many).version_id,
        )


class LanguageRelationTests(unittest.TestCase):
    """Every relation the language builds has its declared arity."""

    def test_corpus_programs_and_their_runs(self):
        problems = []

        for example in examples.EXAMPLES:
            states = {}

            def recording(runtime, entry, *args, **options):
                try:
                    return run(runtime, entry, *args, **options)
                finally:
                    state = runtime.active.state
                    states[state.id] = state

            problems += arity_problems(example.program, f"{example.name}, input")
            problems += arity_problems(load(example.program), example.name)
            examples.play(example, recording)

            for state in states.values():
                problems += arity_problems(state, f"{example.name}, after a step")

        self.assertEqual(problems, [])

    def test_continuity_cases_and_their_results(self):
        problems = []

        for case in continuity.CASES:
            source = load(parse(case.source))
            problems += arity_problems(source, case.name)

            try:
                produced = case.operation(source)
            except Exception:
                continue  # a case that expects rejection

            results = produced if isinstance(produced, tuple) else (produced,)

            for result in results:
                problems += arity_problems(
                    result.destination,
                    f"{case.name}, result",
                )

        self.assertEqual(problems, [])

    def test_link_target_roles_are_operations_but_not_code_roles(self):
        self.assertLessEqual(set(LINK_TARGET_ROLES), set(OPERATIONS))

        for kind, roles in LINK_TARGET_ROLES.items():
            with self.subTest(kind=kind):
                self.assertTrue(set(roles).isdisjoint(OPERATIONS[kind].code))


class ConstraintSubjectTests(unittest.TestCase):
    """A role holding a tuple maps to the tuple of its endpoints' contents
    (relation_model.md §7), one-element tuples included."""

    def state(self, endpoint, kind):
        cell, relation = EntityID("cell"), EntityID("relation")

        return State.create({
            cell: Value.create(cell, CellDeclaration(IsKind("int"), 5)),
            relation: Value.create(
                relation,
                Relation("typed", {"value": endpoint}, Role("value", IsKind(kind))),
            ),
        })

    def test_a_one_element_tuple_role_is_seen_as_a_tuple(self):
        cell = EntityID("cell")

        for endpoint, kind, loads in (
            (cell, "int", True),
            ((cell,), "tuple", True),
            (cell, "tuple", False),
            ((cell,), "int", False),
        ):
            with self.subTest(endpoint=endpoint, kind=kind):
                try:
                    Runtime(self.state(endpoint, kind))
                except RelationConstraintRejected:
                    loaded = False
                else:
                    loaded = True

                self.assertEqual(loaded, loads)


if __name__ == "__main__":
    unittest.main()
