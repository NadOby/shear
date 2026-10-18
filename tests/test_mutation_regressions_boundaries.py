"""Mutation regressions for semantic boundary contracts found by the final campaign."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import unittest
from unittest import mock

from shear import (
    CellDeclaration,
    EntityID,
    External,
    IsKind,
    Runtime,
    State,
    Value,
    canonical_serialize,
)
from shear import machine
from shear.examples._support import program
from shear.fold import fold_constants, sources_of
from shear.hosted_bootstrap import AdmissionRejected
from shear.hosted_bootstrap.restricted import (
    RESTRICTED_FAILURE,
    RestrictedExecutor,
)
from shear.lang import (
    Function,
    LanguageError,
    _definition_of,
    function_of,
    links,
    load,
    run,
)
from shear.relations import relation_of
from shear.syntax import SourceError, parse, render
from tests.test_restricted_execution import (
    PRED,
    PURE_POLICY,
    RAISE,
    evaluator_source,
)


F = EntityID("f")
TARGET = EntityID("target")
OTHER = EntityID("other")
CELL = EntityID("counter")


def language_state_of(body: tuple) -> State:
    return load(
        State.create({
            F: Value.create(
                F,
                Function((), body),
            ),
        })
    )


def rendered(body: tuple, params: tuple[str, ...] = ()) -> str:
    state = load(program({
        F: Function(params, body),
        TARGET: Function((), ("lit", 0)),
        OTHER: Function((), ("lit", 1)),
        CELL: CellDeclaration(IsKind("int"), 0),
        EntityID("f.links"): links(F, a=TARGET, b=OTHER, c=CELL),
    }))
    return render(state, F)


class LanguageBoundaryMutationRegressions(unittest.TestCase):
    def test_function_record_is_immutable(self) -> None:
        function = Function(
            ("x",),
            ("arg", "x"),
        )
        serialized = canonical_serialize(function)
        hashed = hash(function)

        with self.assertRaises(FrozenInstanceError):
            function.body = ("lit", 1)

        self.assertEqual(canonical_serialize(function), serialized)
        self.assertEqual(hash(function), hashed)

    def test_truthy_unhashable_capture_name_raises_language_error(self) -> None:
        body = (
            "closure",
            (),
            ([1],),
            ("lit", 1),
        )

        with self.assertRaises(LanguageError):
            run(Runtime(language_state_of(body)), F)

    def test_malformed_input_forms_remain_language_errors(self) -> None:
        cases = (
            (("call",), "call needs a link"),
            (("ref", "missing"), "unknown link 'missing'"),
            (("apply",), "apply needs a function"),
            (("trial",), "trial needs a call form"),
        )

        for body, message in cases:
            with self.subTest(body=body):
                with self.assertRaises(LanguageError) as caught:
                    run(Runtime(language_state_of(body)), F)

                self.assertIn(message, str(caught.exception))


class FoldMappingMutationRegressions(unittest.TestCase):
    def test_constant_if_maps_into_unfolded_selected_branch(self) -> None:
        state = load(
            State.create({
                F: Value.create(
                    F,
                    Function(
                        ("x",),
                        (
                            "if",
                            ("lit", True),
                            ("arg", "x"),
                            ("lit", 0),
                        ),
                    ),
                ),
            })
        )
        source_root = _definition_of(state.values[F]).body
        source_if = relation_of(state.values[source_root])

        self.assertIsNotNone(source_if)
        assert source_if is not None
        selected = source_if.roles["then"]
        condition = source_if.roles["cond"]

        result = fold_constants(state)
        destination_root = _definition_of(
            result.destination.values[F]
        ).body

        self.assertEqual(destination_root, selected)
        self.assertEqual(
            set(sources_of(result, destination_root)),
            {
                source_root,
                condition,
                selected,
            },
        )


class SyntaxParserBoundaryMutationRegressions(unittest.TestCase):
    def test_unicode_name_escape_is_validated_and_hexadecimal(self) -> None:
        state = parse(
            "fn `\\u0041`():\n"
            "    1\n"
        )
        self.assertIn(EntityID("A"), state.values)

        high_digit = parse(
            "fn `\\u1234`():\n"
            "    1\n"
        )
        self.assertIn(
            EntityID("\u1234"),
            high_digit.values,
        )

        with self.assertRaises(SourceError):
            parse(
                "fn `\\u0x00`():\n"
                "    1\n"
            )

    def test_raw_unknown_link_does_not_create_dangling_link(self) -> None:
        state = parse(
            "fn f():\n"
            '    raw(("call", "missing"))\n'
        )
        function = function_of(state.values[F])

        self.assertIsNotNone(function)
        assert function is not None
        self.assertEqual(function.body, ("call", "missing"))
        self.assertNotIn(EntityID("f.links"), state.values)

    def test_parse_over_base_preserves_live_ownership(self) -> None:
        owner = EntityID("owner")
        child = EntityID("child")
        base = State.create(
            parse(
                "fn owner():\n"
                "    1\n"
                "\n"
                "fn child():\n"
                "    2\n"
            ).values,
            {owner: (child,)},
        )

        result = parse(
            "fn extra():\n"
            "    3\n",
            base=base,
        )

        self.assertEqual(
            result.owned_children(owner),
            (child,),
        )


class SyntaxRawMappingMutationRegressions(unittest.TestCase):
    def test_raw_mapping_boundary_cases(self) -> None:
        cases = (
            (
                ("activate", (), ("lit", 1)),
                ('raw(("activate", (), ("lit", 1)))',),
                (),
            ),
            (
                ("activate", 7, ("lit", 1)),
                ('raw(("activate", 7, ("lit", 1)))',),
                (),
            ),
            (
                ("activate", ("a", 7), ("lit", 1)),
                ('("target", 7)',),
                ('("a", 7)',),
            ),
            (
                ("frobnicate", ("lit", ("call", "a"))),
                ('("lit", ("call", "a"))',),
                ('("lit", ("call", "target"))',),
            ),
            (
                ("trial",),
                ('raw(("trial",))',),
                (),
            ),
            (
                (
                    "activate",
                    7,
                    ("lit", 0),
                    "a",
                    ("lit", 1),
                    "b",
                    ("lit", 2),
                ),
                ('"target"', '"other"'),
                ('"a"', '"b"'),
            ),
            (
                (
                    "trial",
                    ("lit", 0),
                    "a",
                    ("lit", 1),
                    "b",
                    ("lit", 2),
                    "c",
                    ("lit", 3),
                ),
                ('"target"', '"other"', '"counter"'),
                ('"a"', '"b"', '"c"'),
            ),
        )

        for body, present, absent in cases:
            with self.subTest(body=body):
                text = rendered(body)

                for fragment in present:
                    self.assertIn(fragment, text)

                for fragment in absent:
                    self.assertNotIn(fragment, text)

    def test_raw_let_keeps_binding_metadata_out_of_link_mapping(self) -> None:
        text = rendered(
            (
                "let",
                ("call", "a"),
                ("call", "a"),
                ("call", "a"),
            )
        )

        self.assertIn(
            'raw(("let", ("call", "a"), '
            '("call", "target"), ("call", "target")))',
            text,
        )

    def test_raw_closure_keeps_metadata_and_maps_only_body_links(
        self,
    ) -> None:
        text = rendered(
            (
                "quote",
                (
                    "closure",
                    ("p",),
                    (("call", "a"),),
                    ("label", "k", ("call", "a")),
                ),
            )
        )

        self.assertIn('("p",)', text)
        self.assertIn('(("call", "a"),)', text)
        self.assertIn('("label", "k", ("call", "target"))', text)

    def test_raw_unsupported_leaf_stays_a_visible_leaf(self) -> None:
        text = rendered(("frobnicate", EntityID("opaque")))

        self.assertIn('raw(("frobnicate", <', text)


class SyntaxRendererBoundaryMutationRegressions(unittest.TestCase):
    def test_malformed_forms_render_without_widening_raw_fallback(
        self,
    ) -> None:
        cases = (
            (
                ("seq", 1),
                (),
                "raw(1)",
            ),
            (
                ("let", 7, ("lit", 1), ("lit", 2)),
                (),
                'raw(("let", 7, ("lit", 1), ("lit", 2)))',
            ),
            (
                (
                    "if",
                    ("seq", ("lit", 1), ("lit", 2)),
                    ("lit", 3),
                    ("lit", 4),
                ),
                (),
                'if raw(("seq", ("lit", 1), ("lit", 2))):',
            ),
            (
                ("write", "c", ("seq", ("lit", 1), ("lit", 2))),
                (),
                'counter = raw(("seq", ("lit", 1), ("lit", 2)))',
            ),
            (
                ("let", "x", ("seq", ("lit", 1), ("lit", 2)), ("arg", "x")),
                (),
                'let x = raw(("seq", ("lit", 1), ("lit", 2)))',
            ),
            (
                (
                    "let",
                    "x",
                    ("write", "c", ("seq", ("lit", 1), ("lit", 2))),
                    ("arg", "x"),
                ),
                (),
                'let x = counter = raw(("seq", ("lit", 1), ("lit", 2)))',
            ),
            (
                ("apply", 1, ("lit", 2)),
                (),
                'apply(raw(1), (2,))',
            ),
            (
                ("apply", ("arg", ""), ("lit", 1)),
                (),
                'apply(raw(("arg", "")), (1,))',
            ),
            (
                ("label", "k", ()),
                (),
                "label(k, raw(()))",
            ),
            (
                (
                    "quote",
                    (
                        "lit",
                        (
                            "unquote",
                            ("seq", ("lit", 1), ("lit", 2)),
                        ),
                    ),
                ),
                (),
                'literal(raw(("seq", ("lit", 1), ("lit", 2))))',
            ),
            (
                ("closure", (7,), (), ("lit", 1)),
                (),
                'raw(("closure"',
            ),
            (
                ("closure", (), (7,), ("lit", 1)),
                (),
                'raw(("closure"',
            ),
            (
                ("closure", (), (), ("seq", ("lit", 1), ("lit", 2))),
                (),
                'raw(("closure", (), (), ("seq",',
            ),
        )

        for body, params, expected in cases:
            with self.subTest(body=body):
                self.assertIn(expected, rendered(body, params))

    def test_truthy_unhashable_closure_capture_renders_raw(self) -> None:
        text = rendered(
            (
                "closure",
                (),
                ([1],),
                ("lit", 1),
            )
        )

        self.assertIn('raw(("closure"', text)
        self.assertIn("<[1]>", text)

    def test_unquote_keeps_raw_fallback_at_inner_expression(self) -> None:
        text = rendered(
            (
                "quote",
                (
                    "unquote",
                    ("seq", ("lit", 1), ("lit", 2)),
                ),
            )
        )

        self.assertIn(
            'quote(unquote(raw(("seq",',
            text,
        )
        self.assertNotIn(
            'raw(("quote"',
            text,
        )

    def test_let_forms_use_current_link_targets(self) -> None:
        cases = (
            (
                ("let", "x", ("call", "a"), ("arg", "x")),
                "let x = target()",
            ),
            (
                (
                    "let",
                    "x",
                    ("write", "c", ("call", "a")),
                    ("arg", "x"),
                ),
                "let x = counter = target()",
            ),
            (
                ("closure", (), (), ("call", "a")),
                "closure() captures(): target()",
            ),
        )

        for body, expected in cases:
            with self.subTest(body=body):
                self.assertIn(expected, rendered(body))

    def test_literal_unquote_uses_current_link_target(self) -> None:
        text = rendered(
            (
                "quote",
                (
                    "lit",
                    (
                        "unquote",
                        ("call", "a"),
                    ),
                ),
            )
        )

        self.assertIn("literal(target())", text)

    def test_trial_and_activate_local_collisions_render_raw(self) -> None:
        cases = (
            (
                ("trial", ("call", "a")),
                'raw(("trial", ("call", "target")))',
            ),
            (
                ("activate", "a", ("lit", 1)),
                'raw(("activate", "target", ("lit", 1)))',
            ),
        )

        for body, expected in cases:
            with self.subTest(body=body):
                self.assertIn(
                    expected,
                    rendered(body, params=("target",)),
                )

    def test_malformed_function_values_use_generic_form(self) -> None:
        bodies = (
            (
                "function",
                ("lit", (7,)),
                ("quote", ("lit", 1)),
            ),
            (
                "function",
                ("lit", ("x",)),
                7,
            ),
            (
                "function",
                ("lit", ("x",)),
                ("bad", ("lit", 1)),
            ),
            (
                "function",
                ("lit", ("x",)),
                ("quote", ("seq", ("lit", 1), ("lit", 2))),
            ),
        )

        for body in bodies:
            with self.subTest(body=body):
                self.assertIn("function(", rendered(body))


class RestrictedExecutionMutationRegressions(unittest.TestCase):
    """Independent regressions for Task 32 Execute Review findings."""

    def setUp(self) -> None:
        self.source = evaluator_source()
        self.executor = RestrictedExecutor()
        self.deployment = self.executor.deploy(
            self.source, compiler_generation=1,
        )

    def test_failed_write_preserves_evaluator_operation_provenance(
        self,
    ) -> None:
        target_state = State.create({
            CELL: Value.create(
                CELL, CellDeclaration(External("policy"), 3),
            ),
        })
        registry = self.executor.registry({
            "policy": (self.deployment, PRED),
        })
        runtime = Runtime(target_state, registry.context)
        registry.replace("policy", (self.deployment, RAISE))

        before_cells = dict(runtime.active.cells)
        before_id = runtime.active.id
        before_events = len(self.executor.trace())

        root = _definition_of(self.source.values[RAISE]).body
        artifact = self.deployment.artifacts[
            (root, self.source.values[root].version_id)
        ]
        opened = []
        real_open = machine._open

        def observe(activation, args, *rest, **kwargs):
            if activation.entity == RAISE:
                opened.append(activation.hold.version.state.id)
            return real_open(activation, args, *rest, **kwargs)

        with mock.patch.object(machine, "_open", side_effect=observe):
            with self.assertRaises(LanguageError) as cm:
                runtime.write(CELL, 4)

        self.assertEqual(opened, [self.source.id])
        self.assertEqual(
            cm.exception.error[:3],
            ("program", "evaluator_failure", "probe"),
        )
        self.assertEqual(runtime.active.id, before_id)
        self.assertEqual(dict(runtime.active.cells), before_cells)

        events = self.executor.trace()[before_events:]
        failures = [
            event for event in events
            if event.kind == RESTRICTED_FAILURE
            and event.entity == RAISE
            and event.target_state_id == target_state.id
        ]
        self.assertEqual(len(failures), 1)
        failure = failures[0]
        self.assertEqual(failure.version, artifact.version)
        self.assertEqual(failure.artifact_id, artifact.artifact_id)
        self.assertEqual(failure.compiler_generation, 1)
        self.assertIn("write: External(policy)", failure.detail)
        self.assertIn(
            f"evaluator_source={self.source.id.value}",
            failure.detail,
        )
        self.assertIn(
            "outcome=failure:LanguageError",
            failure.detail,
        )
        self.assertFalse(any(
            event.kind == "execute"
            and event.target_state_id == target_state.id
            for event in events
        ))

    def test_copied_deployment_has_no_execution_authority(self) -> None:
        copied = replace(self.deployment)
        self.assertIsNot(copied, self.deployment)
        self.assertIs(copied.artifacts, self.deployment.artifacts)

        with self.assertRaises(AdmissionRejected):
            self.executor.run(
                copied, PRED, 3, policy=PURE_POLICY,
            )

        with self.assertRaises(AdmissionRejected):
            self.executor.registry({"policy": (copied, PRED)})

        registry = self.executor.registry({
            "policy": (self.deployment, PRED),
        })
        with self.assertRaises(AdmissionRejected):
            registry.replace("policy", (copied, PRED))

        self.assertEqual(
            self.executor.run(
                self.deployment, PRED, 3, policy=PURE_POLICY,
            ),
            "satisfied",
        )
        accepted = Runtime(State.create({
            CELL: Value.create(
                CELL, CellDeclaration(External("policy"), 3),
            ),
        }), registry.context)
        self.assertEqual(accepted.read(CELL), 3)


if __name__ == "__main__":
    unittest.main()
