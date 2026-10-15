"""Plan-owned task 31 acceptance tests: one table of the instructions
lowering emits (docs/live_evolution.md section 5.2, issue #67).

The table is metadata shared by admission, the host machine's tests and the
SHEAR-written VM; execution semantics stay separate per route. It is checked
here against independent sources: the host machine's dispatch, every chunk
``bytecode.lower`` produces for the corpus and the operation witnesses, and
the VM's instruction set. Every test fails before task 31 is implemented.
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from unittest import mock

from shear import EntityID, bytecode, machine, operations
from shear.examples import EXAMPLES, vm
from shear.hosted_bootstrap import AdmissionRejected
from shear.hosted_bootstrap import validation
from shear.lang import NODE_KINDS, load
from shear.relations import relation_of
from tests.test_bootstrap_boundary import VM_MISSING_INSTRUCTIONS, _node_for
from tests.live_support import LIVE, code_nodes
from tests.test_operations import dispatched

# Instructions the host machine dispatches but lowering never emits.
INTERNAL = frozenset({"CATCH_OK", "RETURN"})


def table():
    from shear.instructions import INSTRUCTIONS

    return INSTRUCTIONS


def entities_in(value):
    """Every ``EntityID`` inside a role value."""

    if isinstance(value, EntityID):
        yield value
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from entities_in(item)
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from entities_in(item)


def corpus_chunks():
    """``(where, state or None, relation, chunk)`` for every corpus code node
    and every operation witness, lowered by the host."""

    for kind in operations.OPERATIONS:
        relation = _node_for(kind)
        yield kind, None, relation, bytecode.lower(relation)

    for example in EXAMPLES:
        state = load(example.program)

        for node, _ in code_nodes(state):
            relation = relation_of(state.values[node])
            yield example.name, state, relation, bytecode.lower(relation)


def is_code(state, entity):
    if state is None:
        return None

    relation = relation_of(state.values[entity])
    return relation is not None and relation.kind in NODE_KINDS


class InstructionTable(unittest.TestCase):

    def test_the_table_is_the_emitted_instruction_set(self):
        self.assertEqual(
            set(table()),
            dispatched(machine._execute, "op") - INTERNAL,
        )

    def test_host_lowering_agrees_with_the_table(self):
        instructions = table()

        for where, state, relation, chunk in corpus_chunks():
            named = set(entities_in(relation.roles))

            for instruction in chunk:
                op, operands = instruction[0], instruction[1:]

                with self.subTest(where=where, op=op):
                    self.assertIn(op, instructions)
                    entry = instructions[op]
                    self.assertEqual(len(operands), entry.operands)

                    for position, operand in enumerate(operands):
                        found = set(entities_in(operand))

                        if position in entry.children:
                            # A child is one of the node's own code children.
                            self.assertIsInstance(operand, EntityID)
                            self.assertIn(operand, named)
                            self.assertIsNot(is_code(state, operand), False)
                        elif position in entry.linked:
                            # Link targets: an entity, a tuple of them, or
                            # none when the link did not resolve.
                            self.assertLessEqual(found, named)

                            for target in found:
                                self.assertIsNot(is_code(state, target), True)
                        else:
                            self.assertFalse(
                                found, "an entity operand the table misses",
                            )

    def test_the_vm_lacks_exactly_the_declared_instructions(self):
        instructions = set(table())

        self.assertLessEqual(set(vm._ORDER), instructions)
        self.assertEqual(
            instructions - set(vm._ORDER), VM_MISSING_INSTRUCTIONS,
        )


class AdmissionReadsTheTable(unittest.TestCase):

    def live_nodes(self):
        for example in EXAMPLES:
            if example.name not in LIVE - {"bootstrap"}:
                continue

            state = load(example.program)

            for node, owner in code_nodes(state):
                chunk = bytecode.lower(relation_of(state.values[node]))
                yield example.name, state, node, owner, chunk

    def test_admission_accepts_host_chunks_and_rejects_extra_operands(self):
        for name, state, node, owner, chunk in self.live_nodes():
            with self.subTest(example=name, node=node.value):
                validation.validate_chunk(state, node, owner, chunk)

                for index, instruction in enumerate(chunk[:-1]):
                    widened = (
                        *chunk[:index],
                        (*instruction, None),
                        *chunk[index + 1:],
                    )

                    with self.assertRaises(AdmissionRejected):
                        validation.validate_chunk(state, node, owner, widened)

    def test_validation_follows_the_table(self):
        instructions = table()

        for name, state, node, owner, chunk in self.live_nodes():
            ops = {instruction[0] for instruction in chunk}

            if "ADD" not in ops:
                continue

            validation.validate_chunk(state, node, owner, chunk)

            # Without its table entry, the same well-formed chunk is refused.
            with mock.patch.dict(instructions):
                del instructions["ADD"]

                with self.assertRaises(AdmissionRejected):
                    validation.validate_chunk(state, node, owner, chunk)

            validation.validate_chunk(state, node, owner, chunk)
            return

        self.fail("no live node lowers to ADD")


if __name__ == "__main__":
    unittest.main()
