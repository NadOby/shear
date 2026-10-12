"""The version in a reference (roadmap task 22).

``Reference(StateID, EntityID, VersionID)``: ``StateID`` is derived from
every entity's ``VersionID`` and the ownership relation (state_model.md
section 4), so for a reference that names a real state the version follows
from the state and the entity (reference_model.md section 14). These tests
pin the observations the audit classifies:

- every reference the model produces has the version its state and entity
  determine, so two references that agree on state and entity agree on the
  version;
- such a reference never fails the version check, in ``State.resolve`` or in
  ``transfer_reference``; only a reference built by hand with another
  version is stale.

If a later change breaks the premise (a ``StateID`` that does not cover
every entity's version, a reference without a ``StateID``, or resolution
against another state), these tests fail and the classification must be
revisited.
"""

import random
import unittest

from shear import (
    AmbiguousEntityMapping,
    EntityID,
    MissingEntityMapping,
    Reference,
    StaleReference,
    State,
    TransformResult,
    continuity,
    rebind_reference,
    transfer_reference,
    version_id_for,
)
from shear.lang import load
from shear.syntax import parse
from tests.generation import seeds
from tests.test_properties import (
    apply_stating_ownership,
    random_definition,
    random_state,
)


def rebuilt(state: State) -> State:
    """The same content, supplied in reverse order: an independent object
    with the same ``StateID``."""

    return State.create(
        dict(reversed(list(state.values.items()))),
        dict(reversed(list(state.ownership.items()))),
    )


def references(
    states: list[State],
    results: list[TransformResult],
) -> list[Reference]:
    """Every reference the model's own producers make from these states and
    results: ``State.reference``, ``transfer_reference`` and
    ``rebind_reference``."""

    pool = [
        state.reference(entity)
        for state in states
        for entity in state.values
    ]

    for result in results:
        for entity in result.source.values:
            try:
                pool.append(
                    transfer_reference(
                        result.source.reference(entity), result,
                    )
                )
            except (MissingEntityMapping, AmbiguousEntityMapping):
                pass

        for entity in result.destination.values:
            stale_source = result.source.reference(
                next(iter(result.source.values))
            )
            pool.append(
                rebind_reference(stale_source, result.destination, entity)
            )

    return pool


def generated_cases():
    for seed in seeds(150):
        rng = random.Random(seed)
        state = random_state(rng)
        definition, _ = random_definition(rng, sorted(state.values), "n")

        try:
            result = apply_stating_ownership(definition, state)
        except (KeyError, ValueError):
            yield seed, [state, rebuilt(state)], []
            continue

        states = [state, rebuilt(state), result.destination]
        yield seed, states, [result]


def corpus_cases():
    for case in continuity.CASES:
        source = load(parse(case.source))

        try:
            produced = case.operation(source)
        except Exception:
            yield case.name, [source, rebuilt(source)], []
            continue

        results = list(produced) if isinstance(produced, tuple) else [produced]
        states = [source, rebuilt(source)] + [
            result.destination for result in results
        ]
        yield case.name, states, results


def all_cases():
    yield from (("seed", seed, s, r) for seed, s, r in generated_cases())
    yield from (("case", name, s, r) for name, s, r in corpus_cases())


class VersionIsDeterminedTests(unittest.TestCase):
    def test_state_and_entity_determine_the_version(self) -> None:
        checked = 0

        for label, key, states, results in all_cases():
            with self.subTest(**{label: key}):
                seen = {}

                for reference in references(states, results):
                    place = (reference.state, reference.entity)
                    seen.setdefault(place, set()).add(reference.version)

                for place, versions in seen.items():
                    self.assertEqual(
                        len(versions), 1,
                        f"{place[1].value}: {len(versions)} versions",
                    )

                for state in states:
                    for entity, value in state.values.items():
                        self.assertEqual(
                            seen[(state.id, entity)],
                            {version_id_for(value)},
                        )
                        checked += 1

        self.assertGreater(checked, 1000)

    def test_a_produced_reference_is_never_stale(self) -> None:
        resolved = 0
        transferred = 0

        for label, key, states, results in all_cases():
            with self.subTest(**{label: key}):
                pool = references(states, results)

                for reference in pool:
                    for state in states:
                        if state.id != reference.state:
                            continue

                        value = state.resolve(reference)
                        self.assertEqual(
                            version_id_for(value), reference.version,
                        )
                        resolved += 1

                    for result in results:
                        if result.source.id != reference.state:
                            continue

                        try:
                            transfer_reference(reference, result)
                        except StaleReference:
                            self.fail(
                                f"{reference.entity.value} was stale"
                            )
                        except (
                            MissingEntityMapping,
                            AmbiguousEntityMapping,
                        ):
                            pass
                        else:
                            transferred += 1

        self.assertGreater(resolved, 1000)
        self.assertGreater(transferred, 100)

    def test_only_a_hand_built_reference_is_stale(self) -> None:
        source = load(parse(continuity.CASES[0].source))
        entity = next(iter(source.values))
        produced = source.reference(entity)
        other = next(
            value for value in source.values.values()
            if version_id_for(value) != produced.version
        )

        forged = Reference(
            state=produced.state,
            entity=entity,
            version=version_id_for(other),
        )

        with self.assertRaises(StaleReference):
            source.resolve(forged)

        self.assertEqual(source.resolve(produced), source.values[entity])


if __name__ == "__main__":
    unittest.main()
