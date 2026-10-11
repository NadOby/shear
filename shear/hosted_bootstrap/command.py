"""The documented command (docs/hosted_pipeline.md section 8):

    python3 -m shear.hosted_bootstrap --source-file FILE --entry NAME \\
        --args-json JSON [--edited-source-file EDITED --edit-mode prepare]

Source text goes through host parsing and graph construction, the SHEAR
compiler and admission, and the entry runs on admitted artifacts. In edit
mode the edited text is reconciled against the original and the candidate is
run beside it; it is never activated. The result is one JSON document.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from ..canonical import CanonicalNode
from ..identity import EntityID
from ..lang import LanguageError, load
from ..runtime import Runtime
from ..syntax import parse
from .descriptors import _plain
from .errors import AdmissionRejected
from .session import HostedSession
from .trace import ADMITTED_HOST, EXECUTE


def _tuples(value: Any) -> Any:
    """JSON arrays are SHEAR tuples."""

    if isinstance(value, list):
        return tuple(_tuples(item) for item in value)

    return value


def _jsonable(value: Any) -> Any:
    if isinstance(value, CanonicalNode):
        value = _plain(value)

    if isinstance(value, EntityID):
        return value.value

    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]

    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m shear.hosted_bootstrap",
        description="Run a SHEAR program through the SHEAR compiler.",
    )
    parser.add_argument("--source-file", required=True, type=Path)
    parser.add_argument("--entry", required=True)
    parser.add_argument("--args-json", default="[]")
    parser.add_argument("--edited-source-file", type=Path)
    parser.add_argument("--edit-mode", choices=("prepare",))
    return parser


def main(argv: list[str] | None = None) -> int:
    options = _parser().parse_args(argv)

    if (options.edit_mode is None) != (options.edited_source_file is None):
        print(
            "--edit-mode and --edited-source-file go together",
            file=sys.stderr,
        )
        return 2

    entry = EntityID(options.entry)
    args = _tuples(json.loads(options.args_json))
    text = options.source_file.read_text(encoding="utf-8")
    runtime = Runtime(load(parse(text)))
    session = HostedSession(runtime)

    try:
        if options.edit_mode is None:
            session.prepare(compiler_generation=1)
            output: dict[str, Any] = {
                "result": _jsonable(session.run(entry, *args)),
                "base_state_id": runtime.active.state.id.value,
            }
        else:
            edited = options.edited_source_file.read_text(encoding="utf-8")
            staged = session.stage_edit(edited, entry, tuple(args))
            output = {
                "result": _jsonable(staged.result),
                "candidate_result": _jsonable(staged.candidate_result),
                "base_state_id": staged.base_state_id.value,
                "candidate_state_id": staged.candidate_state_id.value,
                "active_state_id": staged.active_state_id.value,
                "continuity": staged.continuity,
            }
    except (LanguageError, AdmissionRejected) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    output["route"] = ADMITTED_HOST
    output["executed_artifacts"] = [
        event.as_json()
        for event in session.trace()
        if event.kind == EXECUTE and event.route == ADMITTED_HOST
    ]
    print(json.dumps(output, indent=1, sort_keys=True))
    return 0
