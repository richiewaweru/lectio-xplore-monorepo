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
| G19 | PASS | `pnpm app:test` 264/264 on tip (`tip-app-test.out.txt`; also `p06c-app-test-fix.out.txt`) |
| G20 | PASS | SSE replay/stream reconnect + browser `events_mode=replay` |
| G21 | PASS | Browser competing PUT: 200 then 409; local TAB-B kept |
| G22 | PASS | Full linked journey; PDF `p06c-print.pdf` (88405 bytes) marker extracted |
| G23 | PASS | Learn+Print Idempotency-Key replay; regenerate recovery |
| G24 | PASS | Independent verifier READY — see `VERIFIER-REPORT.md` |

## Focused tests added

- `uv run pytest tests/application/test_p02_admission_stages.py` — `test_g07_failed_terminal_prep_is_not_reused`, `test_g07_regenerate_stale_then_admit_rebinds_identity`
- `tests/print_learn/test_composition_bridge.py` — bare choices without sources fall back to document; bound sources keep `choices`

## Tip SHA (inventoried)

`4af552fe0b7dcfbbda1f88822cdf7fe78ac48fce` (rewritten tip; dropped oversized `p06-validate-after-wire.txt` for GitHub push)

Inventory summary: `docs/lectio-reliability-health/evidence/tip-inventory-summary.json` — all listed commands exit 0, including `validate_repo.py --scope backend` (1416 passed).

## Independent verifier

- **final_verdict: READY** — all G01–G24 PASS.
- G03: first personal `validate_repo` EXIT=1 was sqlite lock flake on `test_d01`/`test_d02` only; serial rerun EXIT=0 (1416 passed) in `verifier-g24-validate-backend-rerun.out.txt`.
- G19: personal `pnpm app:test` 264/264.
- G20–G23: retained live evidence (session now logged out; no new live PASS invented).
- Report: `docs/lectio-reliability-health/tracking/VERIFIER-REPORT.md`.

Do not merge until operators accept READY stamp.
