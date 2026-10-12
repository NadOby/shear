# Handoff

Read `CLAUDE.md`, the Workflow section and task 21 of `docs/roadmap.md`,
issue #58, and `docs/relation_model.md` §2 ("Endpoint arity") and §7. Verify
this checkpoint against GitHub and the repository before relying on it.

## Current state

- Task: #58, task 21: endpoint arity audit.
- Branch: `task/21-endpoint-arity`, from `main` at `a852714`.
- Plan head: `41cd145`.
- Role: Publish done. Two Reviews of PR #112 ran in a separate context:
  - the first found three P3 findings, all fixed (below);
  - the second, at `bbf119f`, accepted the implementation, with one P3
    drift in this file, fixed at Publish.
- Waiting for the owner to merge.
- Plan and Execute ran in one chat, with the owner's permission. The
  evidence below therefore comes from one context and is a claim, not a
  certification. Review must re-derive it.

## Review findings and fixes

1. **P3, PR description held a session link.** Verified: the environment
   appended a footer with the session URL. Fixed: the description was
   rewritten without it.
2. **P3, inventory omits `machine.py` (`LINKS`) and
   `canonical.canonicalize`.** Verified. Fixed: relation_model.md §2 names
   both, in their categories.
3. **P3, the relation_model.md legend lacks Provisional.** Verified. Fixed:
   added "current direction, not fully settled", the wording of
   activation_model.md.

4. **P3, this file's "Changes against the Plan head" left out the legend
   change** (second Review). Fixed at Publish.

No finding is unresolved.

## What Execute did

- **Inventory:** re-derived with the Plan's method (search `shear/` for
  `.roles`, `.endpoints`, `with_endpoints`, `Endpoint`, `role_subject`,
  `_decode_endpoint`, a definition's `.links` and the builder's `scope`).
  Each reader is placed in one category in relation_model.md §2.
- **Spec:** replaced the Open predictions in relation_model.md §2 "Endpoint
  arity" with the result:
  - language relations: redundant but retained (**Provisional**);
  - kinds the core does not interpret: semantically required
    (**Decided**, following from §7 and §9);
  - a tuple where one entity is expected: **Open**, #110.
- **Log:** added the `CHANGES.md` entry.
- **Issues:** filed `follow-up` issues #110 (tuple link targets and
  `function` roles fail closed) and #111 (a code literal holding a
  constraint makes its node a constraint relation; not about arity).

## Changes against the Plan head

- `docs/relation_model.md`:
  - Execute replaced the Open block the contract named; Resolve then named
    two more readers inside that section.
  - Resolve also added Provisional to the status legend near the top,
    outside that block, because the classification uses Provisional and the
    legend lacked it (first Review, finding 3).
- `docs/roadmap.md`: task 21 marked Implemented (PR #112).
- `CHANGES.md`, `handoff.md`.
- `tests/test_endpoint_arity.py` and `tests/lanes.py` are unchanged.
- Nothing under `shear/` changed.

## Evidence

Measured on Python 3.13.

- **Inventory:** the method found all of the Plan's readers, plus:
  - `continuity._node_at`, which assumes `body` is one endpoint;
  - the readers that pass link tables through: `load`, `_edits_of`,
    `_Definition`, `reconcile`, `examples/vm.py`. `define` passes tuple link
    targets through and checks only the `function` role.

  `RelationRewrite` reads its own rewrite pairs, not a relation's roles, so
  it is not a reader.
- **Corpus:** 106 distinct states, 3,865 relation versions, every operation
  kind except `invalid`. No language relation has a role of the wrong arity.
- **Probe for #111:** a function returning `("lit", IsKind("int"))` makes
  `Runtime(load(program))` raise `RelationConstraintRejected` for its node.
- **Checks:** `cross-boundary` lane, `test_docs` and `test_lanes` pass;
  the golden check against `main` shows 55 unchanged, 0 new, 0 changed.

## Claims Review must verify independently

1. `git diff main -- shear/` is empty.
2. The inventory is complete under the stated method.
3. Within one kind and role of a language relation, no reader branches on
   the form.
4. The acceptance tests are not vacuous: re-plant one of the bugs listed in
   `CHANGES.md` and see it fail.
5. Each family's status marker follows from the evidence.
6. Plan-owned files differ from `41cd145` only in the Open block of
   relation_model.md §2.

## Owner decision (non-blocking)

Keep `test_endpoint_arity` permanently (recommended), or keep only the
constraint test.

## Next action

The owner merges PR #112, which closes #58. Follow-ups #110 and #111 stay
open.
