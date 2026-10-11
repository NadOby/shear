# Handoff

Read `CLAUDE.md`, the Workflow and D3/D4 sections of
`docs/roadmap.md`, and `docs/hosted_pipeline.md`.
Verify this checkpoint against GitHub before relying on it.

## Current state

- Task: 30 – Hosted-bootstrap pipeline.
- Issue: #66.
- Branch: `task/30-hosted-bootstrap`.
- Main baseline: `c1a4596ff555b1f3483b93398a3e8f73fd89bffa`.
- Original protected Plan head: `2f2081b866ca2d686a4cabed3fa4a05a48a31789`.
- First revised Plan head: `94ac037cbcd5e08ed86a3ae6e39c8d20c08f464a`.
- **Current protected Plan head: `fbbb32379c327c1e29f5646e89d30fd1bb8a8084`.**
- Role: Plan revision complete; ready for independent final Plan verification before Execute.
- The subsequent handoff-only commit is not part of the protected Plan baseline.

`docs/hosted_pipeline.md` is authoritative for Task 30.
This handoff is a checkpoint, not architectural authority.

## Settled scope

D3 and D4 remain Decided. The eight owner-approved decisions are unchanged:

1. One SHEAR compiler implementation shared between expanded and node-aware lowering.
2. All 20 specified non-evolution corpus examples, preserving failures and cell effects.
3. `catch` and `raise` included; dedicated error canaries deferred to Task 31.
4. Real G1–G3 compiler generations over unchanged pinned compiler source.
5. Immutable host-provided, version-pinned descriptors; no expanded language reflection.
6. Finite, independently checked, closed G0 compiler seed.
7. Conservative artifact invalidation; cross-activation reuse deferred.
8. Remaining metaprogramming operations deferred unless a real Task 30 dependency is established.

Final text syntax, filename extensions, live evolution and Python removal are outside Task 30.

## Independent Plan reviews and corrections

The first independent review identified four P2 acceptance gaps:

- Unspecified compiler/target source separation.
- Insufficient evidence of genuine G1–G3 rebuilding.
- Insufficiently verified G0 seed closure.
- Missing reconciliation command acceptance.

The first revision addressed these in the specification and tests.

Two subsequent independent reviews found remaining verification gaps and compatibility conflicts. The second revision includes:

- An actual link-rebinding witness: redefine the caller and its link table together, verify the resolved target and compare against ordinary host execution.
- Corpus admission failures cannot satisfy expected `LanguageError` or `CellContentRejected` outcomes.
- G2 and G3 tests observe actual compiler chunks consumed by `machine._open`, comparing object identity against the immediately preceding generation's admitted artifact bindings.
- Negative predecessor-generation invalidation remains required.
- In-process reconciliation testing instruments the CLI's `HostedSession.stage_edit` path and guards `Runtime.activate`, independently checking that the original target runtime remains active.
- Explicit authorization for the known shared-compiler consequences in Task 28's bootstrap-boundary tests, route-A compiler dependencies, mutation-catalog source pins and golden records.
- Separate hosted witnesses required for `applyv` and `linksof`, which are not exercised by the selected corpus.

These are Plan-contract corrections. They do not reopen D3/D4 or expand the agreed Task 30 workload.

## Second revision commits

- `26177c0620784a79d4128f203302fc088a2e65e3` – correct link-rebinding witness.
- `942fe7d5d10520f464f5fa97a6488a4475e5928b` – prevent vacuous corpus failure acceptance.
- `96be6d2fa2ff51ee33826d3e9944d66743a2f805` – verify consumed compiler artifacts and staged edit isolation.
- `297e7e990f53992b50ed0c957a6ef4d8467594e1` – reconcile specification and compiler compatibility obligations.
- `fbbb32379c327c1e29f5646e89d30fd1bb8a8084` – declare expected golden changes.

## Protected Plan-owned files

At the current protected Plan head:

- `docs/hosted_pipeline.md`
- `tests/test_hosted_corpus.py`
- `tests/test_hosted_pipeline.py`
- `tests/test_hosted_safety.py`
- `tests/lanes.py`
- `tests/golden_changes/GH-66.txt`

Execute must not silently weaken acceptance tests or change declared expectations. A material defect in the protected Plan contract returns to Plan.

The expected golden changes are exactly:

- `programs/compiler`
- `programs/bootstrap`
- `programs/instrument`

The declaration must match actual compiler-derived changes during Execute. Any additional, missing or unrelated changes require explicit Plan reconsideration.

## Execute requirements

Implement the revised specification, including:

1. Separate pinned compiler and target canonical states.
2. Unified SHEAR lowering, including `catch` and `raise`.
3. Exact G0 seed manifest and independent closure verification.
4. Authentic G1–G3 generation ancestry, with actual admitted predecessor-code execution.
5. Per-runtime route-B admission, transitive artifact resolution and fail-closed behavior.
6. Complete selected corpus execution, including ordinary failures.
7. Correct dependency invalidation and existing host chunk-cache isolation.
8. Text-source execution and staged reconciliation without activating the candidate.
9. Independent operation witnesses and correctness oracles.
10. Diagnostics, performance measurements, historical evidence preservation and `CHANGES.md`.

Known compatibility work is authorized:

- Adjust `tests/test_bootstrap_boundary.py` for genuinely supported `catch`/`raise` lowering.
- Update `shear/examples/vm.py` dependencies only as needed while preserving route-A behavior.
- Re-review source-pinned mutation survivors for `self_hosting.py` before updating the catalog.
- Reconcile exactly the declared golden-record changes.
- Resolve Task 29's experimental execution-route and mutation-catalog disposition.

Preserve existing semantics. Neither compiler-shaped Python synthesis nor silent host-lowering fallback may be attributed to SHEAR execution.

Tests currently lack the `shear.hosted_bootstrap` implementation and are expected to fail. The golden declaration is also expected to remain unfulfilled until the compiler changes. No successful acceptance run is claimed.

## Independent verification

Before Execute, independently review the latest Plan against the previous findings, particularly:

1. Actual G1/G2 artifact consumption rather than reported ancestry.
2. Reconciliation's independently guarded non-activation.
3. The corrected link-rebinding oracle.
4. Expected failure classification.
5. Golden, mutation-catalog, Task 28 and route-A compatibility allowances.

After Execute, review in a fresh context against protected head `fbbb32379c327c1e29f5646e89d30fd1bb8a8084`.

Verify source preservation, real SHEAR compilation, closed seed membership, authenticated transitive execution, dependency invalidation, complete corpus coverage, independent oracles, ordinary CI and diagnostics.

Classify verified defects, limitations, hypotheses and documentation drift separately. Execute cannot certify itself.

## Next action

Perform a short independent final Plan verification. If no blocking findings remain, start Execute Task 30 (#66) in a fresh chat.

The owner operates from mobile without assistant GitHub write access. Provide complete replacement files, clickable GitHub links and copyable `GH-66` commit messages, one commit at a time. Verify each commit before proceeding.
