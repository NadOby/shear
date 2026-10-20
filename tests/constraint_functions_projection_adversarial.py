"""Adversarial generic canonical-projection acceptance for SHEAR #123.

Execute must provide:
    select_projection(value, path) -> canonical subtree

The path is a tuple of nonnegative integer indices into the existing
canonical tagged representation. CanonicalNode is inspected structurally
as ("__type__", kind, payload). No constraint-specific traversal is allowed.

All candidate methods must execute admitted ordinary SHEAR functions.
This Plan-owned module is not discovered until Execute registers it.
"""

from importlib import import_module
from random import Random
import unittest

from shear import (
    EntityID,
    StateID,
    VersionID,
    canonicalize,
    canonical_serialize,
    kind_of,
)
from tests.constraint_functions_complete_projection import (
    KINDS,
    NESTED,
)
from tests.constraint_functions_complete_acceptance import (
    candidate_execution_guard,
    forbid_incumbent,
)


LEAVES = (
    None,
    False,
    True,
    0,
    1,
    -1,
    2 ** 1024,
    -(2 ** 1024),
    "",
    "\x00",
    "e\u0301",
    "\U0001f600",
    b"",
    b"\x00\xff",
    EntityID("x"),
    StateID("x"),
    VersionID("x"),
)

MAP_KEYS = (
    "key",
    b"key",
    17,
    True,
    EntityID("key"),
    ("key", 1),
)

COUNTABLE = frozenset({"str", "bytes", "tuple", "list", "map"})


def canonical_bytes(value):
    return canonical_serialize(canonicalize(value))


def generated(seed, depth=5):
    """Deterministic heterogeneous nested data, without oracle outputs."""
    rng = Random(seed)

    def build(level):
        if level == 0 or rng.randrange(5) == 0:
            return rng.choice(LEAVES)

        form = rng.randrange(3)
        count = rng.randrange(5)

        if form == 0:
            return tuple(build(level - 1) for _ in range(count))

        if form == 1:
            return [build(level - 1) for _ in range(count)]

        keys = rng.sample(MAP_KEYS, count)
        return {key: build(level - 1) for key in keys}

    return build(depth)


def structural_paths(value):
    """Enumerate paths independently from the candidate implementation."""
    paths = []

    def visit(node, path):
        paths.append((path, node))
        if isinstance(node, tuple):
            for index, child in enumerate(node):
                visit(child, path + (index,))

    visit(canonicalize(value), ())
    return tuple(paths)


def sampled_paths(value, maximum=12):
    paths = structural_paths(value)
    if len(paths) <= maximum:
        return paths

    indices = {
        index * (len(paths) - 1) // (maximum - 1)
        for index in range(maximum)
    }
    indices.add(0)
    indices.add(len(paths) - 1)
    return tuple(paths[index] for index in sorted(indices))


def deep_value(depth):
    value = {"terminal": b"\x00\xff"}
    for index in range(depth):
        value = (value,) if index % 2 else [value]
    return value


def wide_value(width):
    return {
        f"key-{index:04d}": (index, [index, index + 1])
        for index in range(width)
    }


class AdversarialProjectionAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.candidate = import_module(
                "tests.constraint_functions_complete_candidate"
            )

        cls.entries = cls.candidate.EVALUATOR_ENTRIES
        for operation in (
            "inspect_projection",
            "equal_projection",
            "select_projection",
        ):
            if not callable(getattr(cls.candidate, operation, None)):
                raise AssertionError(
                    f"candidate lacks {operation}"
                )

    def execute(self, operation, *arguments):
        with candidate_execution_guard(self.entries) as opened:
            result = getattr(self.candidate, operation)(*arguments)
        self.assertTrue(
            opened, f"{operation}: no admitted SHEAR evaluator entered"
        )
        return result

    def assert_inspection(self, value):
        before = canonical_bytes(value)
        result = self.execute("inspect_projection", value)

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)

        observed_kind, observed_length, reconstructed = result
        expected_kind = kind_of(value)

        self.assertEqual(observed_kind, expected_kind)
        self.assertEqual(
            observed_length,
            len(value) if expected_kind in COUNTABLE else None,
        )
        self.assertEqual(canonical_bytes(reconstructed), before)
        self.assertEqual(canonical_bytes(value), before)

    def assert_selection(self, value, path, expected):
        actual = self.execute("select_projection", value, path)
        self.assertEqual(
            canonical_bytes(actual),
            canonical_bytes(expected),
            f"incorrect subtree at path {path!r}",
        )

    def test_full_cross_kind_equality_matrix(self):
        self.assertEqual(len(KINDS), 15)

        for left_kind, left in KINDS:
            for right_kind, right in KINDS:
                with self.subTest(left=left_kind, right=right_kind):
                    expected = canonical_bytes(left) == canonical_bytes(right)
                    actual = self.execute("equal_projection", left, right)
                    self.assertIs(type(actual), bool)
                    self.assertIs(actual, expected)

    def test_deterministic_generated_nested_values(self):
        for seed in range(128):
            with self.subTest(seed=seed):
                value = generated(seed)
                self.assert_inspection(value)

    def test_structural_path_access(self):
        values = tuple(value for _, value in KINDS) + NESTED
        values += tuple(generated(seed) for seed in range(64))

        for number, value in enumerate(values):
            with self.subTest(case=number):
                for path, expected in sampled_paths(value):
                    self.assert_selection(value, path, expected)

    def test_deep_and_wide_structures(self):
        for depth in (8, 64, 128, 256):
            with self.subTest(depth=depth):
                value = deep_value(depth)
                self.assert_inspection(value)

                for path, expected in sampled_paths(value):
                    self.assert_selection(value, path, expected)

        for width in (8, 64, 256):
            with self.subTest(width=width):
                value = wide_value(width)
                self.assert_inspection(value)

                for path, expected in sampled_paths(value):
                    self.assert_selection(value, path, expected)

    def test_reordered_maps_preserve_identity(self):
        for seed in range(64):
            rng = Random(seed)
            entries = [
                (key, generated(seed * 10 + index, depth=3))
                for index, key in enumerate(MAP_KEYS)
            ]
            rng.shuffle(entries)
            first = dict(entries)
            second = dict(reversed(entries))

            with self.subTest(seed=seed):
                self.assertEqual(canonical_bytes(first), canonical_bytes(second))
                self.assert_inspection(first)
                self.assert_inspection(second)
                self.assertIs(
                    self.execute("equal_projection", first, second),
                    True,
                )

    def test_near_equal_values_are_distinguished(self):
        for seed in range(64):
            left = {"payload": generated(seed), "version": seed}
            right = {"payload": generated(seed), "version": seed + 1}

            with self.subTest(seed=seed):
                self.assertNotEqual(canonical_bytes(left), canonical_bytes(right))
                self.assertIs(
                    self.execute("equal_projection", left, right),
                    False,
                )

    def test_tagged_tuple_is_not_a_semantic_record(self):
        impostor = ("__type__", "map", (("key", 1),))
        actual_map = {"key": 1}

        self.assertEqual(kind_of(impostor), "tuple")
        self.assertEqual(kind_of(actual_map), "map")
        self.assertNotEqual(
            canonical_bytes(impostor),
            canonical_bytes(actual_map),
        )

        self.assert_inspection(impostor)
        self.assert_inspection(actual_map)
        self.assertIs(
            self.execute("equal_projection", impostor, actual_map),
            False,
        )

    def test_type_and_identity_collisions(self):
        collisions = (
            (True, 1),
            (False, 0),
            ("x", b"x"),
            ((1, 2), [1, 2]),
            (EntityID("x"), StateID("x")),
            (EntityID("x"), VersionID("x")),
            (StateID("x"), VersionID("x")),
            ({"x": True}, {"x": 1}),
            ({1: "value"}, {True: "value"}),
        )

        for left, right in collisions:
            with self.subTest(left=repr(left), right=repr(right)):
                self.assertNotEqual(
                    canonical_bytes(left),
                    canonical_bytes(right),
                )
                self.assertIs(
                    self.execute("equal_projection", left, right),
                    False,
                )

    def test_path_result_depends_on_machine_output(self):
        value = {"a": [1, 2], "b": {"c": True}}
        path = (1,)
        expected = "map"

        self.assertEqual(
            self.execute("select_projection", value, path),
            expected,
        )

        with candidate_execution_guard(
            self.entries,
            forced="__corrupted_machine_result__",
        ) as opened:
            try:
                actual = self.candidate.select_projection(value, path)
            except Exception:
                changed = True
            else:
                changed = actual != expected

        self.assertTrue(opened, "perturbation never reached the evaluator")
        self.assertTrue(
            changed,
            "projection result is independent of machine output",
        )


if __name__ == "__main__":
    unittest.main()
