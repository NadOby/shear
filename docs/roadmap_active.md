# Active Roadmap

**Status: provisional.** This is the working list of unfinished roadmap
tasks and their dependencies. `roadmap.md` retains Workflow, D1–D5 and
historical task definitions. GitHub issues track execution and ownership;
`CHANGES.md` records architectural results.

Minimize time and implementation needed to reach an architectural decision,
not merely the size of each task. Prefer the shortest decisive experiment
that tests the motivating question. Preserve frozen acceptance, independent
Review, evidence integrity, safety and owner authority.

## Next architectural experiment

### Complete constraint semantics with ordinary SHEAR functions

**Open.** Issue #123. Follows Task 32 (#119, PR #125).

Determine whether ordinary SHEAR functions can implement the complete
existing constraint contract without a separate constraint interpreter.
Test sufficiency, not superiority or mechanism savings.

Use Task 32's restricted execution, adding only the generic canonical-content
access and resource budgeting required. Exercise every existing constraint
form, strong Kleene semantics, relation subjects, Unknown versus host failure
and computation budgets through actual runtime admission paths.

Preserve Task 24's frozen semantic/property oracles and 17 boundary cases.
A positive result establishes bounded equivalence; a negative result names
the smallest reproducible blocker or unacceptable cost; an inconclusive
result identifies the missing discriminator and immediate successor.

Prefer one decisive cross-module experiment over fragmented integration
tasks. Language-shaping decisions remain with the owner.

## Deferred tasks

### 25. Field identity under layout change

**Planned – deferred.** Issue #61. Begin when records are planned.

Scenario: record A `{x, y}`, a reference R to `A.y`, and a running
old-version frame holding R. Activation continues A to A' with layout
`{x, z, y}` and a converter; new code reads `A'.y`, while the old frame
continues under the old state and R has an explicitly defined fate.

Vary moved and deleted fields, split records, ownership changes and
old-version retirement.

Discriminate among independent field identity, record plus selector,
or a logical property independent of layout and access path. Include
planned `ref` values. Model activation and lifetime in Alloy; test
representation and layout in Python.

Done when the scenarios have been tested against recorded predictions
and the result identifies the field-identity model and its requirements
for records.

### 26. Content consolidation decision

**Planned – blocked by Task 25.** Issue #62.

Use Task 23's baseline and the findings of Tasks 24 and 25 to decide
whether unifying `Value` content, relation records and payloads into a
single relational content form is justified.

Require preservation of `EntityID`, reference and ownership semantics
and demonstrate a concrete reduction in mechanisms or conversion paths.

Done when the decision is recorded. A positive decision authorizes
planning a separate refactor, not silently implementing one.

## Unscheduled work

Longer-term possibilities remain in `roadmap.md` under "Later".
They enter this working backlog only when selected for planning.
