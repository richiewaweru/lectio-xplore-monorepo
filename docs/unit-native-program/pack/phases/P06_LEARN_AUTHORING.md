# P06 — Complete Learn generation, ordered rendering and publishing

Dependencies: P04.
Canonical owners: @lectio/learn runtime contracts; learn generation/authoring/publishing; student renderer.

## Entry
Read the master prompt, contract documents, previous phase report and current STATE.json. Confirm required predecessor gates are PASS at compatible revisions. Record new baseline and run only necessary baseline checks. Any substantive upstream change reopens affected gates.

## Work
1. Produce validated activity payloads and content blocks using package-defined contracts; carry concept, assessment, feedback and completion metadata.
2. Render authoritative ordered block instances, including repeated types and interleaving. Remove lossy SectionContent reconstruction from paths where it collapses order.
3. Connect package-derived Builder editors for interaction configs, answers and assets. Round-trip unknown legacy fields only under an explicit compatibility contract.
4. Preview uses same renderer and isolated non-persisting attempts. Keep draft edits independent of published snapshots.
5. Implement full publish validation, pinned source provenance, transactional release numbering and explicit immutable release versions.

## Acceptance gates
- [ ] P06-L01: Generated lesson contains at least one new interaction through normal selector/writer flow, not a manually injected payload.
- [ ] P06-L02: Repeated same-type blocks and content→activity→content order survive assemble/Builder/reload/render.
- [ ] P06-L03: Builder edit changes task/answer config validly and persists; malformed config or dangling references blocks publish.
- [ ] P06-L04: Preview interactions create zero production attempts/evidence and do not mutate a published release.
- [ ] P06-L05: Publish v1, edit, publish v2: v1 data/hash unchanged; concurrent publishing/idempotency tested.
- [ ] P06-L06: Publishing an old draft after PathLesson revision change never stamps false current provenance; explicit policy enforced.

For each gate record a concrete test/command, expected behaviour, actual exit code, fixture identity and evidence location. A assertion of file presence or a mock that bypasses the changed handoff cannot satisfy a behaviour gate. Do not mark every gate passing from one broad test invocation unless its assertions actually cover each gate.

## Deliverables
Ordered Learn output, interaction authoring, unified preview renderer and validated immutable publishing.

## Failure and rollback
Keep last passing revision available. For data changes use additive schema and explicit old-record handling. Do not reset user data or delete unrelated changes. If gate fails, attribute to the responsible stage, repair locally and rerun that gate plus impacted dependencies. If blocked externally, record evidence and next unblock action; proceed with independent permitted work but never label dependent phases complete.

## Exit report
Copy tracking/PHASE_REPORT_TEMPLATE.md; attach per-gate results. Update STATE.json, GATE_RESULTS.csv and decision log. Record implementation commits where repository policy permits. Continue to the next eligible phase without routine confirmation.
