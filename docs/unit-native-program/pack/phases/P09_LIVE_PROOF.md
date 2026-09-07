# P09 — Run and inspect both product paths live

Dependencies: P08.
Canonical owners: Casa/Grok executing authenticated product workflow and evidence review.

## Entry
Read the master prompt, contract documents, previous phase report and current STATE.json. Confirm required predecessor gates are PASS at compatible revisions. Record new baseline and run only necessary baseline checks. Any substantive upstream change reopens affected gates.

## Work
1. Follow verification/LIVE_PROTOCOL.md using real configured providers, real test DB and authenticated product UI.
2. Create test Unit/path, approve instructional work, produce both native outputs for the same shared lesson revision. Do not inject finished plans or documents.
3. Run four contrasting lesson cases with Print and Learn output; inspect PDF pages, interact as student and verify persistence/release identity.
4. Exercise one controlled recoverable failure and one teacher edit/new release. Capture latencies and real failure traces.
5. Report acceptance separately for core dual paths and full interaction catalogue. Unavailable credentials/provider/browser access is BLOCKED; finish other available evidence.

## Acceptance gates
- [ ] P09-V01: All four case rows have real run IDs, pinned plan hashes, native output IDs, provider/model IDs and timestamps.
- [ ] P09-V02: Each Print output passes semantic review and visual PDF inspection through product export route.
- [ ] P09-V03: Each Learn output is generated, edited/previewed/published and completed through UI with persisted authoritative results.
- [ ] P09-V04: Same-plan fidelity holds across both paths; stage timings/failures/retries documented without invented performance claims.
- [ ] P09-V05: Controlled recovery succeeds without replacing successful blocks; old release survives new draft/release.
- [ ] P09-V06: Final report lists every enabled/deferred interaction and honest PASS/FAIL/BLOCKED decisions with evidence links.

For each gate record a concrete test/command, expected behaviour, actual exit code, fixture identity and evidence location. A assertion of file presence or a mock that bypasses the changed handoff cannot satisfy a behaviour gate. Do not mark every gate passing from one broad test invocation unless its assertions actually cover each gate.

## Deliverables
Live campaign evidence, final acceptance report, residual debt and implementation handoff.

## Failure and rollback
Keep last passing revision available. For data changes use additive schema and explicit old-record handling. Do not reset user data or delete unrelated changes. If gate fails, attribute to the responsible stage, repair locally and rerun that gate plus impacted dependencies. If blocked externally, record evidence and next unblock action; proceed with independent permitted work but never label dependent phases complete.

## Exit report
Copy tracking/PHASE_REPORT_TEMPLATE.md; attach per-gate results. Update STATE.json, GATE_RESULTS.csv and decision log. Record implementation commits where repository policy permits. Continue to the next eligible phase without routine confirmation.
