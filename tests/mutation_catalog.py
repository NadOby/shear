"""Mutation targets and reviewed survivor classifications.

Mutation-target policy remains executable Python. Reviewed survivor data and
its version pins live under tests/mutation_catalog_data/ and are loaded
fail-closed from TOML.

Catalog paths mirror mutation targets:

    mutation_catalog_data/shear/lang.toml
        -> shear/lang.py

A target receives a TOML file only while it has reviewed survivors. The
manifest inventories those files so deleting a complete target catalog cannot
silently erase its classifications.
"""

from __future__ import annotations

from pathlib import Path
import re
import tomllib

from tests.mutation import MutationKey


EQUIVALENT = "equivalent"
UNSPECIFIED = "unspecified"

CLASSIFICATIONS = frozenset({
    EQUIVALENT,
    UNSPECIFIED,
})


# Production semantic implementation exercised by mutation campaigns.
#
# Examples are normally inputs/fixtures rather than implementation, but the
# embedded compiler and VM are independent implementations and therefore are
# deliberate mutation targets.
TARGETS = (
    "shear/bytecode.py",
    "shear/canonical.py",
    "shear/cells.py",
    "shear/closures.py",
    "shear/constraints.py",
    "shear/continuity.py",
    "shear/equality.py",
    "shear/errors.py",
    "shear/fold.py",
    "shear/identity.py",
    "shear/instructions.py",
    "shear/lang.py",
    "shear/machine.py",
    "shear/machine_calls.py",
    "shear/machine_errors.py",
    "shear/machine_runtime.py",
    "shear/machine_semantics.py",
    "shear/matching.py",
    "shear/operations.py",
    "shear/ownership.py",
    "shear/reconcile.py",
    "shear/references.py",
    "shear/relations.py",
    "shear/runtime.py",
    "shear/semantic_access.py",
    "shear/state.py",
    "shear/syntax/forms.py",
    "shear/syntax/lexer.py",
    "shear/syntax/parser.py",
    "shear/syntax/printer.py",
    "shear/transforms.py",
    "shear/values.py",
    # The seed manifest pins this file's exact semantic source, so every
    # mutant is killed by the manifest check before behaviour is exercised.
    # A kill here is not evidence that a behavioural test caught the change;
    # that evidence is tests/test_hosted_bootstrap.py's differential test.
    "shear/examples/compiler_source.py",
    "shear/examples/constraint_continuation.py",
    "shear/examples/constraint_evaluator.py",
    "shear/examples/self_hosting.py",
    "shear/examples/vm.py",
    "shear/examples/vm_bootstrap.py",
    "shear/hosted_bootstrap/artifacts.py",
    "shear/hosted_bootstrap/command.py",
    "shear/hosted_bootstrap/descriptors.py",
    "shear/hosted_bootstrap/generations.py",
    "shear/hosted_bootstrap/restricted.py",
    "shear/hosted_bootstrap/restricted_policy.py",
    "shear/hosted_bootstrap/seed.py",
    "shear/hosted_bootstrap/session.py",
    "shear/hosted_bootstrap/target.py",
    "shear/hosted_bootstrap/trace.py",
    "shear/hosted_bootstrap/validation.py",
)


# Python files intentionally not mutation targets. This makes omissions
# explicit rather than allowing new semantic modules to fall out of mutation
# coverage silently.
OMITTED = {
    "shear/syntax/__init__.py":
        "re-export surface of the syntax package; behaviour lives in its modules",
    "shear/__init__.py":
        "public re-export surface; semantic behaviour lives in its modules",
    "shear/hosted_bootstrap/__init__.py":
        "public re-export surface of the hosted pipeline; behaviour lives in its modules",
    "shear/hosted_bootstrap/__main__.py":
        "command-line entry shim that calls hosted_bootstrap.command.main",
    "shear/hosted_bootstrap/diagnostics.py":
        "diagnostic measurement harness (section 10); reports, asserts no contract",
    "shear/hosted_bootstrap/live_diagnostics.py":
        "live evolution measurement harness (live_evolution.md section 7); reports, asserts no contract",
    "shear/hosted_bootstrap/seed_cli.py":
        "command-line entry shim that calls hosted_bootstrap.seed.main; nothing imports it",
    "shear/hosted_bootstrap/errors.py":
        "exception classes only; no behaviour to mutate",
    "shear/examples/__init__.py":
        "example/corpus harness rather than a semantic implementation",
    "shear/examples/_support.py":
        "example construction helper rather than semantic implementation",
    "shear/examples/closures.py":
        "example program exercised through the corpus",
    "shear/examples/control.py":
        "example program exercised through the corpus",
    "shear/examples/data.py":
        "example program exercised through the corpus",
    "shear/examples/errors.py":
        "example program exercised through the corpus",
    "shear/examples/higher_order.py":
        "example program exercised through the corpus",
    "shear/examples/ledger.py":
        "example program exercised through the corpus",
    "shear/examples/missing.py":
        "wanted-feature corpus data rather than implementation",
    "shear/examples/recursion.py":
        "example program exercised through the corpus",
    "shear/examples/self_modification.py":
        "example program exercised through the corpus",
    "shear/examples/side_effects.py":
        "example program exercised through the corpus",
}


