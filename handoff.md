# Handoff

## Current state

- Issue: #123 – complete constraint semantics with ordinary SHEAR functions.
- Branch: `task/123-complete-constraints`.
- Original baseline: `f994a2d59b0f6f890f4800effe209d88e1c838c1`.
- Latest verified Plan Resolve: `69e97fee96daf69bba2b0594a5b913b8e7cde5c2`.
- Architecture: independently approved.
- D123-7c read-only semantic inspection: owner-approved.
- D123-8 generic semantic-record construction: owner-approved.
- T5 acceptance: independently approved, 18 modules and 78 tests.
- Candidate implementation: not yet accepted.
- Complete constraint equivalence: unproven.
- No published #123 PR.

The bounded Plan Resolve addresses two contract defects:
unsupported float arguments in the sequence acceptance
suite, and compiler-induced golden-record identity changes.

The float correction is committed.
The narrow golden exception is recorded in
`docs/constraint_functions_complete.md`.

A golden-change declaration must be created during
Execute only for records that actually change.

## Architectural decisions

### D123-7a and D123-7b – Approved

Ordinary SHEAR functions may inspect immutable semantic
structure across all 15 canonical kinds.

Generic `inspect(value)` returns:

    (semantic_kind, original_value)

The original value is retained without eager expansion.

Inspection preserves semantic identity, type, opacity
and authority boundaries.

### D123-7c – Approved

The owner authorized the independently reviewed public
inspection interface in `docs/semantic_inspection.md`.

It includes:

- Generalized `len`, `item` and `slice` for strings,
  bytes, tuples, lists, maps and semantic records.
- String-named record-field access through `item`.
- Exact public Cell, Constraint and Relation schemas.
- Shallow nested-value access.
- Unicode code-point semantics without normalization.
- Canonical-key map ordering.
- Closure opacity and live-cell isolation.
- No new graph, runtime or external authority.

Existing tuple behavior and canonical identity rules
remain unchanged.

### D123-8 – Approved

The owner authorized the independently reviewed generic
semantic-record construction operation:

    record(kind, fields)

Supported record kinds:

- cell
- constraint
- relation

Construction is pure, typed and validated.

Ordinary SHEAR computation determines the kind and
fields. The authenticated VM constructs the immutable
semantic value using existing canonical validation
and normalization rules.

Host-side reconstruction after VM execution is forbidden.

The decision does not authorize:

- A constraint-specific interpreter.
- Python predicate or reconstruction fallback.
- Arbitrary host callbacks.
- Closure construction or reflection.
- Forging opaque identifiers.
- Graph mutation or additional runtime authority.

The normative design is in
`docs/semantic_record_construction.md`.

C10 construction support is authorized but not yet
implemented or demonstrated. Full C10 closure cannot
be inferred merely from implementing `record`.

## Approved acceptance contract

Preserve:

- All 18 candidate-dependent modules and 78 test methods.
- All Task 24 semantic oracles.
- All 17 frozen runtime boundary scenarios.
- Task 32 authentication and security guarantees.
- Existing behavioral expectations and canonical identity rules.
- Approved 1000x warm median and p95 latency ceilings.
- Independent source-path, authority and fallback audits.
- Complete existing corpus and applicable CI lanes.

The candidate-dependent suites remain unexecuted.
Ordinary regression CI is not candidate-equivalence evidence.

### Unsupported float correction

`tests/constraint_functions_sequence_acceptance.py`
distinguishes representable invalid slice bounds from
unsupported host input.

Representable invalid bounds must reach authenticated
SHEAR execution and raise LanguageError.

Floats cannot be canonicalized as SHEAR values and
must be rejected before admitted evaluator entry.

The acceptance method inventory is unchanged.

### Compiler golden-change exception

Compiler extensions may change the canonical identity
of semantic programs containing compiler code.

Expected affected golden records:

- `programs/compiler`
- `programs/instrument`
- `programs/bootstrap`

During Execute, create
`tests/golden_changes/GH-123.txt` declaring individually
only records demonstrated to have changed.

Do not declare an unchanged record.
Do not use `*`.
Do not modify historical declarations.

All unrelated golden identities and behavioral
expectations remain protected.

Regenerate and verify the hosted seed manifest after
the compiler changes.

This exception follows existing golden-checker rules
and the precedent of `GH-67.txt`.

## Decisive integrated experiment

Demonstrate a complete ordinary SHEAR evaluator using
authenticated Task 32 restricted execution:

Raw canonical subject
→ generic semantic inspection
→ ordinary constraint dispatch and composition
→ exact semantic budget accounting
→ Satisfied / Violated / Unknown.

Implement all nine existing constraint forms.

Preserve strong Kleene logic, short circuits, canonical
subjects, exact budgets and host-failure boundaries.

External evaluator composition is the largest remaining
technical uncertainty.

Prioritize an integrated witness for nested External
inside AllOf, AnyOf, Not and Role, checking:

- Correct evaluator selection.
- Exact callback subject.
- Continuation without replay of completed work.
- Correct short circuits and semantic-node accounting.
- Fresh budget per top-level evaluation.
- Exception identity and failure provenance.
- No unauthorized dispatch or hidden fallback.

If the existing authenticated host boundary cannot
support this, demonstrate the smallest counterexample
before requesting any new language authority.

## Runtime integration

The candidate must execute during actual:

- Initial cell and relation admission.
- Successful and rejected writes.
- Successful and rejected activation.
- Isolated trials.

Rejected operations preserve the required live state,
versions, references and artifact bindings.

A standalone evaluator demonstration is insufficient.

## Evidence and verification

Execute must provide:

1. Implemented language, syntax, compiler, VM, verifier
   and restricted-policy changes.
2. Authenticated constructor and evaluator execution.
3. Correct semantic reconstruction for all nine forms.
4. Nested External callback and continuation evidence.
5. Full 18-module, 78-test candidate acceptance.
6. Task 24 oracle and boundary results.
7. Task 32 security and authority regressions.
8. Existing corpus, golden and applicable CI results.
9. Hosted seed-manifest verification.
10. Reproducible latency, allocation, artifact and
    mechanism accounting.

Record exact commits, commands, CI runs, failures and
unexecuted checks.

Independent Review must verify absence of Python
semantic fallback and genuine source-path execution.

## Remaining documentation synchronization

Keep the authoritative acceptance contract in
`docs/constraint_functions_complete_coverage.md`.

Synchronize the capability matrix and any remaining
obsolete approval or golden-record wording without
changing the independently approved acceptance behavior.

Documentation synchronization is maintenance, not
authorization for new language semantics.

## Next actions

1. Finish bounded documentation synchronization.
2. Obtain narrowly scoped independent Resolve review.
3. Execute the approved generic operations and complete
   constraint evaluator.
4. Test nested External callback continuation early.
5. Integrate candidate-backed runtime operations.
6. Run all frozen acceptance, CI and performance checks.
7. Independently review evidence before publication.

The owner retains architectural and publication authority.
