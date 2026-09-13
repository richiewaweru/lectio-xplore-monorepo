# P06c Report — G20–G24 live closeout

Phase: P06c (G20–G24 live journey after P06b auth recovery)

## Goal

Clear remaining live gates with one linked Unit→Learn→Builder→Print→PDF run, plus SSE reconnect, two-editor 409, and repeat-admission recovery. No merge/deploy.

## What unblocked Print

1. Prior prep `8a890460-…` ended `failed_terminal` on `choices` PlannedBlock without `source_question_ids` (`orient-b1`).
2. `composition_bridge.py` now falls back to document treatment when assessment treatment lacks sources.
3. `:regenerate` created prep `7206057e-…`.
4. Old Learn/Print realizations collided on unique identity at teaching revision 1 → admission 409. Fixed by marking realizations stale on regenerate and rebinding stale rows on admit when teaching/prep hash changes.
5. Lesson status now reports `generation_id` from `lesson.pack_id` (not superseded Print output id).

## Linked live IDs

See `docs/lectio-reliability-health/evidence/p06c-run-manifest.json`.

## Gate results (implementer)

| Gate | Verdict | Evidence |
| --- | --- | --- |
| G20 | PASS | SSE replay/stream reconnect + browser `events_mode=replay` |
| G21 | PASS | Browser competing PUT: 200 then 409; local TAB-B kept |
| G22 | PASS | Full linked journey; PDF `p06c-print.pdf` (88405 bytes) marker extracted |
| G23 | PASS | Learn+Print Idempotency-Key replay; regenerate recovery |
| G24 | NOT_RUN | Independent verifier; dirty tree |

## Artifacts

- `evidence/p06c-run-manifest.json`
- `evidence/p06c-print.pdf` + `p06c-print-extracted.txt` + `p06c-pdf-meta.json`
- `evidence/p06c-browser-409.json`
- `evidence/p06c-learner-attempt.json` (attempt `434fa0b8-…` correct)
- Screenshots: `p06c-print-studio.png`, `p06c-print-reloaded.png`

## Remaining for READY

1. Commit dirty reliability fixes to a tip SHA.
2. Independent verifier per `prompts/02_VERIFIER.md` reruns command inventory and re-checks G01–G24.
3. Do not merge until READY.
