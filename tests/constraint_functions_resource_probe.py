"""Narrow authenticated inspection probes for GH-123 resource acceptance.

Each measured operation uses its own minimal admitted SHEAR program.
No host code traverses semantic values or computes inspection results.
"""

from __future__ import annotations

from functools import lru_cache

from shear import EntityID, canonicalize
from shear.examples._support import program
from shear.hosted_bootstrap.restricted import RestrictedExecutor
from shear.lang import Function, load


NARROW_RESOURCE_ENTRY = EntityID("constraint.resource.narrow")


def _probe_body(operation: str) -> tuple:
    value = ("arg", "value")
    argument = ("arg", "argument")

    if operation == "control":
        return ("lit", None)
    if operation == "inspect":
        return ("inspect", value)
    if operation == "item":
        return ("item", value, argument)
    if operation == "roles":
        return ("item", value, ("lit", "roles"))
    if operation == "arguments":
        return ("item", value, ("lit", "arguments"))

    raise ValueError(f"unsupported resource probe: {operation!r}")


@lru_cache(maxsize=5)
def _admitted_probe(operation: str) -> tuple:
    """Cache source-specific admitted code, never an input or a result."""
    body = _probe_body(operation)
    source = load(program({
        NARROW_RESOURCE_ENTRY: Function(("value", "argument"), body),
    }))
    executor = RestrictedExecutor()
    deployment = executor.deploy(source)
    return executor, deployment


def prepare_narrow_resource_probe(canonical_value: object, operation: str):
    """Return a measured callable over one previously canonicalized value.

    Source admission and argument normalization precede the measurement.
    Every invocation authenticates, preflights and executes SHEAR code.
    """
    if operation not in (
        "control", "inspect", "item", "roles", "arguments",
    ):
        raise ValueError(f"unsupported resource probe: {operation!r}")

    value = canonicalize(canonical_value)
    executor, deployment = _admitted_probe(operation)

    def invoke(argument: object) -> object:
        return executor.run(
            deployment, NARROW_RESOURCE_ENTRY, value, argument,
        )

    return invoke
