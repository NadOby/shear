"""Execution machine for SHEAR bytecode."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable, Mapping

from . import bytecode, machine_semantics
from .canonical import CanonicalNode, canonical_serialize, canonicalize
from .closures import Closure
from .constraints import _HOST_FAILURES, _is_host_failure, kind_of
from .identity import EntityID
from .lang import (
    CallDepthExceeded, LanguageError, _decode, _definition_of, _fill,
    function_at, function_of,
)
from .machine_calls import (
    _callable, _closure, _function, _reference, _resolved_call,
)
from .machine_errors import (
    _RUN, _Raised, _attach, _attach_runtime, _detail,
)
from .machine_runtime import _activation_pairs, _define_for_operation
from .runtime import (
    ActivationRejected, CellContentRejected, CellError,
    RelationConstraintRejected, Runtime,
)
from .values import Value

_RETURN: bytecode.Chunk = (("RETURN",),)

# Where the current run gets the chunk of a node: ``(state, entity, owner)``
# to chunk. None, the default, lowers on demand and caches on the node's value
# (bytecode.chunk_of). A caller that must run only artifacts it has admitted
# passes ``resolver`` to :func:`run`; the resolver then replaces lowering and
# its value cache completely, for every node the run opens. Two loaded
# versions can have one state, so a resolver that has a ``for_version``
# method is asked ``for_version(version, entity, owner)`` instead, with the
# version of the frame that opens the node.
ChunkResolver = Callable[[Any, EntityID, EntityID], bytecode.Chunk]
_RESOLVER: ContextVar[ChunkResolver | None] = ContextVar(
    "shear_chunk_resolver",
    default=None,
)


def _chunk_for(
    version: Any,
    entity: EntityID,
    owner: EntityID,
) -> bytecode.Chunk:
    resolver = _RESOLVER.get()

    if resolver is not None:
        scoped = getattr(resolver, "for_version", None)

        if scoped is not None:
            return scoped(version, entity, owner)

        return resolver(version.state, entity, owner)

    return bytecode.chunk_of(version.state, entity, owner)


class _Activation:
    __slots__ = ("entity", "hold", "values")

    def __init__(self, entity: EntityID, hold: Any) -> None:
        self.entity = entity
        self.hold = hold
        self.values: Mapping[EntityID, Value] = {}


class _Handler:
    __slots__ = ("control_depth", "stack_height", "live_count", "kinds")

    def __init__(
        self,
        control_depth: int,
        stack_height: int,
        live_count: int,
        kinds: tuple[str, ...] | None,
    ) -> None:
        self.control_depth = control_depth
        self.stack_height = stack_height
        self.live_count = live_count
        self.kinds = kinds


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


_PRIMITIVES = (str, int, bool, type(None))


def _semantically_equal(left: Any, right: Any) -> bool:
    if type(left) in _PRIMITIVES and type(right) in _PRIMITIVES:
        return type(left) is type(right) and left == right

    return canonical_serialize(canonicalize(left)) == canonical_serialize(
        canonicalize(right)
    )


def _items(value: Any) -> tuple[Any, ...] | None:
    if isinstance(value, CanonicalNode):
        return value[2] if value[1] == "tuple" else None

    return value if isinstance(value, tuple) else None


def _pop_n(
    stack: list[Any],
    count: int,
) -> list[Any]:
    start = len(stack) - count
    values = stack[start:]
    del stack[start:]
    return values


def _child_chunk(
    activation: _Activation,
    entity: EntityID,
    function: EntityID,
) -> bytecode.Chunk:
    if _RESOLVER.get() is not None:
        return _chunk_for(activation.hold.version, entity, function)

    value = activation.values.get(entity)
    child = (
        None
        if value is None
        else value.__dict__.get("_chunk")
    )

    if child is not None:
        return child

    try:
        return bytecode.lower_value(
            value,
            entity,
            function,
        )
    except LanguageError as exc:
        _attach(
            exc,
            "language",
            "invalid_code",
            _detail(problem=str(exc)),
            function,
            entity,
        )
        raise


def _open(
    activation: _Activation,
    args: list[Any],
    where: tuple[EntityID, EntityID] | None = None,
    operation: str = "call",
) -> tuple[
    bytecode.Chunk,
    dict[str, Any],
    EntityID,
]:
    entity = activation.entity
    state = activation.hold.version.state
    activation.values = state.values
    value = state.values[entity]
    definition = _definition_of(value)

    if definition is None:
        unloaded = function_of(value) is not None
        exc = LanguageError(
            f"{entity.value} is not a function"
            + (
                "; load the program first"
                if unloaded
                else ""
            )
        )
        function, node = where or (entity, entity)
        raise _attach(
            exc,
            "language",
            "not_a_function",
            _detail(
                entity=entity,
                operation=operation,
            ),
            function,
            node,
        )

    failure_where = where or (
        entity,
        definition.body,
    )

    if len(args) != len(definition.params):
        exc = LanguageError(
            f"{entity.value} takes "
            f"{len(definition.params)} argument(s), "
            f"got {len(args)}"
        )
        raise _attach(
            exc,
            "language",
            "arity",
            _detail(
                expected=len(definition.params),
                function=entity,
                got=len(args),
            ),
            *failure_where,
        )

    try:
        chunk = _chunk_for(
            activation.hold.version,
            definition.body,
            entity,
        )
    except LanguageError as exc:
        _attach(
            exc,
            "language",
            "invalid_code",
            _detail(problem=str(exc)),
            entity,
            definition.body,
        )
        raise

    return (
        chunk,
        dict(zip(definition.params, args)),
        definition.body,
    )


def _open_closure(
    activation: _Activation,
    closure: Closure,
    args: list[Any],
    where: tuple[EntityID, EntityID],
    operation: str,
) -> tuple[
    bytecode.Chunk,
    dict[str, Any],
    EntityID,
]:
    state = activation.hold.version.state
    activation.values = state.values
    owner_value = state.values.get(
        closure.owner
    )
    message = (
        f"{closure.owner.value}: closure owner is not "
        f"a function in the active version"
    )

    if owner_value is None:
        raise _attach(
            LanguageError(message),
            "language",
            "absent",
            _detail(
                entity=closure.owner,
                operation=operation,
            ),
            *where,
        )

    if _definition_of(owner_value) is None:
        raise _attach(
            LanguageError(message),
            "language",
            "not_a_function",
            _detail(
                entity=closure.owner,
                operation=operation,
            ),
            *where,
        )

    if closure.body not in state.values:
        exc = LanguageError(
            f"{closure.owner.value}: closure body "
            f"{closure.body.value} is absent from the active version"
        )
        raise _attach(
            exc,
            "language",
            "absent",
            _detail(
                entity=closure.body,
                operation=operation,
            ),
            *where,
        )

    if state.owner_of(closure.body) != closure.owner:
        problem = (
            f"closure body {closure.body.value} "
            f"no longer belongs to its owner"
        )
        exc = LanguageError(
            f"{closure.owner.value}: {problem}"
        )
        raise _attach(
            exc,
            "language",
            "malformed",
            _detail(
                operation=operation,
                problem=problem,
            ),
            *where,
        )

    if len(args) != len(closure.params):
        exc = LanguageError(
            f"{closure.owner.value} closure takes "
            f"{len(closure.params)} argument(s), "
            f"got {len(args)}"
        )
        raise _attach(
            exc,
            "language",
            "arity",
            _detail(
                expected=len(closure.params),
                function=closure.owner,
                got=len(args),
            ),
            *where,
        )

    env = dict(closure.captures)
    env.update(
        zip(closure.params, args)
    )

    try:
        chunk = _chunk_for(
            activation.hold.version,
            closure.body,
            closure.owner,
        )
    except LanguageError as exc:
        _attach(
            exc,
            "language",
            "invalid_code",
            _detail(problem=str(exc)),
            closure.owner,
            closure.body,
        )
        raise

    return chunk, env, closure.body


def _execute(
    runtime: Runtime,
    may_activate: bool,
    entry: EntityID,
    args: list[Any],
    run_token: object,
) -> Any:
    previous_run = _RUN.set(run_token)
    stack: list[Any] = []
    control: list[tuple] = []
    live: list[_Activation] = []
    handlers: list[_Handler] = []

    try:
        hold = runtime.enter(entry)
        activation = _Activation(
            entry,
            hold,
        )
        live.append(activation)
        chunk, env, current_node = _open(
            activation,
            args,
        )
        current_function = entry
        pc = 0
        tail = True
        control.append(
            (
                _RETURN,
                0,
                False,
                None,
                activation,
                current_function,
                current_node,
            )
        )

        while True:
            try:
                instr = chunk[pc]
                pc += 1
                op = instr[0]

                if op == "EVAL":
                    child = _child_chunk(
                        activation,
                        instr[1],
                        current_function,
                    )
                    control.append(
                        (
                            chunk,
                            pc,
                            tail,
                            env,
                            activation,
                            current_function,
                            current_node,
                        )
                    )
                    chunk = child
                    current_node = instr[1]
                    pc = 0
                    tail = False

                elif op == "ARG":
                    name = instr[1]

                    if (
                        not isinstance(name, str)
                        or name not in env
                    ):
                        exc = LanguageError(
                            f"{activation.entity.value}: "
                            f"unknown parameter {name!r}"
                        )
                        raise _attach(
                            exc,
                            "language",
                            "unknown_name",
                            _detail(name=name),
                            current_function,
                            current_node,
                        )

                    stack.append(env[name])

                elif op == "LIT":
                    stack.append(
                        _decode(instr[1])
                    )

                elif op == "END":
                    (
                        chunk,
                        pc,
                        tail,
                        env,
                        activation,
                        current_function,
                        current_node,
                    ) = control.pop()

                elif op == "INT":
                    value = stack[-1]
                    named_field = (
                        instr[1] == "item"
                        and isinstance(value, str)
                        and machine_semantics.execute(
                            "INSPECT", stack[-2]
                        )[0] in ("cell", "constraint", "relation")
                    )

                    if not (_is_int(value) or named_field):
                        exc = LanguageError(
                            f"{activation.entity.value}: "
                            f"{instr[1]} operands must be int"
                        )
                        raise _attach(
                            exc,
                            "language",
                            "wrong_kind",
                            _detail(
                                expected="int",
                                got=kind_of(value),
                                operation=instr[1],
                            ),
                            current_function,
                            current_node,
                        )

                elif op in (
                    "ADD",
                    "SUB",
                    "MUL",
                    "LT",
                ):
                    right = stack.pop()

                    if op == "ADD":
                        stack[-1] += right
                    elif op == "SUB":
                        stack[-1] -= right
                    elif op == "MUL":
                        stack[-1] *= right
                    else:
                        stack[-1] = (
                            stack[-1] < right
                        )

                elif op == "EQ":
                    right = stack.pop()
                    stack[-1] = _semantically_equal(
                        stack[-1],
                        right,
                    )

                elif op == "BRANCH":
                    condition = stack.pop()

                    if not isinstance(condition, bool):
                        exc = LanguageError(
                            f"{activation.entity.value}: "
                            f"if condition must be bool"
                        )
                        raise _attach(
                            exc,
                            "language",
                            "wrong_kind",
                            _detail(
                                expected="bool",
                                got=kind_of(condition),
                                operation="if",
                            ),
                            current_function,
                            current_node,
                        )

                    entity = (
                        instr[1]
                        if condition
                        else instr[2]
                    )
                    chunk = _child_chunk(
                        activation,
                        entity,
                        current_function,
                    )
                    current_node = entity
                    pc = 0

                elif op == "GOTO":
                    chunk = _child_chunk(
                        activation,
                        instr[1],
                        current_function,
                    )
                    current_node = instr[1]
                    pc = 0

                elif op == "POP":
                    stack.pop()

                elif op in (
                    "CALL",
                    "APPLY",
                    "APPLYV",
                ):
                    closure = None
                    call_function = current_function
                    call_node = current_node
                    operation = (
                        "call"
                        if op == "CALL"
                        else op.lower()
                    )

                    if op == "CALL":
                        target_entity = instr[1]
                        arguments = _pop_n(
                            stack,
                            instr[2],
                        )
                    else:
                        arguments = (
                            _pop_n(
                                stack,
                                instr[1],
                            )
                            if op == "APPLY"
                            else list(stack.pop())
                        )
                        target = stack.pop()
                        (
                            target_entity,
                            closure,
                        ) = _resolved_call(
                            runtime,
                            call_function,
                            call_node,
                            target,
                            operation,
                        )

                    if (
                        not tail
                        and len(live)
                        >= bytecode.CALL_DEPTH_LIMIT
                    ):
                        exc = CallDepthExceeded(
                            f"{activation.entity.value}: more than "
                            f"{bytecode.CALL_DEPTH_LIMIT} "
                            f"calls waiting on each other"
                        )
                        raise _attach(
                            exc,
                            "limit",
                            "depth_limit",
                            _detail(
                                limit=bytecode.CALL_DEPTH_LIMIT,
                            ),
                            call_function,
                            call_node,
                        )

                    hold = runtime.enter(
                        target_entity
                    )

                    if tail:
                        released = activation.hold
                        activation.entity = (
                            target_entity
                        )
                        activation.hold = hold
                        released.release()
                    else:
                        control.append(
                            (
                                chunk,
                                pc,
                                tail,
                                env,
                                activation,
                                current_function,
                                current_node,
                            )
                        )
                        activation = _Activation(
                            target_entity,
                            hold,
                        )
                        live.append(activation)
                        control.append(
                            (
                                _RETURN,
                                0,
                                False,
                                None,
                                activation,
                                target_entity,
                                call_node,
                            )
                        )

                    if closure is None:
                        (
                            chunk,
                            env,
                            current_node,
                        ) = _open(
                            activation,
                            arguments,
                            (
                                call_function,
                                call_node,
                            ),
                            operation,
                        )
                        current_function = (
                            target_entity
                        )
                    else:
                        (
                            chunk,
                            env,
                            current_node,
                        ) = _open_closure(
                            activation,
                            closure,
                            arguments,
                            (
                                call_function,
                                call_node,
                            ),
                            operation,
                        )
                        current_function = (
                            closure.owner
                        )

                    pc = 0
                    tail = True

                elif op == "RETURN":
                    live.pop()
                    activation.hold.release()

                    if not control:
                        return stack.pop()

                    (
                        chunk,
                        pc,
                        tail,
                        env,
                        activation,
                        current_function,
                        current_node,
                    ) = control.pop()

                elif op == "LETCHECK":
                    if instr[1] in env:
                        exc = LanguageError(
                            f"{activation.entity.value}: "
                            f"let name {instr[1]!r} "
                            f"is already in scope"
                        )
                        raise _attach(
                            exc,
                            "language",
                            "name_in_scope",
                            _detail(
                                name=instr[1],
                            ),
                            current_function,
                            current_node,
                        )

                elif op == "LETBIND":
                    env = {
                        **env,
                        instr[1]: stack.pop(),
                    }
                    chunk = _child_chunk(
                        activation,
                        instr[2],
                        current_function,
                    )
                    current_node = instr[2]
                    pc = 0

                elif op == "CATCH":
                    handler = _Handler(
                        len(control),
                        len(stack),
                        len(live),
                        instr[2],
                    )
                    handlers.append(handler)
                    continuation = (
                        (
                            "CATCH_OK",
                            handler,
                        ),
                        ("END",),
                    )
                    control.append(
                        (
                            continuation,
                            0,
                            False,
                            env,
                            activation,
                            current_function,
                            current_node,
                        )
                    )
                    chunk = _child_chunk(
                        activation,
                        instr[1],
                        current_function,
                    )
                    current_node = instr[1]
                    pc = 0
                    tail = False

                elif op == "CATCH_OK":
                    handler = instr[1]

                    if (
                        not handlers
                        or handlers[-1]
                        is not handler
                    ):
                        raise RuntimeError(
                            "catch handler stack is inconsistent"
                        )

                    handlers.pop()
                    value = stack.pop()
                    stack.append(
                        ("ok", value)
                    )

                elif op == "MKTUPLE":
                    stack.append(
                        tuple(
                            _pop_n(
                                stack,
                                instr[1],
                            )
                        )
                    )

                elif op == "TUPLE":
                    value = stack.pop()

                    if instr[1] in ("len", "item", "slice"):
                        try:
                            machine_semantics.execute("LEN", value)
                        except machine_semantics.SemanticFailure as error:
                            exc = LanguageError(
                                f"{activation.entity.value}: "
                                f"{instr[1]}: {error}"
                            )
                            raise _attach(
                                exc,
                                "language",
                                error.kind,
                                error.detail,
                                current_function,
                                current_node,
                            ) from error

                        stack.append(value)
                    else:
                        items = _items(value)

                        if items is None:
                            exc = LanguageError(
                                f"{activation.entity.value}: "
                                f"{instr[1]} operands must be tuples"
                            )
                            raise _attach(
                                exc,
                                "language",
                                "wrong_kind",
                                _detail(
                                    expected="tuple",
                                    got=kind_of(value),
                                    operation=instr[1],
                                ),
                                current_function,
                                current_node,
                            )

                        stack.append(items)
                elif op in ("INSPECT", "RECORD", "LEN", "ITEM", "SLICE"):
                    values = _pop_n(stack, machine_semantics.ARITY[op])

                    try:
                        result = machine_semantics.execute(op, *values)
                    except machine_semantics.SemanticFailure as error:
                        exc = LanguageError(
                            f"{activation.entity.value}: "
                            f"{op.lower()}: {error}"
                        )
                        raise _attach(
                            exc,
                            "language",
                            error.kind,
                            error.detail,
                            current_function,
                            current_node,
                        ) from error

                    stack.append(result)

                elif op == "CONCAT":
                    right = stack.pop()
                    stack[-1] += right

                elif op == "REF":
                    held = activation.values.get(
                        instr[1]
                    )

                    if (
                        held is None
                        or _definition_of(held)
                        is None
                    ):
                        exc = LanguageError(
                            f"{activation.entity.value}: "
                            f"ref {instr[2]!r} does not "
                            f"name a function"
                        )
                        error_kind = (
                            "absent"
                            if held is None
                            else "not_a_function"
                        )
                        raise _attach(
                            exc,
                            "language",
                            error_kind,
                            _detail(
                                entity=instr[1],
                                operation="ref",
                            ),
                            current_function,
                            current_node,
                        )

                    stack.append(instr[1])

                elif op == "CODE":
                    function = function_at(
                        runtime.active.state,
                        instr[1],
                    )

                    if function is None:
                        exc = LanguageError(
                            f"{activation.entity.value}: "
                            f"code {instr[2]!r} does not "
                            f"name a function"
                        )
                        error_kind = (
                            "absent"
                            if instr[1]
                            not in runtime.active.state.values
                            else "not_a_function"
                        )
                        raise _attach(
                            exc,
                            "language",
                            error_kind,
                            _detail(
                                entity=instr[1],
                                operation="code",
                            ),
                            current_function,
                            current_node,
                        )

                    stack.append(
                        (
                            function.params,
                            function.body,
                        )
                    )

                elif op == "LINKS":
                    held = (
                        runtime.active.state.values.get(
                            instr[1]
                        )
                    )
                    definition = (
                        None
                        if held is None
                        else _definition_of(held)
                    )

                    if definition is None:
                        exc = LanguageError(
                            f"{activation.entity.value}: "
                            f"linksof {instr[2]!r} does not "
                            f"name a function"
                        )
                        error_kind = (
                            "absent"
                            if held is None
                            else "not_a_function"
                        )
                        raise _attach(
                            exc,
                            "language",
                            error_kind,
                            _detail(
                                entity=instr[1],
                                operation="linksof",
                            ),
                            current_function,
                            current_node,
                        )

                    stack.append(
                        tuple(
                            (
                                name,
                                target,
                            )
                            for name, target
                            in sorted(
                                definition.links.items()
                            )
                            if isinstance(
                                target,
                                EntityID,
                            )
                        )
                    )

                elif op == "REFCHECK":
                    value = stack.pop()
                    target = _callable(value)

                    if target is None:
                        operation = (
                            "applyv"
                            if any(
                                item[0] == "APPLYV"
                                for item in chunk[pc:]
                            )
                            else "apply"
                        )
                        exc = LanguageError(
                            f"{activation.entity.value}: "
                            f"apply needs a function "
                            f"reference or closure"
                        )
                        raise _attach(
                            exc,
                            "language",
                            "wrong_kind",
                            _detail(
                                expected="callable",
                                got=kind_of(value),
                                operation=operation,
                            ),
                            current_function,
                            current_node,
                        )

                    stack.append(target)

                elif op == "CLOSURE":
                    try:
                        value = _closure(
                            activation.entity,
                            instr[1],
                            instr[2],
                            instr[3],
                            env,
                        )
                    except LanguageError as exc:
                        _attach(
                            exc,
                            "language",
                            "malformed",
                            _detail(
                                operation="closure",
                                problem=str(exc),
                            ),
                            current_function,
                            current_node,
                        )
                        raise

                    stack.append(value)

                elif op == "READ":
                    try:
                        stack.append(
                            runtime.read(
                                instr[1]
                            )
                        )
                    except CellError as exc:
                        wrapped = LanguageError(
                            str(exc)
                        )
                        raise _attach(
                            wrapped,
                            "language",
                            "not_a_cell",
                            _detail(
                                entity=instr[1],
                                operation="read",
                            ),
                            current_function,
                            current_node,
                        ) from exc

                elif op == "WRITE":
                    try:
                        runtime.write(
                            instr[1],
                            stack[-1],
                        )
                    except CellError as exc:
                        if _is_host_failure(exc):
                            raise

                        wrapped = LanguageError(
                            str(exc)
                        )
                        raise _attach(
                            wrapped,
                            "language",
                            "not_a_cell",
                            _detail(
                                entity=instr[1],
                                operation="write",
                            ),
                            current_function,
                            current_node,
                        ) from exc
                    except (
                        CellContentRejected,
                        RelationConstraintRejected,
                    ) as exc:
                        _attach_runtime(
                            exc,
                            current_function,
                            current_node,
                            "write",
                        )
                        raise

                elif op == "QUOTE":
                    holes = iter(
                        _pop_n(
                            stack,
                            instr[2],
                        )
                    )
                    stack.append(
                        _fill(
                            _decode(instr[1]),
                            holes,
                        )
                    )

                elif op == "FUNCTION":
                    body = stack.pop()
                    params = stack.pop()

                    try:
                        value = _function(
                            activation.entity,
                            params,
                            body,
                        )
                    except LanguageError as exc:
                        _attach(
                            exc,
                            "language",
                            "malformed",
                            _detail(
                                operation="function",
                                problem=str(exc),
                            ),
                            current_function,
                            current_node,
                        )
                        raise

                    stack.append(value)

                elif op == "ACTIVATE":
                    values = _pop_n(
                        stack,
                        len(instr[1]),
                    )
                    active, edits = _activation_pairs(
                        runtime,
                        current_function,
                        current_node,
                        instr[1],
                        instr[2],
                        values,
                        "activate",
                    )

                    if not may_activate:
                        exc = ActivationRejected(
                            "activation capability not granted"
                        )
                        raise _attach(
                            exc,
                            "runtime",
                            "no_capability",
                            _detail(
                                operation="activate",
                            ),
                            current_function,
                            current_node,
                        )

                    result = _define_for_operation(
                        active,
                        edits,
                        "activate",
                        current_function,
                        current_node,
                    )

                    try:
                        runtime.activate(result)
                    except ActivationRejected as exc:
                        _attach_runtime(
                            exc,
                            current_function,
                            current_node,
                            "activate",
                        )
                        raise

                    stack.append(None)

                elif op == "TRIAL":
                    (
                        _,
                        entries,
                        targets,
                        problem,
                        target,
                        arg_count,
                    ) = instr
                    values = _pop_n(
                        stack,
                        len(entries),
                    )
                    arguments = _pop_n(
                        stack,
                        arg_count,
                    )
                    active, edits = _activation_pairs(
                        runtime,
                        current_function,
                        current_node,
                        entries,
                        targets,
                        values,
                        "trial",
                    )

                    if problem is not None:
                        exc = LanguageError(
                            f"{activation.entity.value}: "
                            f"{problem}"
                        )
                        raise _attach(
                            exc,
                            "language",
                            "malformed",
                            _detail(
                                operation="trial",
                                problem=problem,
                            ),
                            current_function,
                            current_node,
                        )

                    if not may_activate:
                        exc = ActivationRejected(
                            "activation capability not granted"
                        )
                        raise _attach(
                            exc,
                            "runtime",
                            "no_capability",
                            _detail(
                                operation="trial",
                            ),
                            current_function,
                            current_node,
                        )

                    result = _define_for_operation(
                        active,
                        edits,
                        "trial",
                        current_function,
                        current_node,
                    )

                    try:
                        candidate = runtime.trial(
                            result
                        )
                    except ActivationRejected as exc:
                        _attach_runtime(
                            exc,
                            current_function,
                            current_node,
                            "trial",
                        )
                        raise

                    try:
                        answer = _execute(
                            candidate,
                            False,
                            target,
                            arguments,
                            run_token,
                        )
                    finally:
                        candidate.end_trial()

                    stack.append(answer)

                elif op == "FAIL":
                    detail = stack.pop()
                    error_kind = stack.pop()

                    if not isinstance(
                        error_kind,
                        str,
                    ):
                        exc = LanguageError(
                            f"{activation.entity.value}: "
                            f"raise kind must be str"
                        )
                        raise _attach(
                            exc,
                            "language",
                            "wrong_kind",
                            _detail(
                                expected="str",
                                got=kind_of(error_kind),
                                operation="raise",
                            ),
                            current_function,
                            current_node,
                        )

                    if not error_kind:
                        problem = (
                            "raise kind must not be empty"
                        )
                        exc = LanguageError(
                            f"{activation.entity.value}: "
                            f"{problem}"
                        )
                        raise _attach(
                            exc,
                            "language",
                            "malformed",
                            _detail(
                                operation="raise",
                                problem=problem,
                            ),
                            current_function,
                            current_node,
                        )

                    exc = _Raised(
                        f"{activation.entity.value}: "
                        f"{error_kind}"
                    )
                    raise _attach(
                        exc,
                        "program",
                        error_kind,
                        detail,
                        current_function,
                        current_node,
                    )

                elif op == "RAISE":
                    exc = LanguageError(
                        f"{activation.entity.value}: "
                        f"{instr[1]}"
                    )
                    raise _attach(
                        exc,
                        "language",
                        "invalid_code",
                        _detail(
                            problem=instr[1],
                        ),
                        current_function,
                        current_node,
                    )

                else:
                    problem = (
                        f"unknown instruction {op!r}"
                    )
                    exc = LanguageError(
                        f"{activation.entity.value}: "
                        f"{problem}"
                    )
                    raise _attach(
                        exc,
                        "language",
                        "invalid_code",
                        _detail(
                            problem=problem,
                        ),
                        current_function,
                        current_node,
                    )

            except BaseException as exc:
                if _is_host_failure(exc):
                    raise

                error = getattr(
                    exc,
                    "error",
                    None,
                )

                if (
                    not isinstance(error, tuple)
                    or len(error) != 4
                    or getattr(exc, "_shear_run", None)
                    is not run_token
                ):
                    raise

                accepted = None

                for index in range(
                    len(handlers) - 1,
                    -1,
                    -1,
                ):
                    kinds = handlers[index].kinds

                    if (
                        kinds is None
                        or error[1] in kinds
                    ):
                        accepted = index
                        break

                if accepted is None:
                    raise

                handler = handlers[accepted]
                del handlers[accepted:]

                for pending in reversed(
                    live[handler.live_count:]
                ):
                    if not pending.hold.released:
                        pending.hold.release()

                del live[handler.live_count:]
                del stack[handler.stack_height:]
                del control[handler.control_depth:]
                stack.append(
                    ("failed", error)
                )

                (
                    chunk,
                    pc,
                    tail,
                    env,
                    activation,
                    current_function,
                    current_node,
                ) = control.pop()

    except BaseException:
        for pending in reversed(live):
            if not pending.hold.released:
                pending.hold.release()

        raise

    finally:
        _RUN.reset(previous_run)


def run(
    runtime: Runtime,
    entry: EntityID,
    *args: Any,
    may_activate: bool = False,
    resolver: ChunkResolver | None = None,
) -> Any:
    """Evaluate one graph-form function.

    ``resolver`` supplies the chunk of every node the run opens instead of
    lowering it (see ``_RESOLVER``). A run nested in one that has a resolver
    keeps it: no run inside an admitted run falls back to lowering.
    """

    failures = _HOST_FAILURES.set({})
    chunks = None if resolver is None else _RESOLVER.set(resolver)

    try:
        return _execute(
            runtime,
            may_activate,
            entry,
            [
                canonicalize(arg)
                for arg in args
            ],
            object(),
        )
    finally:
        if chunks is not None:
            _RESOLVER.reset(chunks)

        _HOST_FAILURES.reset(failures)
