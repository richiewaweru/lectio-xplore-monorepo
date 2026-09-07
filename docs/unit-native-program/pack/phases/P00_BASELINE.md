# P00 — Establish executable baseline

Dependencies: none.
Canonical owners: Repository tooling, frontend imports, package tests and architecture guidance.

## Entry
Read the master prompt, contract documents, previous phase report and current STATE.json. Confirm required predecessor gates are PASS at compatible revisions. Record new baseline and run only necessary baseline checks. Any substantive upstream change reopens affected gates.

## Work
1. Verify origin and current branch. Record head, working-tree status, database target and package lockfiles. Preserve unrelated changes; use an isolated implementation branch/worktree when needed.
2. Read root/app/package AGENTS instructions and current architecture. Map moved canonical paths; reconcile stale project guidance without reintroducing old ownership.
3. Re-run D6 recorded failed gates at actual head. Repair frontend aliases/import paths, Learn test defects and blocking migration/tooling issues. Do not suppress diagnostics or delete failing tests.
4. Inventory every new interaction shell and existing native contract; classify supported, incomplete, legacy, manual-only and generation-ready. Record evaluator mismatch and spatial-authoring gaps.
5. Create verified command map and test-fixture database policy; choose dedicated test teacher/Unit namespace. No production data reset.

## Acceptance gates
- [ ] P00-B01: App production build and typecheck pass; record full commands and exit codes.
- [ ] P00-B02: Print and Learn relevant package tests pass, including previously failed evaluator tests with correct behaviour assertions.
- [ ] P00-B03: Domain guards pass; current architecture and contributor guidance do not contradict implementation owners.
- [ ] P00-B04: Database migration head is verified against a disposable test DB; missing access yields BLOCKED, not skip-as-pass.
- [ ] P00-B05: All new shells have readiness rows and source locations; no assumed 'complete' from presence of UI alone.

For each gate record a concrete test/command, expected behaviour, actual exit code, fixture identity and evidence location. A assertion of file presence or a mock that bypasses the changed handoff cannot satisfy a behaviour gate. Do not mark every gate passing from one broad test invocation unless its assertions actually cover each gate.

## Deliverables
BASELINE_REPORT.md, COMMAND_MAP.md, CAPABILITY_INVENTORY.json and repaired baseline commits.

## Failure and rollback
Keep last passing revision available. For data changes use additive schema and explicit old-record handling. Do not reset user data or delete unrelated changes. If gate fails, attribute to the responsible stage, repair locally and rerun that gate plus impacted dependencies. If blocked externally, record evidence and next unblock action; proceed with independent permitted work but never label dependent phases complete.

## Exit report
Copy tracking/PHASE_REPORT_TEMPLATE.md; attach per-gate results. Update STATE.json, GATE_RESULTS.csv and decision log. Record implementation commits where repository policy permits. Continue to the next eligible phase without routine confirmation.
