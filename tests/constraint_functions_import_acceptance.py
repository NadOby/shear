"""Fresh-process candidate import acceptance for SHEAR #123.

The candidate must be imported under incumbent-evaluator poisoning in
a newly started Python interpreter, independent of module caching.

Execute registers this module after supplying the real candidate.
It is deliberately outside ordinary Plan-time test discovery.
"""

from pathlib import Path
import subprocess
import sys
import unittest


CANDIDATE = "tests.constraint_functions_complete_candidate"

FRESH_IMPORT = """
import sys
from importlib import import_module

from tests.constraint_functions_complete_acceptance import forbid_incumbent

name = "tests.constraint_functions_complete_candidate"
assert name not in sys.modules, "candidate was loaded before poisoning"

with forbid_incumbent():
    candidate = import_module(name)

assert sys.modules[name] is candidate
assert callable(getattr(candidate, "semantic", None))
assert callable(getattr(candidate, "boundary", None))
print("FRESH_IMPORT_VERIFIED")
"""


class CandidateFreshImportAcceptance(unittest.TestCase):
    def test_import_under_poisoning_in_fresh_process(self):
        root = Path(__file__).resolve().parent.parent

        result = subprocess.run(
            [sys.executable, "-c", FRESH_IMPORT],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        self.assertEqual(
            result.returncode,
            0,
            "Fresh candidate import failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}",
        )
        self.assertEqual(
            result.stdout.strip(),
            "FRESH_IMPORT_VERIFIED",
        )


if __name__ == "__main__":
    unittest.main()
