"""Task 23: semantic-content inventory and measurement validation.

The deterministic inventory does not execute the compiler. Measurements
run only in the separately dispatched CI diagnostic.
"""

from __future__ import annotations

import ast
from collections import Counter
import json
import math
from pathlib import Path
from typing import Any

from shear.canonical import canonical_serialize, canonicalize
from tests.content_baseline_evidence import collect_evidence
from tests.mutation_catalog import SURVIVORS, SURVIVOR_SOURCE_BLOBS


ROOT = Path(__file__).resolve().parents[1]

TARGETS = (
    "shear/canonical.py",
    "shear/values.py",
    "shear/relations.py",
)

# The original helper-call inventory. Its count is preserved separately
# from the direct conversion mechanisms in content_baseline_evidence.py.
CONVERSIONS = {
    "canonicalize": (
        "host semantic value or record",
        "canonical semantic content",
    ),
    "canonical_serialize": (
        "semantic content",
        "canonical bytes",
    ),
    "relation_of": (
        "Value.content",
        "cached Relation or None",
    ),
    "_decode": (
        "canonical expression content",
        "host expression data",
    ),
    "_decode_endpoint": (
        "canonical endpoint",
        "EntityID endpoint",
    ),
    "_function_from_canonical": (
        "canonical function content",
        "Function input record",
    ),
    "function_of": (
        "Value.content",
        "Function input record or None",
    ),
    "function_at": (
        "graph-form function",
        "Function input record",
    ),
    "_compile": (
        "expression input tree",
        "graph-form relation nodes",
    ),
    "_collapse": (
        "graph-form relation nodes",
        "expression input tree",
    ),
}

# These entries identify particular source locations, not general rules
# inferred from a callee name. Every relationship is validated against
# the mechanism inventory. Other sites have unresolved overlap.
#
# Key: (module, qualified enclosing function, called helper).
# Value: named relationships in content_baseline_evidence.py.
SITE_RELATIONSHIPS = {
    (
        "shear/values.py",
        "Value.__post_init__",
        "canonicalize",
    ): ("value_record_storage",),
    (
        "shear/relations.py",
        "Relation.__post_init__",
        "canonicalize",
    ): ("role_normalization",),
    (
        "shear/relations.py",
        "Relation.canonical_node",
        "canonicalize",
    ): ("relation_roundtrip", "role_normalization"),
    (
        "shear/relations.py",
        "relation_of",
        "_decode_endpoint",
    ): ("relation_roundtrip",),
    (
        "shear/lang.py",
        "Function.canonical_node",
        "canonicalize",
    ): ("function_roundtrip",),
    (
        "shear/lang.py",
        "_function_from_canonical",
        "_decode",
    ): ("function_roundtrip",),
    (
        "shear/lang.py",
        "function_of",
        "_function_from_canonical",
    ): ("input_and_loaded_functions",),
    (
        "shear/lang.py",
        "_function_value",
        "_function_from_canonical",
    ): ("input_and_loaded_functions",),
    (
        "shear/lang.py",
        "_read_definition",
        "relation_of",
    ): ("definition_views", "definition_caching"),
    (
        "shear/lang.py",
        "_read_definition",
        "_decode",
    ): ("definition_views",),
    (
        "shear/lang.py",
        "load",
        "_compile",
    ): ("input_to_graph", "graph_roundtrip"),
    (
        "shear/lang.py",
        "define.compile_entry",
        "_compile",
    ): ("input_to_graph",),
    (
        "shear/lang.py",
        "_collapse",
        "_decode",
    ): ("graph_roundtrip",),
    (
        "shear/lang.py",
        "function_at",
        "_collapse",
    ): ("graph_readback", "graph_roundtrip"),
    (
        "shear/bytecode.py",
        "lower",
        "_decode",
    ): ("host_vs_shear_lowering",),
    (
        "shear/machine_calls.py",
        "_function",
        "_decode",
    ): ("function_roundtrip",),
    (
        "shear/machine.py",
        "_execute",
        "function_at",
    ): ("graph_readback",),
}

