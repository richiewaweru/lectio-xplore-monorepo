# Phase report

Phase: P07 — Finish learner responses, evidence and completion
Status: PASS
Starting commit: `7bec70c` (P06 STATE head) / ending code commits: see implementation commits below.
Dirty files preserved: `.tmp/**`, `apps/textbook-agent/backend/.tmp/*.log`, `apps/textbook-agent/backend/data/` — none committed.

Contract/spec/prompt versions:

| Artefact | Version / note |
|---|---|
| Runtime contract | `pack/contracts/04_RUNTIME_AND_RELEASE.md` (authenticated runtime + progress) |
| Evaluators | `learn/runtime/evaluation.py` — Sequence parity with `@lectio/learn` TS |
| Attempt API | `learn/runtime/runtime_routes.py` — rejects client score/outcome/bindings |
| Analytics scope | `learn/analytics/insight_service.py` — assignment-bound instances only |
| Student bridge | `OrderedBlockList` / `SequenceInteraction` / instance page POST + hydrate |

Dependencies verified: P05 PASS; P06 PASS (`a42be33` / report `7bec70c`).

## Changes and purpose

### Authoritative evaluation (closes LRN-002 / LRN-003)

- New Python evaluators mirror TS `evaluateSequence` (position scoring, unknown/duplicate rejection, partial outcomes).
- `submit_attempt` loads the interaction contract from the immutable release; derives outcome, scores, assessment mode and concept bindings server-side.
- Request body with `outcome` / `score_*` / `concept_bindings` / `assessment_mode` is rejected with 422.

### Persistence bridge (closes LRN-004)

- Sequence Check in production posts authenticated attempts with stable `client_submission_id`.
- GET instance returns `response_json` so refresh restores order + authoritative feedback.
- Preview continues to use local-only evaluation (no production POST).

### Completion, retries, aggregation (closes LRN-005 partially)

- Completion rules `submitted` / `correct` / `score_at_least` applied when rebuilding progress.
- Passive aggregation `first` | `latest` | `best` (default `latest`) prevents score inflation across retries.
- Practice attempts are scored separately from graded totals.
- Passive section completion via `/sections/complete` (and resume `mark_visited`) without inventing graded attempts.
- Idempotency: same key+response replays; same key+different response → 409; max attempts enforced under instance row lock.

### Authorization and analytics (closes LRN-007)

- Instance access checks learner session ownership and assignment recipient when bound.
- Class analytics include only instances linked to that class’s assignments and matching release; self-started instances excluded.

## Gate evidence

All backend commands from `apps/textbook-agent/backend` with `uv run`. Evidence under `docs/unit-native-program/evidence/mocks/p07/`.

| Gate ID | Test or command | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|
| P07-U01 | `...::test_p07_u01_persist_restore_authoritative_feedback` | Correct/incorrect/partial persist; refresh restores response; feedback from server eval | 1 passed, exit 0 | PASS | `u01.txt` |
| P07-U02 | `...::test_p07_u02_reject_forged_scores_unknown_ix_cross_learner` | Forged scores/bindings rejected; unknown ix 404; cross-learner 403; evidence from release only | 1 passed, exit 0 | PASS | `u02.txt` |
| P07-U03 | `...::test_p07_u03_idempotency_conflict_and_max_attempts` | Idempotent replay; conflict on different response; concurrent cannot exceed max | 1 passed, exit 0 | PASS | `u03.txt` |
| P07-U04 | `...::test_p07_u04_completion_rules_and_passive_sections` | submitted/correct/threshold differ; passive complete with zero graded attempts | 1 passed, exit 0 | PASS | `u04.txt` |
| P07-U05 | `...::test_p07_u05_aggregation_and_practice_separation` | first/latest/best without inflation; practice separated | 1 passed, exit 0 | PASS | `u05.txt` |
| P07-U06 | `...::test_p07_u06_analytics_excludes_self_started_keeps_release` | Self-started excluded from class analytics; instance bound to immutable release | 1 passed, exit 0 | PASS | `u06.txt` |

Supporting: `u01-u06-pytest.txt` (7 passed incl. evaluator parity); `legacy-runtime-regression.txt` (18 passed); `evaluator-parity.txt`.

## Failure attribution and repairs

- Builder rejects `learn-interaction:sequence` component ids — gate fixtures remap host `component_id` to `explanation-block` while keeping the contract (D-029).
- Legacy D6C/runtime tests updated off client-score payloads onto Sequence + server evaluation.
- Adversarial suite auth overrides retargeted to `infra.auth` / `infra.database.session`.

## Migration and compatibility

- No DB migration. Attempt rows remain immutable; progress rebuild is additive.
- Clients that still POST scores receive 422 — intentional break of the insecure contract.
- Aggregation default is `latest` when `score_aggregation` is absent on the contract.

## Decisions or deviations

- D-026: Python Sequence evaluator parity-tested against TS goldens (not a separate hand-scored path).
- D-027: Default score aggregation is `latest`; `first`/`best` when declared on the contract.
- D-028: Class analytics scope = assignment-bound instances for that class only (fixes LRN-007).
- D-029: Until interaction component ids are registered, drafts may host Sequence contracts on a registered content component for Builder persistence.

## Remaining risk / blocked access

- LRN-001 (learner vs teacher JWT mix) partially mitigated by session checks when header present; teacher JWT can still act without learner session.
- LRN-006 sequential navigation enforcement still incomplete.
- Non-Sequence interactions remain unmounted in the student renderer; evaluators exist for choice but are not UI-wired.
- Spatial interactions remain unavailable.

## Next phase

P08 (integration) is eligible. Runtime evidence for Learn delivery is now available.

Next command: read `docs/unit-native-program/pack/phases/P08_INTEGRATION.md`.