CATALOG_ROOT = Path(__file__).with_name(
    "mutation_catalog_data"
)
SCHEMA_VERSION = 1

_BLOB_RE = re.compile(r"[0-9a-f]{40}")


class CatalogError(ValueError):
    """The serialized mutation catalog is malformed or inconsistent."""


def _read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream)
    except FileNotFoundError as exc:
        raise CatalogError(
            f"missing mutation catalog file: {path}"
        ) from exc
    except tomllib.TOMLDecodeError as exc:
        raise CatalogError(
            f"invalid TOML in mutation catalog file {path}: {exc}"
        ) from exc


def _require_fields(
    data: dict,
    expected: set[str],
    context: str,
) -> None:
    actual = set(data)
    missing = expected - actual
    unexpected = actual - expected

    if not missing and not unexpected:
        return

    problems = []

    if missing:
        problems.append(
            "missing fields: " + ", ".join(sorted(missing))
        )

    if unexpected:
        problems.append(
            "unexpected fields: "
            + ", ".join(sorted(unexpected))
        )

    raise CatalogError(
        f"{context}: " + "; ".join(problems)
    )


def _require_string(
    data: dict,
    field: str,
    context: str,
) -> str:
    value = data[field]

    if not isinstance(value, str):
        raise CatalogError(
            f"{context}: {field} must be a string"
        )

    if not value.strip():
        raise CatalogError(
            f"{context}: {field} must not be empty"
        )

    return value


def _require_integer(
    data: dict,
    field: str,
    context: str,
) -> int:
    value = data[field]

    # bool is an int subclass, but is not a valid catalog integer.
    if type(value) is not int:
        raise CatalogError(
            f"{context}: {field} must be an integer"
        )

    return value


def _require_blob(
    data: dict,
    field: str,
    context: str,
) -> str:
    value = _require_string(
        data,
        field,
        context,
    )

    if _BLOB_RE.fullmatch(value) is None:
        raise CatalogError(
            f"{context}: {field} must be a lowercase "
            "40-character Git blob ID"
        )

    return value


def _require_string_list(
    data: dict,
    field: str,
    context: str,
) -> tuple[str, ...]:
    value = data[field]

    if not isinstance(value, list):
        raise CatalogError(
            f"{context}: {field}[{index}] must be an array of strings"
        )

    items = []

    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise CatalogError(
                f"{context}: {field}[{index}] must be a string"
            )

        if not item or item != item.strip():
            raise CatalogError(
                f"{context}: {field}[{index}] must be a "
                "non-empty stripped string"
            )

        items.append(item)

    if len(items) != len(set(items)):
        raise CatalogError(
            f"{context}: {field} contains duplicate entries"
        )

    if items != sorted(items):
        raise CatalogError(
            f"{context}: {field} must be sorted"
        )

    return tuple(items)


def _target_for(
    path: Path,
    root: Path,
) -> str:
    relative = path.relative_to(root)

    if (
        len(relative.parts) < 2
        or relative.parts[0] != "shear"
    ):
        raise CatalogError(
            f"{relative.as_posix()}: catalog data must mirror "
            "a target path below shear/"
        )

    target = relative.with_suffix(".py").as_posix()

    if target not in TARGETS:
        raise CatalogError(
            f"{relative.as_posix()}: derived target "
            f"{target!r} is not a mutation target"
        )

    return target


