# Handoff

Read `CLAUDE.md`, the Workflow section of `docs/roadmap.md`, roadmap task 22,
issue #59 and `docs/reference_model.md` §14. Verify this checkpoint against
GitHub and the repository before relying on it.

## Current state

- Issue: #59 (`task`), roadmap task 22, reference version audit.
- Branch: `task/22-reference-version`, from `main` at `1db6d5e`.
- Role: Plan and Execute done, in separate chats; the owner chose D22
  option 1. Next: Review.
- Plan head: `b7123c3a0ff3adb951c60dc65e5dc155a354ce5c` ("Change handoff.md
  to record the owner's D22 choice"). Review diffs the Plan-owned files from
  it. Execute head: the commit that records this file.

## Result of the audit (Plan)

`VersionID` in a state-pinned `Reference` is redundant: `StateID` hashes
every entity's `VersionID` (state_model.md §4), every producer derives the
version from the named state, and `resolve` and `transfer_reference` check
the state first. `StaleReference` needs a hand-built reference. No
production reader uses the version for anything else, and the language
never sees a `Reference`, `VersionID` or `StateID`.

With the planned `ref` values (Later), the version stays redundant as long
as a `ref` carries a `StateID`. It does work only if the `ref` design drops
the state from the reference, resolves across states, or makes `StateID`
partial. New constraint found: a reference held in semantic content cannot
contain the `StateID` of its own state, nor its own entity's `VersionID`.

## Decision (owner, D22)

Option 1, chosen 2026-10-12. How to classify the version, given the
evidence. No refactor either way.

1. **Redundant, kept until the `ref` design chooses the reference form**
   (recommended, written in §14 as Provisional). The `ref` design may move the
   version into the key rather than drop it, so removing it now risks churn.
2. Retained deliberately as an integrity witness. Not recommended: it catches
   only a triple whose parts disagree, not a forged reference.
3. Redundant, removed now: a follow-up issue for the refactor (`Reference`,
   `make_reference`, `resolve`, `transfer_reference`, `StaleReference`, about
   ten tests). Not recommended before the `ref` design.

§14 already states option 1; it needs no change.

## Plan-owned files

- `docs/reference_model.md`: §2 and §5 say when a stale reference can arise;
  new §14 holds the classification, evidence, roles checked, the `ref`
  premises and the content constraint.
- `docs/roadmap.md`: the Later item for `ref` values points to §14.
- `tests/test_reference_version.py` (new, lane `cross-boundary`), three tests
  over 150 generated states and transformations and the 21 continuity cases:
  - state and entity determine the version of every produced reference
    (`State.reference`, `transfer_reference`, `rebind_reference`);
  - a produced reference never fails the version check in `resolve` or
    `transfer_reference`, including against an independently rebuilt equal
    state;
  - a hand-built reference with another version is stale.
  These are characterization tests: they pass on `main`. Planted bugs, each
  caught: transfer keeping the source version, a `StateID` that ignores
  versions, `make_reference` deriving a wrong version.
- `tests/lanes.py`: one line.
- Golden: none declared. Measured against `main`: 55 unchanged, 0 new,
  0 changed.

## Execute (done)

- Implemented exactly the Plan's steps: the Plan head is recorded above, §14
  is untouched, and the `CHANGES.md` entry is appended as the Plan wrote it.
  Nothing under `shear/`, no Plan-owned file and no test expectation changed;
  the only files Execute touched are `CHANGES.md` and this one. No
  provisional choices were made, no mutation campaign was run (nothing under
  `shear/` changes), and no survivor decisions arise.
- Verification, on the Plan head plus these two files, Python 3.13:
  - `python3 -m tests.lanes --all`: all eight lanes ok (the longest,
    `cross-boundary`, 64 s), run on the final tree.
  - `python3 -m tests.golden --against main` (`main` at `1db6d5e`): 55
    unchanged, 0 new, 0 changed.
  - The three planted bugs, in a scratch copy, each make
    `tests.test_reference_version` fail, and the unplanted copy passes:
    transfer keeping the source version (76 failures, 75 errors); a `StateID`
    that ignores versions (9, 9); `make_reference` deriving a wrong version
    (33, 312).
- Not checked: issue #59 itself (GitHub issue reads were refused in this
  session); the contract was taken from this file and the roadmap entry.

Execute does not certify the audit. If its argument is wrong, return to Plan.

## Claims Review must verify independently

1. `StateID` covers every entity's `VersionID`: `_state_content` takes all
   values, `StateID` cannot be supplied, and no path builds a `State`
   without deriving it.
2. Production code reads `Reference.version` only in `State.resolve` and
   `transfer_reference`; the language (`lang`, `bytecode`, `machine`) never
   constructs a `Reference`, `VersionID` or `StateID` value.
3. The tests' oracle is independent: expected versions come from the
   states' values, not from the references under test, and the transfer
   route is actually exercised (the corpus yields results for 20 of 21
   cases).
4. §14's content constraint is correct, including that a cell's declared
   initial content is state content and its current content is not.

## Limitations and notes

- The argument assumes SHA-256 has no collisions, as state identity does.
- `tests/test_references.py::test_version_fast_path_for_exact_value`
  compares two states with equal content, so one `StateID`; it shows no
  cross-state use. Left unchanged (owner's test); rename only if the owner
  wants.
- Hosted-bootstrap descriptors carry `(state_id, node, version)` with the
  same redundancy inside one pinned state; their artifact key
  `(entity, version)` is deliberate for reuse across activations (task 31).
  Out of scope: they are not `Reference`.
- CI fails on the commit between adding the test module and its lane entry;
  it passes once both are on the branch.

## Next action

Review task 22, in a fresh chat.
