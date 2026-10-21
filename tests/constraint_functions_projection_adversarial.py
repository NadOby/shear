"""Adversarial generic semantic-inspection acceptance for SHEAR #123.

Execute must provide:
    inspect_projection(value) -> (kind, length_or_none, reconstructed)
    equal_projection(left, right) -> bool
    select_projection(value, path) -> selected semantic value

Paths address public semantic structure using integer sequence/map-entry
indices and declared semantic-record field names. Opaque values are leaves;
private CanonicalNode tags and serialized payloads are never path elements.

Every candidate operation must enter authenticated ordinary SHEAR code.
This Plan-owned module remains outside discovery until Execute.

An inconsistent machine result may be rejected only with explicit operation
and VM-output provenance. Generic processing failures do not qualify.
"""

from collections.abc import Mapping
from importlib import import_module
from random import Random
import unittest

from shear import (
    AllOf,
    AnyOf,
    CellDeclaration,
    EntityID,
    External,
    IntRange,
    IsKind,
    Length,
    Not,
    OneOf,
    Relation,
    Role,
    StateID,
    VersionID,
    canonicalize,
    canonical_serialize,
    kind_of,
)
from shear.closures import Closure
from shear.constraints import Constraint
from shear.hosted_bootstrap import AdmissionRejected
from shear.lang import LanguageError
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
    """Independent host identity oracle, never candidate-side inspection."""
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


def constraint_arguments(value):
    """Public semantic operands for the independent record-field oracle."""
    if isinstance(value, IsKind):
        return (value.kind,)
    if isinstance(value, (IntRange, Length)):
        return (value.min, value.max)
    if isinstance(value, OneOf):
        return (value.values,)
    if isinstance(value, (AllOf, AnyOf)):
        return (value.parts,)
    if isinstance(value, Not):
        return (value.part,)
    if isinstance(value, Role):
        return (value.name, value.part)
    if isinstance(value, External):
        return (value.name,)
    raise AssertionError(f"unrecognized semantic constraint: {type(value)}")


def record_fields(value):
    """Reference the approved schema, not private canonical-node positions."""
    if isinstance(value, CellDeclaration):
        return (("constraint", value.constraint), ("initial", value.initial))
    if isinstance(value, Relation):
        return (
            ("kind", value.kind),
            ("roles", tuple(value.roles.items())),
            ("payload", value.payload),
        )
    if isinstance(value, Constraint):
        forms = {
            IsKind: "is_kind",
            IntRange: "int_range",
            Length: "length",
            OneOf: "one_of",
            AllOf: "all_of",
            AnyOf: "any_of",
            Not: "not",
            Role: "role",
            External: "external",
        }
        return (
            ("form", forms[type(value)]),
            ("arguments", constraint_arguments(value)),
        )
    return ()


def semantic_children(value):
    """Enumerate public paths using raw semantic fixtures only.

    Canonicalized nested values are intentionally terminal in this host
    oracle rather than being interpreted as tagged tuples. Explicit
    field/nested-access witnesses below exercise those cases through SHEAR.
    """
    if type(value) in (tuple, list, str, bytes):
        return tuple(enumerate(value))

    if isinstance(value, Mapping):
        entries = sorted(
            value.items(),
            key=lambda pair: canonical_bytes(pair[0]),
        )
        return tuple(enumerate(entries))

    fields = record_fields(value)
    return tuple((name, member) for name, member in fields)


def semantic_paths(value):
    """Enumerate finite public semantic paths independent of the candidate.

    A code-point selection returns a string, even for a one-code-point
    string. Stop recursive test enumeration at that character: otherwise
    indexing "a" at zero would generate (0, 0, 0, ...) indefinitely.
    """
    paths = []

    def visit(current, path, descend=True):
        paths.append((path, current))
        if not descend:
            return

        for component, child in semantic_children(current):
            visit(
                child,
                path + (component,),
                descend=not isinstance(current, str),
            )

    visit(value, ())
    return tuple(paths)


