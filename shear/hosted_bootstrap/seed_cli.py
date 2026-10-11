"""Command line of the seed manifest: ``python3 -m shear.hosted_bootstrap.seed_cli``
checks it, and ``--write`` regenerates it. Nothing imports this module."""

import sys

from .seed import main

raise SystemExit(main(sys.argv[1:]))
