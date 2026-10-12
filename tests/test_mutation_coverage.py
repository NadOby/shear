"""The coverage map that orders mutant runs and the coverage diagnostic."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from tests import mutation, mutation_coverage as coverage


CALC = textwrap.dedent('''\
    def used(n):
        return n + 1


    def unused(n):
        return n - 1
''')

TESTS = {
    "t_plain": '''\
        import unittest
        import calc


        class T(unittest.TestCase):
            def test_used(self):
                self.assertEqual(calc.used(1), 2)
    ''',
    "t_spawning": '''\
        import subprocess
        import sys
        import unittest


        class T(unittest.TestCase):
            def test_child(self):
                subprocess.run([sys.executable, "-c", "pass"], check=True)
    ''',
    "t_failing": '''\
        import unittest
        import calc


        class T(unittest.TestCase):
            def test_used(self):
                calc.used(1)
                self.fail("always")
    ''',
}

# Runs trace_module in its own process, because it applies the oracle's
# address-space cap and installs a tracer, neither of which belongs in the
# test runner.
RUNNER = '''\
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[3])

from tests import mutation_coverage as coverage

value = coverage.trace_module(Path(sys.argv[1]), sys.argv[2], ("calc.py",))
print(json.dumps(value))
'''


def synthetic(
    **modules: coverage.ModuleCoverage,
) -> coverage.CoverageMap:
    return coverage.CoverageMap("f", tuple(modules), dict(modules))


def seen(
    *lines: int,
    complete: bool = True,
    opaque: bool = False,
) -> coverage.ModuleCoverage:
    return coverage.ModuleCoverage(
        complete,
        opaque,
        1.0,
        {"calc.py": frozenset(lines)},
    )


class OrderingTests(unittest.TestCase):
    def test_covering_modules_come_first_in_oracle_order(self) -> None:
        coverage_map = synthetic(a=seen(1), b=seen(2), c=seen(2))

        self.assertEqual(coverage_map.covering("calc.py", 2), ("b", "c"))
        self.assertEqual(coverage_map.first("calc.py", 2), ("b", "c"))

    def test_a_module_that_may_reach_the_line_follows_the_covering_ones(
        self,
    ) -> None:
        coverage_map = synthetic(
            a=seen(1, opaque=True),
            b=seen(2),
            c=seen(1, complete=False),
        )

        self.assertEqual(
            coverage_map.first("calc.py", 2),
            ("b", "a", "c"),
        )

    def test_a_module_missing_from_the_map_counts_as_uncertain(self) -> None:
        coverage_map = coverage.CoverageMap(
            "f",
            ("a", "b"),
            {"a": seen(2)},
        )

        self.assertEqual(coverage_map.first("calc.py", 2), ("a", "b"))
        self.assertEqual(coverage_map.first("calc.py", 9), ("b",))

    def test_a_line_nothing_executes_is_uncovered_only_when_certain(
        self,
    ) -> None:
        certain = synthetic(a=seen(1))
        doubtful = synthetic(a=seen(1), b=seen(1, opaque=True))

        self.assertEqual(certain.status("calc.py", 9), coverage.UNCOVERED)
        self.assertEqual(
            doubtful.status("calc.py", 9),
            coverage.SUBPROCESS_ONLY,
        )
        self.assertEqual(certain.status("calc.py", 1), coverage.COVERED)

    def test_ordering_never_drops_a_module(self) -> None:
        # Only the order of a fail-fast run may change, never its content.
        coverage_map = synthetic(
            a=seen(1),
            b=seen(2, opaque=True),
            c=seen(3),
        )
        rest = [
            module
            for module in coverage_map.order
            if module not in coverage_map.first("calc.py", 3)
        ]

        self.assertEqual(
            sorted(coverage_map.first("calc.py", 3) + tuple(rest)),
            ["a", "b", "c"],
        )


class TracingTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        (self.root / "calc.py").write_text(CALC)

        for name, body in TESTS.items():
            (self.root / f"{name}.py").write_text(textwrap.dedent(body))

        (self.root / "runner.py").write_text(RUNNER)

    def trace(self, module: str) -> dict[str, object]:
        repository = str(Path(__file__).resolve().parent.parent)
        done = subprocess.run(
            [
                sys.executable,
                str(self.root / "runner.py"),
                str(self.root),
                module,
                repository,
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stderr)

        return json.loads(done.stdout.strip().splitlines()[-1])

    @unittest.skipUnless(
        hasattr(sys, "monitoring"),
        "needs sys.monitoring",
    )
    def test_only_the_lines_a_module_executes_are_recorded(self) -> None:
        value = self.trace("t_plain")

        self.assertTrue(value["complete"])
        self.assertFalse(value["opaque"])
        # `used` runs (def line and its body); `unused` body never does.
        self.assertIn(2, value["lines"]["calc.py"])
        self.assertNotIn(6, value["lines"]["calc.py"])

    @unittest.skipUnless(
        hasattr(sys, "monitoring"),
        "needs sys.monitoring",
    )
    def test_starting_a_process_makes_a_module_opaque(self) -> None:
        value = self.trace("t_spawning")

        self.assertTrue(value["complete"])
        self.assertTrue(value["opaque"])

    @unittest.skipUnless(
        hasattr(sys, "monitoring"),
        "needs sys.monitoring",
    )
    def test_a_failing_module_is_incomplete(self) -> None:
        value = self.trace("t_failing")

        self.assertFalse(value["complete"])
        self.assertIn(2, value["lines"]["calc.py"])


class ReportTests(unittest.TestCase):
    def test_executable_lines_include_nested_bodies_only(self) -> None:
        self.assertEqual(
            coverage.executable_lines(CALC, "calc.py"),
            frozenset({1, 2, 5, 6}),
        )

    def test_ranges_join_adjacent_lines(self) -> None:
        self.assertEqual(coverage._ranges([1, 2, 3, 7, 9, 10]), "1-3, 7, 9-10")
        self.assertEqual(coverage._ranges([]), "")

    def test_the_report_lists_lines_no_module_executes(self) -> None:
        target = next(iter(mutation_targets()))
        root = mutation.ROOT
        source_lines = coverage.executable_lines(
            (root / target).read_text(),
            target,
        )
        first = min(source_lines)
        coverage_map = coverage.CoverageMap(
            "f",
            ("a",),
            {"a": coverage.ModuleCoverage(
                True,
                False,
                1.0,
                {target: frozenset(source_lines - {first})},
            )},
        )

        result = coverage.report(coverage_map, root, (target,))

        entry = result["targets"][0]
        self.assertEqual(entry["target"], target)
        self.assertEqual(entry["unexecuted"], [first])
        self.assertEqual(entry["executed"], len(source_lines) - 1)
        self.assertEqual(result["uncertain_modules"], [])
        self.assertIn("not a gate", coverage.render(result))

    def test_prefixes_select_targets(self) -> None:
        coverage_map = coverage.CoverageMap("f", (), {})

        result = coverage.report(
            coverage_map,
            mutation.ROOT,
            ("shear/state",),
        )

        self.assertTrue(result["targets"])
        self.assertTrue(
            all(
                entry["target"].startswith("shear/state")
                for entry in result["targets"]
            )
        )


class LoadTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.path = Path(scratch.name) / "map.json"

    def current(self) -> coverage.CoverageMap:
        from tests import mutation_oracle

        order = mutation_oracle.modules()

        return coverage.CoverageMap(
            coverage.fingerprint(mutation.ROOT),
            order,
            {order[0]: seen(1)},
        )

    def test_a_map_for_this_tree_loads(self) -> None:
        coverage.dump(self.current(), self.path)

        loaded = coverage.load(self.path, mutation.ROOT)

        self.assertEqual(loaded.order, self.current().order)
        self.assertEqual(
            loaded.modules[loaded.order[0]].lines["calc.py"],
            frozenset({1}),
        )

    def test_a_map_for_another_tree_is_refused(self) -> None:
        stale = self.current()
        coverage.dump(
            coverage.CoverageMap("0" * 40, stale.order, stale.modules),
            self.path,
        )

        with self.assertRaisesRegex(ValueError, "stale"):
            coverage.load(self.path, mutation.ROOT)

    def test_a_map_for_other_oracle_modules_is_refused(self) -> None:
        current = self.current()
        coverage.dump(
            coverage.CoverageMap(
                current.fingerprint,
                current.order[:-1],
                current.modules,
            ),
            self.path,
        )

        with self.assertRaisesRegex(ValueError, "oracle modules"):
            coverage.load(self.path, mutation.ROOT)

    def test_malformed_maps_are_refused(self) -> None:
        for name, text in {
            "not json": "{broken",
            "no fields": "{}",
            "not an object": "[]",
            "wrong version": json.dumps({
                "version": 99,
                "fingerprint": "x",
                "order": [],
                "modules": {},
            }),
        }.items():
            with self.subTest(name):
                self.path.write_text(text)

                with self.assertRaises(ValueError):
                    coverage.load(self.path, mutation.ROOT)

    def test_a_missing_map_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            coverage.load(self.path, mutation.ROOT)

    def test_the_fingerprint_follows_file_contents(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)

            for directory in ("shear", "tests"):
                (root / directory).mkdir()
                (root / directory / "x.py").write_text("a = 1\n")

            before = coverage.fingerprint(root)
            self.assertEqual(before, coverage.fingerprint(root))

            (root / "tests" / "x.py").write_text("a = 2\n")
            changed = coverage.fingerprint(root)
            self.assertNotEqual(before, changed)

            (root / "tests" / "report.jsonl").write_text("{}\n")
            self.assertEqual(changed, coverage.fingerprint(root))


def mutation_targets() -> tuple[str, ...]:
    from tests.mutation_catalog import TARGETS

    return tuple(TARGETS)


if __name__ == "__main__":
    unittest.main()