def sampled_paths(value, maximum=12):
    paths = semantic_paths(value)
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
            f"incorrect semantic value at path {path!r}",
        )

    def assert_invalid_selection(self, value, path):
        with candidate_execution_guard(self.entries) as opened:
            with self.assertRaises(LanguageError):
                self.candidate.select_projection(value, path)
        self.assertTrue(
            opened,
            f"invalid semantic path {path!r} bypassed admitted SHEAR",
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
        """The former canonical paths are now public semantic paths."""
        values = tuple(value for _, value in KINDS) + NESTED
        values += tuple(generated(seed) for seed in range(64))

        for number, value in enumerate(values):
            with self.subTest(case=number):
                for path, expected in sampled_paths(value):
                    self.assert_selection(value, path, expected)

    def test_deep_and_wide_structures(self):
        for depth in (8, 64, 128):
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
                for index in (0, len(first) - 1):
                    expected_key = sorted(
                        first, key=canonical_bytes,
                    )[index]
                    for mapping in (first, second):
                        self.assert_selection(
                            mapping, (index, 0), expected_key,
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
        self.assert_selection(impostor, (0,), "__type__")
        self.assert_selection(actual_map, (0, 0), "key")

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

    def test_opaque_semantic_leaves(self):
        opaque = (
            EntityID("sample"),
            VersionID("version"),
            StateID("state"),
            Closure(
                EntityID("owner"), EntityID("body"),
                ("parameter",), (("secret", 7),),
            ),
        )
        for value in opaque:
            with self.subTest(kind=kind_of(value)):
                self.assert_inspection(value)
                self.assert_selection(value, (), value)
                for path in ((0,), (2,), ("value",), ("captures",)):
                    self.assert_invalid_selection(value, path)

    def test_unicode_codepoints_and_bytes(self):
        text = "e\u0301\U0001f600\x00"
        raw = b"\x00\xff\x10"
        self.assert_inspection(text)
        self.assert_inspection(raw)
        for index, codepoint in enumerate(text):
            self.assert_selection(text, (index,), codepoint)
        for index, octet in enumerate(raw):
            self.assert_selection(raw, (index,), octet)
        self.assert_selection(text, (), text)
        self.assert_selection(raw, (), raw)
        self.assert_invalid_selection(text, (len(text),))
        self.assert_invalid_selection(raw, (len(raw),))

    def test_semantic_record_fields(self):
        cells = (
            CellDeclaration(IsKind("int"), 3),
            CellDeclaration(IsKind("map"), {"b": 2, "a": 1}),
        )
        constraints = (
            IsKind("int"), IntRange(0, 9), Length(1, 3),
            OneOf(True, 1), AllOf(IsKind("int"), IntRange(0, 9)),
            AnyOf(IsKind("bool"), IsKind("str")),
            Not(IsKind("bool")), Role("item", IsKind("int")),
            External("policy"),
        )
        relations = (
            Relation("single", {"item": EntityID("sample")}),
            Relation(
                "nested",
                {"z": EntityID("last"),
                 "a": (EntityID("first"),)},
                {"data": [1, 2]},
            ),
        )

        for record in cells + constraints + relations:
            with self.subTest(record=repr(record)):
                for index, (name, member) in enumerate(
                    record_fields(record)
                ):
                    self.assert_selection(record, (name,), member)
                    self.assert_selection(record, (index,), (name, member))
                    self.assert_selection(record, (index, 0), name)
                self.assert_invalid_selection(record, ("unknown_field",))

        self.assert_selection(cells[1], ("initial", 1, 1), 2)
        self.assert_selection(
            constraints[4], ("arguments", 0, 0, "form"),
            record_fields(constraints[4].parts[0])[0][1],
        )
        self.assert_selection(relations[1], ("roles", 0, 0), "a")
        self.assert_selection(
            relations[1], ("roles", 0, 1, 0), EntityID("first"),
        )
        self.assert_selection(relations[1], ("payload", 0, 1, 1), 2)

    def test_invalid_semantic_paths(self):
        for value, path in (
            (42, (0,)),
            (None, (0,)),
            ((1, 2), (-1,)),
            ((1, 2), (True,)),
            ((1, 2), (2,)),
            ((1, 2), ("field",)),
            ({"a": 1}, (1,)),
            ({"a": 1}, ("a",)),
            (b"\xff", (1,)),
        ):
            with self.subTest(value=repr(value), path=path):
                self.assert_invalid_selection(value, path)

    def test_large_and_repeated_semantic_access(self):
        """Demand-driven large-value cases; allocation measured separately."""
        text = "\U0001f600e\u0301" * 2048
        raw = bytes(range(256)) * 32
        entries = wide_value(1024)
        sequence = list(range(4096))

        for value in (text, raw, entries, sequence):
            with self.subTest(kind=kind_of(value)):
                self.assert_inspection(value)

        for index in (0, 4096, len(text) - 1):
            self.assert_selection(text, (index,), text[index])
        for index in (0, 4096, len(raw) - 1):
            self.assert_selection(raw, (index,), raw[index])
        for index in (0, 2048, len(sequence) - 1):
            self.assert_selection(sequence, (index,), sequence[index])

        ordered = sorted(entries, key=canonical_bytes)
        for index in (0, len(ordered) // 2, len(ordered) - 1):
            for _ in range(4):
                self.assert_selection(entries, (index, 0), ordered[index])

        captured = Closure(
            EntityID("owner"), EntityID("body"), (),
            (("large", tuple(range(4096))),),
        )
        self.assert_inspection(captured)
        self.assert_invalid_selection(captured, ("captures",))

    def assert_machine_result_controls(
        self, operation, arguments, control_arguments,
    ):
        """Require result dependence or explicitly identified rejection.

        The alternative is observed independently on a different valid
        input. A rejection identifies both the operation and the exact
        injected VM output. Independent source-path audit remains mandatory.
        """
        method = getattr(self.candidate, operation)
        baseline = self.execute(operation, *arguments)
        alternative = self.execute(operation, *control_arguments)

        self.assertNotEqual(
            canonical_bytes(baseline),
            canonical_bytes(alternative),
            "control output does not distinguish the baseline",
        )

        for inputs, expected in (
            (arguments, baseline),
            (control_arguments, alternative),
        ):
            with candidate_execution_guard(
                self.entries, forced=expected,
            ) as opened:
                actual = method(*inputs)

            self.assertTrue(opened)
            self.assertEqual(
                canonical_bytes(actual),
                canonical_bytes(expected),
            )

        rejected = None
        with candidate_execution_guard(
            self.entries, forced=alternative,
        ) as opened:
            try:
                actual = method(*arguments)
            except (ValueError, TypeError, AdmissionRejected) as exc:
                rejected = exc

        self.assertTrue(
            opened, f"{operation}: no admitted evaluator execution",
        )

        if rejected is None:
            self.assertEqual(
                canonical_bytes(actual),
                canonical_bytes(alternative),
                f"{operation}: ignored controlled VM output",
            )
            return

        self.assertEqual(
            getattr(rejected, "projection_operation", None),
            operation,
            "rejection lacks projection-operation provenance",
        )
        self.assertTrue(
            hasattr(rejected, "rejected_vm_output"),
            "rejection lacks VM-output provenance",
        )
        self.assertEqual(
            canonical_bytes(rejected.rejected_vm_output),
            canonical_bytes(alternative),
            "rejection does not identify the injected VM output",
        )
        self.assertTrue(
            str(rejected).strip(),
            "projection rejection lacks a reason",
        )

    def test_selection_depends_on_valid_machine_output(self):
        value = {"a": [1, 2], "b": {"c": True}}
        self.assert_selection(value, (1, 0), "b")
        self.assert_machine_result_controls(
            "select_projection",
            (value, (1, 0)),
            ({"a": [1, 2], "c": {"d": True}}, (1, 0)),
        )

    def test_inspection_depends_on_valid_machine_output(self):
        self.assert_machine_result_controls(
            "inspect_projection",
            ({"a": [1, 2], "b": {"c": True}},),
            ({"a": [1, 2]},),
        )
        self.assert_machine_result_controls(
            "inspect_projection",
            ((1, 2, 3),),
            ((1, 2),),
        )

    def test_equality_depends_on_valid_machine_output(self):
        left = {"a": 1, "b": 2}
        reordered = {"b": 2, "a": 1}
        different = {"a": 1, "b": 3}

        self.assert_machine_result_controls(
            "equal_projection",
            (left, reordered),
            (left, different),
        )
        self.assert_machine_result_controls(
            "equal_projection",
            (left, different),
            (left, reordered),
        )


if __name__ == "__main__":
    unittest.main()
