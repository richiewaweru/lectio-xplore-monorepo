# P07 — Finish learner responses, evidence and completion

Dependencies: P06.
Canonical owners: learn runtime/evaluation/evidence/distribution/analytics; student UI.

## Entry
Read the master prompt, contract documents, previous phase report and current STATE.json. Confirm required predecessor gates are PASS at compatible revisions. Record new baseline and run only necessary baseline checks. Any substantive upstream change reopens affected gates.

## Work
1. Wire rendered interactions to authenticated submission and persistence, with stable release/interaction IDs and idempotency.
2. Load authoritative evaluation, assessment mode and concept bindings from release. Remove acceptance of client score/outcome/evidence as authority.
3. Implement declared retry/completion/aggregation rules and passive completion; restore location/response state after refresh.
4. Validate learner/session, assignment recipient, release and instance ownership. Scope class analytics to intended assignments/instances.
5. Use shared evaluator semantics or generated parity-tested backend evaluators. Complete asset-dependent interaction runtime where activated.

## Acceptance gates
- [ ] P07-U01: Correct/incorrect/partial response persists, refresh restores state and UI feedback agrees with authoritative evaluation.
- [ ] P07-U02: Forged score/concept bindings and unknown interaction IDs cannot alter evidence; cross-learner/cross-assignment access rejected.
- [ ] P07-U03: Duplicate submission is idempotent; same key/different response conflicts; concurrent attempts cannot exceed policy.
- [ ] P07-U04: Submitted/correct/threshold completion differ as declared; passive sections complete without fake graded attempts.
- [ ] P07-U05: Retries follow first/latest/best policy as configured without accidental score inflation; practice separated from graded evidence.
- [ ] P07-U06: Self-started unrelated instance excluded from assignment analytics; instance remains bound to original immutable release.

For each gate record a concrete test/command, expected behaviour, actual exit code, fixture identity and evidence location. A assertion of file presence or a mock that bypasses the changed handoff cannot satisfy a behaviour gate. Do not mark every gate passing from one broad test invocation unless its assertions actually cover each gate.

## Deliverables
End-to-end submission bridge, authoritative scoring, completion, authorization and scoped analytics.

## Failure and rollback
Keep last passing revision available. For data changes use additive schema and explicit old-record handling. Do not reset user data or delete unrelated changes. If gate fails, attribute to the responsible stage, repair locally and rerun that gate plus impacted dependencies. If blocked externally, record evidence and next unblock action; proceed with independent permitted work but never label dependent phases complete.

## Exit report
Copy tracking/PHASE_REPORT_TEMPLATE.md; attach per-gate results. Update STATE.json, GATE_RESULTS.csv and decision log. Record implementation commits where repository policy permits. Continue to the next eligible phase without routine confirmation.
