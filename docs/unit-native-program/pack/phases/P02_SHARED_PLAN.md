# P02 — Implement shared preparation and teaching

Dependencies: P01.
Canonical owners: curriculum, shared contracts and application/unit_lesson.

## Entry
Read the master prompt, contract documents, previous phase report and current STATE.json. Confirm required predecessor gates are PASS at compatible revisions. Record new baseline and run only necessary baseline checks. Any substantive upstream change reopens affected gates.

## Work
1. Split shared resource meaning/skeleton rules from native presentation policies. Remove selected native components and page-document assumptions from fresh Unit preparation.
2. Extract existing instructional teaching model/service from Print ownership into neutral ownership; adapt existing Print calls rather than duplicate the planner.
3. Add learner-action briefs, support/evidence semantics, approved source refs and dependencies. Preserve scope, anchors, optional misconceptions and path-owned objective.
4. Give repeated skeleton occurrences unique IDs; remove first-allowed-component synthesis for added variants. Preserve actuals/prerequisite continuity.
5. Implement typed prompt projections and instructional approval/revision storage; update UI/API handoff without exposing components before native selection.

## Acceptance gates
- [ ] P02-S01: Real Unit preparation produces a shared plan with no native forms/components, including serialized provider request sentinel tests.
- [ ] P02-S02: Objective drift, invented source refs and forbidden scope terms are rejected or repaired explicitly; technical identities are code-owned.
- [ ] P02-S03: Zero misconceptions, procedural/conceptual modes and repeated apply slots preserve intended sequence and stable identities.
- [ ] P02-S04: Both native consumers accept the identical approved teaching revision without fixture substitution or semantic role rewriting.
- [ ] P02-S05: Approved item identity is preserved; source incompatible with task action fails rather than silently changing its assessment.
- [ ] P02-S06: A teaching edit creates a new revision; an old approved revision remains readable and identifiable.

For each gate record a concrete test/command, expected behaviour, actual exit code, fixture identity and evidence location. A assertion of file presence or a mock that bypasses the changed handoff cannot satisfy a behaviour gate. Do not mark every gate passing from one broad test invocation unless its assertions actually cover each gate.

## Deliverables
Shared preparation/teaching models, specs, prompt projections, API migration and semantic contract tests.

## Failure and rollback
Keep last passing revision available. For data changes use additive schema and explicit old-record handling. Do not reset user data or delete unrelated changes. If gate fails, attribute to the responsible stage, repair locally and rerun that gate plus impacted dependencies. If blocked externally, record evidence and next unblock action; proceed with independent permitted work but never label dependent phases complete.

## Exit report
Copy tracking/PHASE_REPORT_TEMPLATE.md; attach per-gate results. Update STATE.json, GATE_RESULTS.csv and decision log. Record implementation commits where repository policy permits. Continue to the next eligible phase without routine confirmation.
