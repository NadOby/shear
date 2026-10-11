"""Source-grounded semantic-content mechanisms for task 23.

This is a bounded mechanism inventory, not a dynamic conversion count.
Mechanisms are distinct from the AST helper-call sites counted by
content_baseline.py. Relationships classify specific pairs without
presuming that equivalent semantic content means redundant work.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


# ID, path, qualified function, required source-level call,
# source representation, destination representation, result behavior.
#
# The evidence collector verifies each function and anchor against the
# checked-out source and reports their actual line numbers.
MECHANISMS = (
    (
        "canonical_value", "shear/canonical.py", "canonicalize", "_node",
        "supported Python semantic values",
        "immutable tagged canonical content",
        "Mixed: canonical nodes pass through; other values may be converted.",
    ),
    (
        "canonical_bytes", "shear/canonical.py",
        "canonical_serialize", "_encode_text",
        "semantic values or canonical content",
        "type-tagged canonical bytes",
        "Serialization for identity; byte results are not generally cached.",
    ),
    (
        "value_content", "shear/values.py",
        "Value.__post_init__", "canonicalize",
        "supplied semantic value or SemanticRecord",
        "stored Value.content",
        "Retained canonical semantic content.",
    ),
    (
        "relation_normalization", "shear/relations.py",
        "Relation.__post_init__", "_normalize_endpoint",
        "supplied role endpoints and payload",
        "normalized Relation record",
        "Retained immutable role mapping and canonicalized payload.",
    ),
    (
        "relation_to_node", "shear/relations.py",
        "Relation.canonical_node", "_node",
        "live Relation record",
        "tagged canonical relation node",
        "Derived canonical form; not an additional authoritative value.",
    ),
    (
        "node_to_relation", "shear/relations.py",
        "relation_of", "Relation",
        "canonical relation content in Value",
        "decoded Relation or None",
        "Value._relation caches the derived result, including None.",
    ),
    (
        "function_to_node", "shear/lang.py",
        "Function.canonical_node", "_node",
        "input-format Function record",
        "canonical tagged function content",
        "Derived serialization of the input-format record.",
    ),
    (
        "node_to_function", "shear/lang.py",
        "_function_from_canonical", "_decode",
        "canonical tagged function content",
        "input-format Function record or None",
        "Conditional reconstruction; no dedicated Function cache.",
    ),
    (
        "function_value", "shear/lang.py",
        "function_of", "_function_from_canonical",
        "Value.content containing input-format Function",
        "Function record or None",
        "Delegates reconstruction; distinct from loaded graph-form code.",
    ),
    (
        "definition_to_relation", "shear/lang.py",
        "_Definition.relation", "Relation",
        "graph-form definition metadata",
        "relation record representing the function definition",
        "Constructs the representation persisted through Value.",
    ),
    (
        "definition_from_relation", "shear/lang.py",
        "_read_definition", "relation_of",
        "stored graph-form definition relation",
        "_Definition record or None",
        "Decodes a definition through the cached Relation view.",
    ),
    (
        "definition_cache", "shear/lang.py",
        "_definition_of", "_read_definition",
        "Value holding a graph-form definition",
        "cached _Definition or None",
        "Value._definition caches the derived definition.",
    ),
    (
        "expression_to_relation", "shear/lang.py",
        "_Builder._relation", "Relation",
        "input-format expression tuple",
        "graph-form Relation node",
        "Creates graph nodes through the expression builder.",
    ),
    (
        "graph_builder", "shear/lang.py",
        "_compile", "_Builder",
        "input-format function body",
        "builder containing graph-form relations",
        "Builds graph nodes; consumed by load or define.",
    ),
    (
        "load_graph", "shear/lang.py",
        "load", "_compile",
        "program with input-format Function values",
        "loaded graph-form State",
        "Uses the graph builder; not a separate expression compiler.",
    ),
    (
        "graph_to_expression", "shear/lang.py",
        "_collapse", "_node_at",
        "graph-form relation nodes",
        "input-format expression tuples",
        "Reconstructs an input expression when needed.",
    ),
    (
        "graph_to_function", "shear/lang.py",
        "function_at", "_collapse",
        "loaded graph-form function",
        "input-format Function record or None",
        "Uses graph collapse and constructs a Function record.",
    ),
    (
        "runtime_function", "shear/machine.py",
        "_function", "_decode",
        "runtime values for parameters and body",
        "input-format Function record",
        "Runtime boundary; decodes only as needed.",
    ),
    (
        "host_chunk", "shear/bytecode.py",
        "lower", "_decode",
        "one graph-form Relation node",
        "host bytecode chunk",
        "Host-side bytecode derivation, distinct from canonical storage.",
    ),
    (
        "bootstrap_compiler", "shear/examples/compiler_source.py",
        "compiler_entities", "Function",
        "Python-constructed compiler expressions",
        "loadable compiler Function records",
        "Python seed construction, not a running compiler conversion.",
    ),
    (
        "vm_compile_source", "shear/examples/vm.py",
        "_compiled", "_item",
        "retained compiler source expression",
        "SHEAR expression invoking active lower",
        "Constructs source for a compiler call, not its result.",
    ),
    (
        "vm_compiler_wrapper", "shear/examples/vm.py",
        "_swapped_function", "_item",
        "compiled chunk and original function metadata",
        "SHEAR-VM function-wrapper expression",
        "Constructs an interpreted wrapper from a compiled chunk.",
    ),
)


# ID, mechanism A, mechanism B, relationship, source-grounded rationale.
#
# These are relationships between *mechanisms*, not assertions that every
# call site of either mechanism performs duplicate work.
RELATIONSHIPS = (
    (
        "value_record_storage",
        "value_content",
        "relation_to_node",
        "composition_not_duplication",
        "Value.__post_init__ canonicalizes supplied content; "
        "Relation.canonical_node supplies the tagged record representation. "
        "The result is one stored Value.content.",
    ),
    (
        "relation_roundtrip",
        "relation_to_node",
        "node_to_relation",
        "inverse_with_derived_cache",
        "Relation.canonical_node encodes a record. relation_of decodes "
        "stored content only on a cache miss and retains the derived view "
        "on the immutable Value; the cache is not separate semantic state.",
    ),
    (
        "role_normalization",
        "relation_normalization",
        "relation_to_node",
        "different_operations",
        "Relation.__post_init__ normalizes endpoints and payload; "
        "canonical_node encodes an already constructed relation.",
    ),
    (
        "function_roundtrip",
        "function_to_node",
        "node_to_function",
        "inverse_not_duplication",
        "Function.canonical_node encodes the input format; "
        "_function_from_canonical reconstructs it when a tagged "
        "function value is read.",
    ),
    (
        "definition_views",
        "node_to_relation",
        "definition_from_relation",
        "composed_decoding",
        "_read_definition invokes relation_of and then interprets "
        "definition-specific roles and payload. This is a second derived "
        "view, not a second authoritative Value.content.",
    ),
    (
        "definition_caching",
        "definition_from_relation",
        "definition_cache",
        "derived_cache",
        "_definition_of caches _read_definition's result on Value. "
        "Repeated callers can reuse the cache. The relative allocation "
        "cost of _Definition and Relation caches is not measured.",
    ),
    (
        "input_to_graph",
        "expression_to_relation",
        "graph_builder",
        "composition_not_duplication",
        "_compile delegates individual expression conversion to "
        "_Builder._relation through the builder.",
    ),
    (
        "graph_roundtrip",
        "expression_to_relation",
        "graph_to_expression",
        "inverse_not_duplication",
        "The builder constructs graph-form nodes; _collapse reconstructs "
        "input-format expressions. These implement opposite directions.",
    ),
    (
        "graph_readback",
        "graph_to_expression",
        "graph_to_function",
        "composition_not_duplication",
        "function_at invokes _collapse and wraps the reconstructed "
        "body with its definition parameters.",
    ),
    (
        "input_and_loaded_functions",
        "function_value",
        "graph_to_function",
        "distinct_inputs_unresolved_cost",
        "function_of reads tagged input-format Function values. "
        "function_at reconstructs loaded graph-form functions. Both "
        "return Function records, but their input forms differ; the "
        "cost and need for repeated reconstruction remain unmeasured.",
    ),
    (
        "host_vs_shear_lowering",
        "host_chunk",
        "vm_compile_source",
        "alternative_routes_unresolved_cost",
        "Host bytecode.lower directly lowers graph-form nodes. "
        "vm._compiled constructs code calling the active SHEAR compiler. "
        "They are alternative compilation machinery, not the same "
        "conversion call; dynamic cost and overlap require measurement.",
    ),
    (
        "bootstrap_wrapper",
        "vm_compile_source",
        "vm_compiler_wrapper",
        "different_pipeline_stages",
        "_compiled constructs the compiler invocation; _swapped_function "
        "constructs a VM wrapper around the resulting chunk.",
    ),
)


# These exclusions prevent the enumerated mechanisms from being mistaken
# for an exhaustive inventory of every host-language representation change.
EXCLUSIONS = (
    {
        "subject": "Ordinary Python tuple/list/dict construction",
        "reason": (
            "Not classified as content conversion without a demonstrated "
            "semantic representation boundary."
        ),
    },
    {
        "subject": "Identity digests and derived cache keys",
        "reason": (
            "Canonical serialization calls are included in the helper "
            "inventory, but digest calculation is not counted as another "
            "semantic-content representation."
        ),
    },
    {
        "subject": "Graph endpoint rebinding and identity continuity",
        "reason": (
            "Changes graph relationships or entity identities, rather "
            "than necessarily converting the representation of content."
        ),
    },
    {
        "subject": "Instruction execution and runtime stacks",
        "reason": (
            "Execution of chunks is not counted as content conversion; "
            "host bytecode derivation is separately identified."
        ),
    },
    {
        "subject": "Unlisted helpers and third-party or host services",
        "reason": (
            "The inventory is a declared source-level boundary, not proof "
            "that every conversion or temporary object in shear/ was found."
        ),
    },
)


def _definition(tree: ast.Module, qualified: str) -> ast.AST:
    body = tree.body

    for part in qualified.split("."):
        matches = [
            node for node in body
            if isinstance(
                node,
                (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            )
            and node.name == part
        ]

        if len(matches) != 1:
            raise ValueError(f"missing or ambiguous mechanism: {qualified}")

        found = matches[0]
        body = found.body

    if not isinstance(found, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError(f"mechanism is not a function: {qualified}")

    return found


def _callee(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id

    if isinstance(node.func, ast.Attribute):
        return node.func.attr

    return None


def collect_evidence(root: Path) -> dict[str, Any]:
    """Validate mechanism anchors against the current source revision."""

    trees: dict[str, ast.Module] = {}
    sources: dict[str, str] = {}
    mechanisms = []
    seen = set()

    for (
        identifier, path, function, anchor, source, destination, behavior
    ) in MECHANISMS:
        if identifier in seen:
            raise ValueError(f"duplicate mechanism ID: {identifier}")

        seen.add(identifier)

        if path not in trees:
            content = (root / path).read_text(encoding="utf-8")
            sources[path] = content
            trees[path] = ast.parse(content, filename=path)

        definition = _definition(trees[path], function)
        calls = sorted(
            (
                node for node in ast.walk(definition)
                if isinstance(node, ast.Call) and _callee(node) == anchor
            ),
            key=lambda node: (node.lineno, node.col_offset),
        )

        if not calls:
            raise ValueError(
                f"{path}:{function} no longer calls {anchor}"
            )

        call = calls[0]
        expression = ast.get_source_segment(sources[path], call)

        mechanisms.append({
            "id": identifier,
            "path": path,
            "function": function,
            "line": definition.lineno,
            "anchor_line": call.lineno,
            "anchor": anchor,
            "source_representation": source,
            "destination_representation": destination,
            "retention": behavior,
            "source_evidence": (
                f"{path}:{call.lineno}: "
                f"{' '.join((expression or anchor).split())[:160]}"
            ),
        })

    relationships = []
    relation_ids = set()

    for identifier, left, right, classification, rationale in RELATIONSHIPS:
        if identifier in relation_ids:
            raise ValueError(f"duplicate relationship ID: {identifier}")

        if left not in seen or right not in seen:
            raise ValueError(
                f"{identifier}: references a missing conversion mechanism"
            )

        relation_ids.add(identifier)
        relationships.append({
            "id": identifier,
            "left": left,
            "right": right,
            "classification": classification,
            "evidence": rationale,
        })

    return {
        "mechanisms": mechanisms,
        "relationships": relationships,
        "exclusions": list(EXCLUSIONS),
        "counting_rule": (
            "Mechanisms are source definitions, not additional AST "
            "call sites or runtime invocations. They must not be added "
            "to the 140-site helper-call count."
        ),
    }
