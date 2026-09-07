# P03 — Separate native output identity and state

Dependencies: P02.
Canonical owners: application/unit_lesson, native generation admission, DB and status APIs.

## Entry
Read the master prompt, contract documents, previous phase report and current STATE.json. Confirm required predecessor gates are PASS at compatible revisions. Record new baseline and run only necessary baseline checks. Any substantive upstream change reopens affected gates.

## Work
1. Introduce explicit requested output(s) and independent native realization identities with the fields in contracts/03_REALIZATIONS_AND_EXECUTION.md.
2. Adapt existing generation rows or add minimal additive tables. Shared plan and native output revisions must be distinguishable; unique idempotency constraints must be transaction-safe.
3. Replace environment-default/contradictory marker routing for new runs with persisted native identity. Keep historical rows readable without silently executing ambiguous records.
4. Update status/open/retry endpoints and Unit UI to select the correct Print/Learn output; preserve both links for one lesson.
5. Implement stale detection and dependent invalidation, including variants, native policy/hash changes and independent path regeneration.

## Acceptance gates
- [ ] P03-R01: One lesson creates both outputs; duplicate requests resolve idempotently without extra rows.
- [ ] P03-R02: Print retry/regeneration does not change Learn output/release or shared plan; inverse also proven.
- [ ] P03-R03: Restart and changed default configuration cannot switch a persisted realization's native path.
- [ ] P03-R04: Changing shared revision marks appropriate outputs stale; old output/release snapshots remain intact.
- [ ] P03-R05: Migration upgrades from existing test fixtures; ambiguous legacy data gets explicit read-only status, not guessed provenance.
- [ ] P03-R06: Concurrent realization creation respects uniqueness; status/open routes identify correct native artifact.

For each gate record a concrete test/command, expected behaviour, actual exit code, fixture identity and evidence location. A assertion of file presence or a mock that bypasses the changed handoff cannot satisfy a behaviour gate. Do not mark every gate passing from one broad test invocation unless its assertions actually cover each gate.

## Deliverables
Migration, realization identity contract, explicit routing and UI/status integration.

## Failure and rollback
Keep last passing revision available. For data changes use additive schema and explicit old-record handling. Do not reset user data or delete unrelated changes. If gate fails, attribute to the responsible stage, repair locally and rerun that gate plus impacted dependencies. If blocked externally, record evidence and next unblock action; proceed with independent permitted work but never label dependent phases complete.

## Exit report
Copy tracking/PHASE_REPORT_TEMPLATE.md; attach per-gate results. Update STATE.json, GATE_RESULTS.csv and decision log. Record implementation commits where repository policy permits. Continue to the next eligible phase without routine confirmation.
