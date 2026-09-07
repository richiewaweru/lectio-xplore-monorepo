# P04 — Connect closed native selectors and writer plans

Dependencies: P03.
Canonical owners: print/resources + generation; learn/resources + generation.

## Entry
Read the master prompt, contract documents, previous phase report and current STATE.json. Confirm required predecessor gates are PASS at compatible revisions. Record new baseline and run only necessary baseline checks. Any substantive upstream change reopens affected gates.

## Work
1. Derive per-block candidates from frozen package compatibility, native policy, intent/action, assets, consumer support and budgets.
2. Adapt Print form planner and introduce Learn content/interaction planning over the shared plan. Preserve whole-lesson rhythm through compact briefs.
3. Store selection snapshot/hash and decisions. Validate with exactly the candidate set sent to the provider.
4. Use exact work orders with capability-specific schemas and dependencies. Remove full catalogue and unrelated schema context from prompts.
5. Wire typed new-activity authoring alongside approved item consumption; new payloads stay linked to task briefs and evidence purpose.

## Acceptance gates
- [ ] P04-N01: Compare-without-response selects eligible content without requiring an interaction; reconstruct-order can select Sequence.
- [ ] P04-N02: Out-of-set choice, missing block, duplicate block and altered teaching identity all fail with attributable selection errors.
- [ ] P04-N03: Empty optional interaction set resolves none; empty required capability set reports typed incompatibility and no silent fallback.
- [ ] P04-N04: Writer requests contain only selected payload schema, allowed facts and references; sentinel fields from siblings never leak.
- [ ] P04-N05: Native plan covers every required teaching block and preserves dependencies; unsupported assets prevent premature selection.
- [ ] P04-N06: A native policy change changes eligible choices without editing component definitions or hardcoding new selector branches.

For each gate record a concrete test/command, expected behaviour, actual exit code, fixture identity and evidence location. A assertion of file presence or a mock that bypasses the changed handoff cannot satisfy a behaviour gate. Do not mark every gate passing from one broad test invocation unless its assertions actually cover each gate.

## Deliverables
Print/Learn selectors, closed candidate snapshots, work-order compiler and typed activity authoring.

## Failure and rollback
Keep last passing revision available. For data changes use additive schema and explicit old-record handling. Do not reset user data or delete unrelated changes. If gate fails, attribute to the responsible stage, repair locally and rerun that gate plus impacted dependencies. If blocked externally, record evidence and next unblock action; proceed with independent permitted work but never label dependent phases complete.

## Exit report
Copy tracking/PHASE_REPORT_TEMPLATE.md; attach per-gate results. Update STATE.json, GATE_RESULTS.csv and decision log. Record implementation commits where repository policy permits. Continue to the next eligible phase without routine confirmation.
