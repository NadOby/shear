# Handoff

Read `CLAUDE.md`, the Workflow section and task 21 of `docs/roadmap.md`,
issue #58, and `docs/relation_model.md` §2 ("Endpoint arity") and §7. Verify
this checkpoint against GitHub and the repository before relying on it.

## Current state

- Task: #58, task 21: endpoint arity audit. One session.
- Branch: `task/21-endpoint-arity`, from `main` at `a852714`.
- Role: Plan done. Plan head: the commit that adds this file (check with
  `git log -1 -- handoff.md`). Next: Execute.

## Scope

Required, with no change under `shear/`:

1. Complete the inventory below: every reader in `shear/` of relation roles
   or of the link table derived from them. Method: search `shear/` for
   `.roles`, `.endpoints`, `with_endpoints`, `Endpoint`, `role_subject`,
   `_decode_endpoint`, `.links` of a definition and the builder's `scope`.
   Put each reader in one category (A–D).
2. Replace the **Open** block of relation_model.md §2 "Endpoint arity" with
   the result. Classify each family with a canonical marker (Decided or
   Provisional), give the evidence by file and function, say whether each
   prediction held, and give the corpus numbers.
3. Append a `CHANGES.md` entry.
4. Give the follow-up issue text below to the owner (or file it with write
   access).

Not in scope: normalizing endpoints, a role schema for kinds, changing how
tuple link targets are handled, or editing `operations.py`.

## Plan-owned files

`tests/test_endpoint_arity.py`, the one line in `tests/lanes.py`, and
`docs/relation_model.md` outside the Open block named above. No golden
declaration: no record should change. If the golden check reports a change,
stop and return to Plan.

## Inventory (Plan's claims to verify)

- **A. Representation (keeps the two forms apart):**
  `relations._normalize_endpoint`, `Relation.canonical_node`,
  `relation_of`/`_decode_endpoint`, `canonical.canonicalize`.
- **B. Flatten (arity-blind):**
  - `Relation.endpoints`; `with_endpoints`, which keeps the shape;
    `check_relation_endpoints`; `relation_index`;
  - `transforms` (`_follow_relation_endpoints`, `_validate_relation_rewrites`,
    `rebase`); `runtime._failed_constraint_relation` (`touching`);
  - `matching._items` (in `shapes` and `match.pair`); `continuity._operands`;
    `fold` (`children`); `lang._subtree`;
  - `hosted_bootstrap.seed`; `hosted_bootstrap.validation._endpoints`.
- **C. Assume the declared arity (code relations):**
  - `bytecode.lower` and `_lower_activation`; `lang._collapse`;
    `lang._read_definition`; `fold` role reads;
  - `hosted_bootstrap.descriptors._operands`, which splices ordered roles,
    so the self-hosted compiler never sees a role;
  - `validation` `_COUNTED`, which calls `len` on the role.
- **D. Branch on arity:**
  - `relations.role_subject`: a tuple role becomes a tuple of contents in a
    constraint subject. Semantic.
  - Link targets:
    - `_Builder.resolve` raises "does not name a single entity", untested;
    - the machine's `LINKS` omits tuple targets, as documented in
      vm_in_shear §1;
    - `syntax.printer` omits them silently, so the text round trip drops
      the link;
    - `reconcile` compares link targets exactly.
  - A links relation's `function` role:
    - `load` finds the relation through the flattened index, so
      `function: (f,)` loads and runs;
    - `define` (`_edits_of`) and `reconcile` (`_input_links`) reject it;
    - the parser's `_merge` ignores it.

## Evidence so far

Measured on `main` `a852714` with Python 3.13.

- **Probes:**
  - `{r: a} != {r: (a,)}`, with different `VersionID`s.
  - A call through a `(g,)` link raises `LanguageError`; `linksof` omits the
    link; `render_program` drops it.
  - `matching.shapes` gives a one-argument `call` the same shape number with
    `args: x` and with `args: (x,)`.
  - `Role("r", IntRange(0, 9))` over cell content 5 is Satisfied for
    `{r: c}` and Violated for `{r: (c,)}`.
  - `load` accepts `function: (f,)`; `define` rejects it.
- **Corpus:** 127 steps; 70 entities created by runs; 4134 role values in
  post-run states, 293 of them one-element tuples, all of the declared
  arity. Every kind that has roles appears, except `links` after loading,
  since `load` removes links relations.
- **Planted bugs:** each makes `test_endpoint_arity` fail:
  - a one-argument `call` storing one endpoint;
  - `activate` with one target storing one endpoint;
  - `role_subject` flattening a one-element tuple.
- **Runs:** `cross-boundary` lane with the new module: 210 tests, about 52 s,
  OK.

## Acceptance

- `tests/test_endpoint_arity.py` passes unchanged; the full suite and the
  golden check pass; `git diff main -- shear/` is empty.
- The relation_model section classifies each family with a canonical marker,
  file-and-function evidence and the prediction outcomes.
- The inventory is complete under the stated method.

## Claims Review must verify independently

1. Nothing under `shear/` changed.
2. The inventory is complete: re-derive it with the stated method.
3. Within one kind and role of a language relation, no reader branches on
   arity. Category D's link items concern a tuple where one endpoint is
   expected, which the language never builds.
4. The acceptance tests are not vacuous: re-plant at least one of the bugs
   above.
5. Each family's status follows from the evidence: required where a reader
   observes the distinction with no other carrier, retained where it is
   derivable but kept for uniform readers.

## Provisional choices (Plan)

- Link-target role arities live in a test-local table (`LINK_TARGET_ROLES`),
  not in `operations.Shape`, so there is no production change. The test
  fails closed: an undeclared role, or a relation kind in a corpus state
  that `declared()` does not classify, fails it.
- The new module runs in the `cross-boundary` lane, because it runs both
  corpora.

## Owner decision (non-blocking)

Keep `test_endpoint_arity` permanently (recommended: about 2.5 s; it guards
the arity assumption that matching, lowering and `function_at` rely on), or
use it once as audit evidence and keep only the constraint test.

## Follow-up issue (`follow-up` label)

Title: "Fail closed on a tuple link target or links `function` role".

Body: A links relation may hold a tuple where the language expects one
entity, which only the Python API can build, and consumers disagree:
- `_Builder.resolve` raises when the link is used;
- `linksof` and `render_program` omit the link silently;
- `load` accepts `function: (f,)` while `define` and `reconcile` reject it.

Pick one rule, for example that `load` and `define` reject it as they reject
a second links relation, and test it. Found in task 21 (#58).

## Next action

Execute task 21.
