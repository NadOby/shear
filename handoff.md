# Handoff

Read `CLAUDE.md`, the Workflow section of `docs/roadmap.md`, issue #111 and
`docs/relation_model.md` §7. Verify this checkpoint against GitHub and the
repository before relying on it.

## Current state

- Issue: #111 (`follow-up`): a constraint in a code node's payload made the
  node a constraint relation.
- Branch: `fix/111-constraint-payload`, from `main` at `1de2510`.
- Role: Plan and Execute done in one chat, with the owner's permission. An
  independent Review accepted the fix, with three findings; Resolve is done
  (below). Waiting for the mutation campaign, then the PR.

## Decision (owner)

The endpoint rule: a relation is a constraint relation
only if its payload is a constraint and it has at least one endpoint
(relation_model.md §7, Decided). Rejected:

- wrapping literal payloads, which would change nearly every program's
  identity;
- forbidding constraint literals, which restricts the language for nothing.

## Review findings and fixes

1. **P2, no campaign confirmed the `relations.py` repin.** A campaign is
   dispatched on this branch with a small `mutation_count`. The plan job
   turns revalidation on itself, because the survivor catalog differs from
   `main`.
2. **P3, the decision comment on #111 said "option 1"**, which is a
   different rule in the issue body. Fixed: the comment now says "the
   endpoint rule" and names the difference.
3. **P3, the wrapped-constraint hazard was untested.** Fixed: a new test in
   `test_constraint_relations.py` checks it.
   - A bare constraint payload on a relation with an endpoint is enforced.
   - The same constraint wrapped in a tuple or a map is data.
   - The test catches a planted rule that looks inside wrappers.
   - It is a characterization test, not a regression test: it passes on
     `main` too.

## Changes

- `shear/relations.py`: one condition in `constraint_relations`, plus its
  docstring.
- `docs/relation_model.md` §7: the rule, why code needs it, and the
  consequences; the §10 status line.
- `CLAUDE.md`: the model map line for `relations.py`.
- `tests/test_data_is_opaque.py` (new, lane `language-runtime`).
- `tests/test_constraint_relations.py`: two new recognition tests. No
  existing test was edited.
- `tests/lanes.py`: one line.
- `tests/mutation_catalog_data/shear/relations.toml`: `source_blob`
  repinned to `eab7f94`. Both survivors (`@dataclass(frozen=True,
  eq=False)` and `return NotImplemented` in `Relation.__eq__`) were
  re-reviewed: the diff touches only `constraint_relations`, so both
  classifications still hold.
- `CHANGES.md`.

## Evidence

Measured with Python 3.13.

- **On `main` (without the fix):** the new tests fail:
  - the `constraint` exemplar as a literal, quoted, and in activated code;
  - a constraint used as a parameter name;
  - the recognition test.
- **Planted bug:** `relation.roles` instead of `relation.endpoints` fails
  the quoted route and the recognition test, so the empty-tuple case is
  covered.
- **With the fix:** all eight lanes pass, and the golden check against
  `main` shows 55 unchanged, 0 new, 0 changed.

## Claims Review must verify independently

1. No language relation with endpoints can hold a bare constraint payload.
   Check every payload `lang._Builder._relation` writes, and `fold`.
2. Before the rule, a relation without endpoints and with a constraint
   payload could only reject a load or activation, or check nothing. So the
   only behaviour change is that such states are now accepted.
3. The exemplars cover every kind `constraints.KINDS` names, plus
   `function`. The routes cover every node that can carry program data in
   its payload (`lit`, `quote`, `arg`), plus a cell, a tuple and activated
   code.
4. The repin is justified: the survivors' lines are unchanged.

## Limitations

- The rule rests on the language's current shapes: a future operation with
  endpoints and a data payload must keep its payload from being a bare
  constraint. The opaque test catches that only if a route for that
  operation is added.
- A constraint stored as data in a relation with endpoints is still
  enforced unless it is wrapped; the spec now says so.

## Next action

When the campaign is green, open the PR closing #111.
