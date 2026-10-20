"""Frozen T4 external evaluator acceptance for SHEAR issue #123.

Execute supplies:
    evaluate_external(name, subject, budget, callback=None)
        -> Observation

The callback is a named external evaluator receiving canonical
subject content and returning ConstraintResult.

The ordinary SHEAR evaluator must execute authenticated bytecode
before external dispatch. Dispatch itself may cross a host boundary;
Task 32 does not provide an in-VM Python callback instruction.

Host exceptions must escape unchanged. The callback must not run
when admitted evaluator execution fails before dispatch.

Outside ordinary CI discovery until Execute.
"""

from importlib import import_module
from pathlib import Path
import subprocess
import sys
import unittest

from shear import ConstraintResult, canonicalize
from tests.constraint_function_acceptance import Observation
from tests.constraint_functions_complete_acceptance import (
    EvaluatorMachineFault,
    candidate_execution_guard,
    forbid_incumbent,
)


SAT = ConstraintResult.SATISFIED
VIO = ConstraintResult.VIOLATED
UNK = ConstraintResult.UNKNOWN


class ProbeHostFault(RuntimeError):
    pass


CHILD_SCRIPT = """
from importlib import import_module
from threading import Event
from unittest.mock import patch

from shear import canonicalize, machine
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from tests.constraint_functions_complete_acceptance import forbid_incumbent

with forbid_incumbent():
    adapter = import_module("tests.constraint_functions_complete_candidate")

real_run = RestrictedExecutor.run
real_open = machine._open
active = []
opened = []

def traced_run(executor, deployment, entry, *args, **kwargs):
    active.append((deployment, entry))
    try:
        return real_run(executor, deployment, entry, *args, **kwargs)
    finally:
        active.pop()

def traced_open(activation, args, *rest, **kwargs):
    chunk, env, node = real_open(activation, args, *rest, **kwargs)
    if active:
        deployment, _ = active[-1]
        state = deployment._target.state
        assert activation.hold.version.state.id == state.id
        key = (node, state.values[node].version_id)
        artifact = deployment.artifacts[key]
        assert chunk is artifact.chunk
        artifact.verify()
        assert artifact.state_id == state.id
        assert artifact.entity == node
        assert artifact.version == key[1]
        assert artifact.owner == activation.entity
        assert artifact.produced_by == deployment.compiler_generation

        if activation.entity in adapter.EVALUATOR_ENTRIES:
            opened.append((activation.entity, node))
            print("ADMITTED_EVALUATOR_OPENED", flush=True)

    return chunk, env, node

expected = canonicalize({"payload": [1, True]})

def blocked(subject):
    assert opened, "external invoked before admitted evaluator entry"
    assert subject == expected, "external subject was not canonical"
    print("EXTERNAL_CALLBACK_ENTERED", flush=True)
    Event().wait()
    raise AssertionError("unreachable")

with (
    forbid_incumbent(),
    patch.object(RestrictedExecutor, "run", new=traced_run),
    patch.object(machine, "_open", new=traced_open),
):
    adapter.evaluate_external(
        "blocking", {"payload": [1, True]}, 1, blocked,
    )

raise AssertionError("nonterminating evaluator unexpectedly returned")
"""


class FrozenExternalAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with forbid_incumbent():
            cls.adapter = import_module(
                "tests.constraint_functions_complete_candidate"
            )
        cls.entries = cls.adapter.EVALUATOR_ENTRIES
        if not callable(
            getattr(cls.adapter, "evaluate_external", None)
        ):
            raise AssertionError(
                "candidate lacks evaluate_external"
            )

    def evaluate(self, name, subject, budget, callback=None):
        with candidate_execution_guard(self.entries) as opened:
            result = self.adapter.evaluate_external(
                name, subject, budget, callback,
            )
        self.assertTrue(opened, "external evaluation bypassed SHEAR")
        self.assertIsInstance(result, Observation)
        self.assertEqual(result.incumbent_calls, 0)
        return result.outcome

    def test_missing_external(self):
        for subject in (0, True, {"a": [1, 2]}):
            with self.subTest(subject=repr(subject)):
                self.assertEqual(
                    self.evaluate("missing", subject, 1),
                    "unknown",
                )

    def test_budget_zero_never_invokes_external(self):
        calls = []

        def callback(subject):
            calls.append(subject)
            return SAT

        self.assertEqual(
            self.evaluate("policy", [1, 2], 0, callback),
            "unknown",
        )
        self.assertEqual(calls, [])

    def test_all_three_external_results(self):
        subject = {"root": [1, True]}

        for verdict in (SAT, VIO, UNK):
            with self.subTest(verdict=verdict):
                calls = []

                def callback(actual):
                    calls.append(actual)
                    return verdict

                outcome = self.evaluate(
                    "policy", subject, 1, callback,
                )
                self.assertEqual(outcome, verdict.value)
                self.assertEqual(calls, [canonicalize(subject)])

    def test_callback_receives_canonical_subject(self):
        subjects = (
            b"\x00\xff",
            ("a", True, 1),
            {"b": 2, "a": [True, 1]},
        )

        for subject in subjects:
            with self.subTest(subject=repr(subject)):
                received = []

                def callback(actual):
                    received.append(actual)
                    return SAT

                self.assertEqual(
                    self.evaluate("capture", subject, 1, callback),
                    "satisfied",
                )
                self.assertEqual(received, [canonicalize(subject)])

    def test_host_failure_escapes_unchanged(self):
        error = ProbeHostFault("external failure")
        received = []

        def callback(subject):
            received.append(subject)
            raise error

        with candidate_execution_guard(self.entries) as opened:
            with self.assertRaises(ProbeHostFault) as caught:
                self.adapter.evaluate_external(
                    "fault", {"x": 3}, 1, callback,
                )

        self.assertTrue(opened, "host fault bypassed evaluator")
        self.assertIs(caught.exception, error)
        self.assertEqual(received, [canonicalize({"x": 3})])

    def test_vm_fault_prevents_external_dispatch(self):
        calls = []

        def callback(subject):
            calls.append(subject)
            return SAT

        with candidate_execution_guard(
            self.entries, fault=True,
        ) as opened:
            with self.assertRaises(EvaluatorMachineFault):
                self.adapter.evaluate_external(
                    "policy", 5, 1, callback,
                )

        self.assertTrue(opened, "VM fault was never injected")
        self.assertEqual(
            calls, [],
            "external callback ran despite evaluator VM fault",
        )

    def test_nonterminating_external_is_isolated(self):
        root = Path(__file__).resolve().parent.parent

        process = subprocess.Popen(
            [sys.executable, "-u", "-c", CHILD_SCRIPT],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            stdout, stderr = process.communicate(timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

        self.assertTrue(
            timed_out,
            f"external did not remain blocked: {stdout}\n{stderr}",
        )
        self.assertIn(
            "ADMITTED_EVALUATOR_OPENED", stdout,
            f"no admitted execution observed:\n{stderr}",
        )
        self.assertIn(
            "EXTERNAL_CALLBACK_ENTERED", stdout,
            f"external callback was not entered:\n{stderr}",
        )
        self.assertLess(
            stdout.index("ADMITTED_EVALUATOR_OPENED"),
            stdout.index("EXTERNAL_CALLBACK_ENTERED"),
            "external callback preceded admitted execution",
        )


if __name__ == "__main__":
    unittest.main()