def _load_survivor(
    raw: object,
    target: str,
    index: int,
) -> tuple[
    MutationKey,
    tuple[str, str],
]:
    context = f"{target}: survivor {index}"

    if not isinstance(raw, dict):
        raise CatalogError(
            f"{context}: survivor must be a table"
        )

    _require_fields(
        raw,
        {
            "kind",
            "source",
            "occurrence",
            "classification",
            "reason",
        },
        context,
    )

    kind = _require_string(
        raw,
        "kind",
        context,
    )
    source = _require_string(
        raw,
        "source",
        context,
    )
    occurrence = _require_integer(
        raw,
        "occurrence",
        context,
    )
    classification = _require_string(
        raw,
        "classification",
        context,
    )
    reason = _require_string(
        raw,
        "reason",
        context,
    ).strip()

    if kind != kind.strip():
        raise CatalogError(
            f"{context}: kind must be stripped"
        )

    if source != source.strip():
        raise CatalogError(
            f"{context}: source must be a stripped source line"
        )

    if occurrence < 0:
        raise CatalogError(
            f"{context}: occurrence must be non-negative"
        )

    if classification not in CLASSIFICATIONS:
        raise CatalogError(
            f"{context}: unknown classification "
            f"{classification!r}"
        )

    key: MutationKey = (
        target,
        kind,
        source,
        occurrence,
    )

    return key, (
        classification,
        reason,
    )


def load_catalog(
    root: Path,
) -> tuple[
    str,
    dict[str, str],
    dict[MutationKey, tuple[str, str]],
]:
    """Load and structurally validate one mutation catalog tree."""

    root = Path(root)
    manifest_path = root / "manifest.toml"
    manifest = _read_toml(manifest_path)

    _require_fields(
        manifest,
        {
            "schema_version",
            "engine_blob",
            "catalog_targets",
        },
        "manifest",
    )

    schema_version = _require_integer(
        manifest,
        "schema_version",
        "manifest",
    )

    if schema_version != SCHEMA_VERSION:
        raise CatalogError(
            "manifest: unsupported schema_version "
            f"{schema_version}; expected {SCHEMA_VERSION}"
        )

    engine_blob = _require_blob(
        manifest,
        "engine_blob",
        "manifest",
    )

    catalog_targets = _require_string_list(
        manifest,
        "catalog_targets",
        "manifest",
    )

    unknown_targets = (
        set(catalog_targets)
        - set(TARGETS)
    )

    if unknown_targets:
        raise CatalogError(
            "manifest: catalog_targets contains non-targets: "
            + ", ".join(sorted(unknown_targets))
        )

    source_blobs: dict[str, str] = {}
    survivors: dict[
        MutationKey,
        tuple[str, str],
    ] = {}

    files = sorted(
        path
        for path in root.rglob("*.toml")
        if path != manifest_path
    )

    for path in files:
        relative = path.relative_to(root)
        context = relative.as_posix()
        target = _target_for(
            path,
            root,
        )
        data = _read_toml(path)

        _require_fields(
            data,
            {
                "source_blob",
                "survivor",
            },
            context,
        )

        source_blob = _require_blob(
            data,
            "source_blob",
            context,
        )

        raw_survivors = data["survivor"]

        if (
            not isinstance(raw_survivors, list)
            or not raw_survivors
        ):
            raise CatalogError(
                f"{context}: survivor must be a non-empty array of tables"
            )

        if target in source_blobs:
            raise CatalogError(
                f"{context}: duplicate catalog for target {target!r}"
            )

        source_blobs[target] = source_blob

        for index, raw in enumerate(raw_survivors):
            key, classification = _load_survivor(
                raw,
                target,
                index,
            )

            if key in survivors:
                raise CatalogError(
                    f"{context}: duplicate survivor key {key!r}"
                )

            survivors[key] = classification

    actual_targets = set(source_blobs)
    expected_targets = set(catalog_targets)

    if actual_targets != expected_targets:
        missing = expected_targets - actual_targets
        unexpected = actual_targets - expected_targets
        problems = []

        if missing:
            problems.append(
                "missing catalogs: " + ", ".join(sorted(missing))
            )

        if unexpected:
            problems.append(
                "unlisted catalogs: " + ", ".join(sorted(unexpected))
            )

        raise CatalogError(
            "manifest/catalog inventory mismatch; "
            + "; ".join(problems)
        )

    return (
        engine_blob,
        source_blobs,
        survivors,
    )


(
    SURVIVOR_ENGINE_BLOB,
    SURVIVOR_SOURCE_BLOBS,
    SURVIVORS,
) = load_catalog(CATALOG_ROOT)
