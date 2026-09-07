# P05 — Complete Print from shared teaching to real PDF

Dependencies: P04.
Canonical owners: print generation, visuals, persistence and PDF product route.

## Entry
Read the master prompt, contract documents, previous phase report and current STATE.json. Confirm required predecessor gates are PASS at compatible revisions. Record new baseline and run only necessary baseline checks. Any substantive upstream change reopens affected gates.

## Work
1. Wire approved shared teaching through existing native form/writer/executor machinery. Preserve exact question sources and answer-key ownership.
2. Ensure visual jobs retain stable positions and required asset identity; writer retries never reorder the document.
3. Exercise persistence/reload and actual teacher/student PDF export route, including known hanging-process behaviour. Add bounded timeout/cleanup with visible failure state.
4. Preserve fragmentation/overflow rules, tables, captions and teacher answers. Do not cut meaningful content to pass layout.
5. Keep existing checkpoint/lease safeguards and scoped repair; verify after the shared contract migration.

## Acceptance gates
- [ ] P05-P01: Prepared Unit with approved assessment item reaches persisted valid native document without injected replacement plan.
- [ ] P05-P02: Student PDF hides answers; teacher PDF contains accurate answer key; exported content matches the pinned document.
- [ ] P05-P03: Required figure exists in correct position with valid labels; missing asset is a tracked dependency, not a blank successful output.
- [ ] P05-P04: Long prose/table/atomic boundaries render without clipped content or lost rows; inspect page images.
- [ ] P05-P05: Actual application export route finishes; injected export failure returns actionable state without hung worker.
- [ ] P05-P06: Recoverable writer failure and restart preserve completed siblings and converge to the same validated document.

For each gate record a concrete test/command, expected behaviour, actual exit code, fixture identity and evidence location. A assertion of file presence or a mock that bypasses the changed handoff cannot satisfy a behaviour gate. Do not mark every gate passing from one broad test invocation unless its assertions actually cover each gate.

## Deliverables
Native Print adapter, repaired export lifecycle, PDF evidence and retry tests.

## Failure and rollback
Keep last passing revision available. For data changes use additive schema and explicit old-record handling. Do not reset user data or delete unrelated changes. If gate fails, attribute to the responsible stage, repair locally and rerun that gate plus impacted dependencies. If blocked externally, record evidence and next unblock action; proceed with independent permitted work but never label dependent phases complete.

## Exit report
Copy tracking/PHASE_REPORT_TEMPLATE.md; attach per-gate results. Update STATE.json, GATE_RESULTS.csv and decision log. Record implementation commits where repository policy permits. Continue to the next eligible phase without routine confirmation.