# These are source-supported semantic invariants, not evidence that
# the conversion is duplicated. All other necessity assessments are
# explicitly provisional.
SEMANTIC_SITES = {
    ("shear/values.py", "Value.__post_init__", "canonicalize"),
    ("shear/values.py", "_compute_version_id", "canonical_serialize"),
    ("shear/values.py", "Value._identity_key", "canonical_serialize"),
    ("shear/relations.py", "Relation.__post_init__", "canonicalize"),
    ("shear/relations.py", "Relation.__eq__", "canonical_serialize"),
    ("shear/relations.py", "Relation.__hash__", "canonical_serialize"),
    ("shear/lang.py", "Function.__eq__", "canonical_serialize"),
    ("shear/lang.py", "Function.__hash__", "canonical_serialize"),
    ("shear/canonical.py", "canonical_serialize", "canonical_serialize"),
    ("shear/state.py", "_state_content", "canonical_serialize"),
}

# An explicit result-retention rule is used only when the surrounding
# function is known to retain its canonicalized result.
STORED_RESULTS = {
    ("shear/values.py", "Value.__post_init__", "canonicalize"),
    ("shear/relations.py", "Relation.__post_init__", "canonicalize"),
}


def _callee(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id

    if isinstance(node.func, ast.Attribute):
        return node.func.attr

    return None


class _ConversionCalls(ast.NodeVisitor):
    """Enumerate AST call sites and preserve their qualified scope."""

    def __init__(
        self,
        path: str,
        source: str,
        relationships: dict[str, dict[str, Any]],
    ) -> None:
        self.path = path
        self.source = source
        self.relationships = relationships
        self.scope: list[str] = []
        self.sites: list[dict[str, Any]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Call(self, node: ast.Call) -> None:
        name = _callee(node)

        if name in CONVERSIONS:
            self.sites.append(self._site(node, name))

        self.generic_visit(node)

    def _site(self, node: ast.Call, name: str) -> dict[str, Any]:
        function = ".".join(self.scope) or "<module>"
        key = (self.path, function, name)
        source, destination = CONVERSIONS[name]

        expression = ast.get_source_segment(self.source, node) or name
        expression = " ".join(expression.split())

        source_evidence = (
            f"{self.path}:{node.lineno}:{node.col_offset}: "
            f"{expression[:160]}"
        )

        relationship_ids = SITE_RELATIONSHIPS.get(key, ())

        linked = [
            self.relationships[identifier]
            for identifier in relationship_ids
        ]

        # The exact call is source-grounded. Relationships are established
        # only for the source locations explicitly associated above.
        if linked:
            overlap: dict[str, Any] = {
                "status": "source_linked",
                "relationship_ids": list(relationship_ids),
                "classifications": [
                    item["classification"] for item in linked
                ],
                "mechanism_pairs": [
                    [item["left"], item["right"]]
                    for item in linked
                ],
                "assessment": (
                    "The cited relationships describe these mechanisms; "
                    "they do not prove that this call is redundant."
                ),
            }
        else:
            overlap = {
                "status": "unresolved",
                "relationship_ids": [],
                "classifications": [],
                "mechanism_pairs": [],
                "assessment": (
                    "No source-supported duplication relationship is "
                    "assigned to this call site. Redundancy is unknown."
                ),
            }

        if key in SEMANTIC_SITES:
            necessity = "semantic"
            necessity_status = "source_supported"
            necessity_reason = (
                "The enclosing implementation participates in canonical "
                "storage, semantic identity, or canonical equality."
            )
        else:
            necessity = "implementation"
            necessity_status = "unresolved"
            necessity_reason = (
                "This is an observed implementation conversion. "
                "Its removability or semantic necessity has not been "
                "established for this individual call site."
            )

        if key in STORED_RESULTS:
            retention = "retained"
            retention_status = "source_supported"
            retention_reason = (
                "The surrounding initializer assigns the converted "
                "result to an immutable stored field."
            )
        elif name == "relation_of":
            retention = "retained"
            retention_status = "conditional_cache"
            retention_reason = (
                "relation_of returns Value._relation on a cache hit, "
                "or reconstructs and caches the record on a miss. "
                "A static call site does not reveal which occurred."
            )
        elif name in {
            "_decode",
            "_decode_endpoint",
            "_function_from_canonical",
            "function_of",
            "function_at",
            "_compile",
            "_collapse",
        }:
            retention = "reconstructed"
            retention_status = "potential_reconstruction"
            retention_reason = (
                "The helper may construct a representation. The "
                "surrounding caller may retain it, and any subordinate "
                "cache reuse is not inferred from this call alone."
            )
        else:
            retention = "neither"
            retention_status = "unresolved"
            retention_reason = (
                "No persistent result storage is established at this "
                "call site. This does not rule out reuse by its caller."
            )

        return {
            "path": self.path,
            "line": node.lineno,
            "column": node.col_offset,
            "callee": name,
            "function": function,
            "source_representation": source,
            "destination_representation": destination,
            "kind": (
                "recursive"
                if self.scope and self.scope[-1] == name
                else "direct"
            ),
            "necessity": necessity,
            "necessity_status": necessity_status,
            "necessity_reason": necessity_reason,
            "retention": retention,
            "retention_status": retention_status,
            "retention_reason": retention_reason,
            "source_evidence": source_evidence,
            "overlap": overlap,
        }


def _conversion_sites(
    relationships: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    sites: list[dict[str, Any]] = []

    for path in sorted((ROOT / "shear").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        visitor = _ConversionCalls(relative, source, relationships)
        visitor.visit(ast.parse(source, filename=relative))
        sites.extend(visitor.sites)

    return sorted(
        sites,
        key=lambda item: (
            item["path"],
            item["line"],
            item["column"],
            item["callee"],
        ),
    )


def _representations() -> list[dict[str, str]]:
    return [
        {
            "subject": "Value.content",
            "classification": (
                "Authoritative canonical semantic content held by an "
                "immutable Value; not a second live input record."
            ),
            "evidence": (
                "shear/values.py: Value.__post_init__ stores canonicalize "
                "of supplied content and caches VersionID independently."
            ),
        },
        {
            "subject": "Relation.roles",
            "classification": (
                "Immutable normalized endpoint mapping on a Relation "
                "record. When decoded from Value.content, this is an "
                "alternative derived view, not independent semantic state."
            ),
            "evidence": (
                "shear/relations.py: Relation.__post_init__, "
                "Relation.canonical_node, and relation_of."
            ),
        },
        {
            "subject": "Relation.payload",
            "classification": (
                "Canonicalized payload retained in the Relation record; "
                "Relation.canonical_node incorporates it into canonical "
                "relation content."
            ),
            "evidence": (
                "shear/relations.py: Relation.__post_init__ and "
                "Relation.canonical_node."
            ),
        },
        {
            "subject": "relation_of cache",
            "classification": (
                "Conditionally decoded record cached as Value._relation. "
                "An immutable Value may retain both canonical content "
                "and a derived decoded view; only content is authoritative."
            ),
            "evidence": (
                "shear/relations.py: relation_of checks _relation, decodes "
                "on a miss, then stores the result, including None."
            ),
        },
    ]


def _boundaries() -> list[dict[str, str]]:
    return [
        {
            "path": "shear/examples/self_hosting.py",
            "function": "compiler_entities",
            "source_representation": "host expression tuples",
            "destination_representation": "Function input records",
            "host_service": "Python constructs the initial compiler program.",
        },
        {
            "path": "shear/examples/self_hosting.py",
            "function": "_lower_body",
            "source_representation": (
                "compiler algorithm expressed as Python tuples"
            ),
            "destination_representation": "SHEAR source expression",
            "host_service": (
                "Python constructs source; SHEAR executes lowering."
            ),
        },
        {
            "path": "shear/examples/vm_bootstrap.py",
            "function": "_compiled",
            "source_representation": "retained graph-form compiler source",
            "destination_representation": "SHEAR compiler-call expression",
            "host_service": (
                "Python constructs the expression; code inspection and "
                "active compiler execution use host runtime services."
            ),
        },
        {
            "path": "shear/examples/vm_bootstrap.py",
            "function": "_swapped_function",
            "source_representation": (
                "compiler-produced chunk and function metadata"
            ),
            "destination_representation": "interpreted compiler wrapper",
            "host_service": (
                "The host supplies function construction, quote and "
                "activation operations."
            ),
        },
        {
            "path": "shear/examples/vm_bootstrap.py",
            "function": "bootstrap_entities",
            "source_representation": (
                "Python-constructed compiler and VM definitions"
            ),
            "destination_representation": "loadable semantic program",
            "host_service": (
                "Python constructs the seed and supplies the host runtime."
            ),
        },
    ]


def _survivors() -> list[dict[str, Any]]:
    records = []

    for key, value in sorted(SURVIVORS.items()):
        target, kind, source, occurrence = key

        if target not in TARGETS:
            continue

        classification, reason = value
        records.append({
            "target": target,
            "kind": kind,
            "source": source,
            "occurrence": occurrence,
            "classification": classification,
            "reason": reason,
        })

    return records


def collect_inventory() -> dict[str, Any]:
    """Inventory the checked-out source without executing programs."""

    evidence = collect_evidence(ROOT)
    relationships = {
        item["id"]: item
        for item in evidence["relationships"]
    }

    for identifiers in SITE_RELATIONSHIPS.values():
        for identifier in identifiers:
            if identifier not in relationships:
                raise ValueError(
                    f"unknown conversion relationship: {identifier}"
                )

    sites = _conversion_sites(relationships)

    # Guard against a site-specific annotation silently becoming stale.
    observed_keys = {
        (site["path"], site["function"], site["callee"])
        for site in sites
    }
    missing = set(SITE_RELATIONSHIPS) - observed_keys

    if missing:
        raise ValueError(
            f"stale source-linked conversion sites: {sorted(missing)}"
        )

    by_callee = Counter(site["callee"] for site in sites)
    by_kind = Counter(site["kind"] for site in sites)
    by_overlap = Counter(
        site["overlap"]["status"] for site in sites
    )
    by_necessity_status = Counter(
        site["necessity_status"] for site in sites
    )
    by_retention_status = Counter(
        site["retention_status"] for site in sites
    )

    return {
        "scope": "checked-out shear/ Python sources",
        "method": (
            "AST helper-call inventory with preserved source coordinates. "
            "Additional direct conversion mechanisms are source-anchored "
            "separately. Source-linked mechanism relationships do not "
            "establish redundant execution or removable conversions. "
            "Unclassified necessity and overlap remain unresolved."
        ),
        "conversion_sites": sites,
        "counts": {
            "total": len(sites),
            "by_callee": dict(sorted(by_callee.items())),
            "by_kind": dict(sorted(by_kind.items())),
            "by_overlap_status": dict(sorted(by_overlap.items())),
            "by_necessity_status": dict(
                sorted(by_necessity_status.items())
            ),
            "by_retention_status": dict(
                sorted(by_retention_status.items())
            ),
        },
        "conversion_mechanisms": evidence["mechanisms"],
        "mechanism_relationships": evidence["relationships"],
        "mechanism_exclusions": evidence["exclusions"],
        "mechanism_counting_rule": evidence["counting_rule"],
        "representations": _representations(),
        "boundaries": _boundaries(),
        "survivors": _survivors(),
        "source_pins": {
            target: SURVIVOR_SOURCE_BLOBS.get(target)
            for target in TARGETS
        },
        "mutation_test_gaps": [],
        "mutation_gap_scope": (
            "No test gaps are inferred from the reviewed survivor "
            "catalog. Unclassified mutants and campaign coverage "
            "require separate mutation-run evidence."
        ),
    }


def _required(mapping: Any, fields: set[str], where: str) -> None:
    if not isinstance(mapping, dict):
        raise ValueError(f"{where} must be an object")

    missing = fields - mapping.keys()

    if missing:
        raise ValueError(
            f"{where} lacks: {', '.join(sorted(missing))}"
        )


def _number(value: Any, where: str, *, positive: bool = False) -> None:
    if type(value) not in (int, float):
        raise ValueError(f"{where} must be numeric")

    if not math.isfinite(value):
        raise ValueError(f"{where} must be finite")

    if value < 0 or (positive and value == 0):
        raise ValueError(
            f"{where} must be nonnegative or positive"
        )


def validate_measurement(report: dict[str, Any]) -> None:
    """Reject incomplete or inconsistent bootstrap evidence."""

    _required(
        report,
        {
            "workload", "revision", "ci_run_url", "hardware",
            "routes", "sizes", "edit",
        },
        "measurement",
    )

    if report["workload"] != "lower(lower)":
        raise ValueError("unexpected workload")

    revision = report["revision"]

    if (
        not isinstance(revision, str)
        or len(revision) != 40
        or any(char not in "0123456789abcdef" for char in revision)
    ):
        raise ValueError("revision must be a full commit SHA")

    if (
        not isinstance(report["ci_run_url"], str)
        or not report["ci_run_url"].startswith(
            "https://github.com/"
        )
        or "/actions/runs/" not in report["ci_run_url"]
    ):
        raise ValueError("CI run URL is missing or invalid")

    hardware = report["hardware"]
    _required(
        hardware,
        {"python", "os", "cpu", "cores"},
        "hardware",
    )

    for field in ("python", "os", "cpu"):
        if (
            not isinstance(hardware[field], str)
            or not hardware[field]
        ):
            raise ValueError(f"hardware.{field} is missing")

    if (
        type(hardware["cores"]) is not int
        or hardware["cores"] < 1
    ):
        raise ValueError("hardware.cores must be positive")

    routes = report["routes"]
    _required(routes, {"native", "shear_vm"}, "routes")

    for name in ("native", "shear_vm"):
        route = routes[name]
        _required(
            route,
            {"seconds", "peak_traced_bytes", "output"},
            name,
        )

        observations = route["seconds"]

        if (
            not isinstance(observations, list)
            or len(observations) < 3
        ):
            raise ValueError(
                f"{name} needs at least three observations"
            )

        for seconds in observations:
            _number(seconds, f"{name}.seconds")

        peak = route["peak_traced_bytes"]

        if type(peak) is not int:
            raise ValueError(
                f"{name}.peak_traced_bytes must be integer"
            )

        _number(peak, f"{name}.peak_traced_bytes")

        try:
            canonical_serialize(canonicalize(route["output"]))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{name}.output is invalid"
            ) from exc

    native = canonical_serialize(
        canonicalize(routes["native"]["output"])
    )
    interpreted = canonical_serialize(
        canonicalize(routes["shear_vm"]["output"])
    )

    if native != interpreted:
        raise ValueError(
            "compiler outputs differ between execution routes"
        )

    sizes = report["sizes"]
    _required(
        sizes,
        {
            "compiler_chunk_bytes",
            "derived_chunk_count",
            "derived_chunk_bytes",
            "state_content_bytes",
            "image_exclusions",
        },
        "sizes",
    )

    for field in (
        "compiler_chunk_bytes",
        "derived_chunk_count",
        "derived_chunk_bytes",
        "state_content_bytes",
    ):
        if type(sizes[field]) is not int:
            raise ValueError(
                f"sizes.{field} must be integer"
            )
        _number(
            sizes[field],
            f"sizes.{field}",
            positive=True,
        )

    exclusions = sizes["image_exclusions"]

    if (
        not isinstance(exclusions, list)
        or not exclusions
        or not all(
            isinstance(item, str) and item
            for item in exclusions
        )
    ):
        raise ValueError(
            "image proxy exclusions must be explicit"
        )

    edit = report["edit"]
    _required(
        edit,
        {
            "phase_seconds",
            "total_seconds",
            "affected_nodes",
            "affected_chunks",
            "before",
            "after",
        },
        "edit",
    )
    _required(
        edit["phase_seconds"],
        {"define", "lower", "activate"},
        "edit.phase_seconds",
    )

    for phase in ("define", "lower", "activate"):
        _number(
            edit["phase_seconds"][phase],
            f"edit.{phase}",
        )

    _number(
        edit["total_seconds"],
        "edit.total_seconds",
    )

    for field in ("affected_nodes", "affected_chunks"):
        if type(edit[field]) is not int:
            raise ValueError(
                f"edit.{field} must be integer"
            )
        _number(
            edit[field],
            f"edit.{field}",
            positive=True,
        )

    if edit["before"] == edit["after"]:
        raise ValueError(
            "the edit did not change the observed result"
        )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=("inventory",),
        help="Inventory is deterministic and performs no timing",
    )
    parser.parse_args(argv)

    print(
        json.dumps(
            collect_inventory(),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
