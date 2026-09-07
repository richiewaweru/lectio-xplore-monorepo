# P08 — Prove uninterrupted flows and recovery

Dependencies: P05, P07.
Canonical owners: Cross-domain integration tests and architecture guards.

## Entry
Read the master prompt, contract documents, previous phase report and current STATE.json. Confirm required predecessor gates are PASS at compatible revisions. Record new baseline and run only necessary baseline checks. Any substantive upstream change reopens affected gates.

## Work
1. Replace or supplement D6 fixture-substitution tests with uninterrupted production service chains. External provider mocking remains allowed only when explicitly labelled for deterministic integration.
2. Exercise same shared teaching revision into both native outputs; compare instructional coverage rather than identical payloads.
3. Add stage leakage, stale-write, crash/retry, teacher edit preservation and cross-path isolation tests.
4. Verify all active interactions' package/consumer readiness and serialization parity. Resolve remaining canonical gates without deleting assertions.
5. Prepare real live campaign data and verified commands, ensuring no test-only adapters are needed for user routes.

## Acceptance gates
- [ ] P08-I01: Unit→Print and Unit→Learn integration run without swapping the prepared plan or bypassing selection.
- [ ] P08-I02: Both outputs preserve objective, approved facts, task meaning and required visual/evidence obligations.
- [ ] P08-I03: Stage input sentinels, scoped repair and stale-lease rejection pass; trace locates failures correctly.
- [ ] P08-I04: Teacher edits survive retries/regeneration policy; one native failure does not block ready sibling output.
- [ ] P08-I05: App build/check, native package gates, domain guards and relevant DB integration suites pass on recorded head.
- [ ] P08-I06: Test evidence explicitly identifies mocks; no live claim derives from deterministic tests.

For each gate record a concrete test/command, expected behaviour, actual exit code, fixture identity and evidence location. A assertion of file presence or a mock that bypasses the changed handoff cannot satisfy a behaviour gate. Do not mark every gate passing from one broad test invocation unless its assertions actually cover each gate.

## Deliverables
Integrated acceptance suite, command map, recovery evidence and live-ready runbook.

## Failure and rollback
Keep last passing revision available. For data changes use additive schema and explicit old-record handling. Do not reset user data or delete unrelated changes. If gate fails, attribute to the responsible stage, repair locally and rerun that gate plus impacted dependencies. If blocked externally, record evidence and next unblock action; proceed with independent permitted work but never label dependent phases complete.

## Exit report
Copy tracking/PHASE_REPORT_TEMPLATE.md; attach per-gate results. Update STATE.json, GATE_RESULTS.csv and decision log. Record implementation commits where repository policy permits. Continue to the next eligible phase without routine confirmation.
