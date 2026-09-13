# C05 Report

## Experiments

| Gate | Evidence | Result |
| --- | --- | --- |
| T01 | `test_t01_fresh_process_reuses_committed_checkpoint` | PASS |
| T02 | `test_t02_ambiguous_reserve_survives_restore` | PASS |
| T03 | `test_t03_exhausted_budget_is_durable_terminal` | PASS |
| T04 | `test_t04_concurrent_claims_admit_one_owner` | PASS |
| T05 | `test_t05_renewals_keep_ownership_past_short_lease` (lease_seconds=1 + renewals) | PASS |
| T06 | `test_t06_expired_lease_allows_takeover_and_blocks_old_persist` | PASS |
| T07 | `test_t07_cancel_blocks_persist_and_dispatch` | PASS |
| T08 | `test_t08_incompatible_ready_reuse_does_not_reset_budget` | PASS |
| T09 | `test_t09_indexed_node_ids_unique_and_collision_raises` | PASS |
| T10 | `test_t10_partial_ready_resume_reuses_one_item` | PASS |
| T11 | `test_t11_progress_events_survive_restart` | PASS |
| T12 | `evidence/t12-live-manifest.json` live Teaching Plan → Learn edit/publish/attempt + Print edit/PDF | PASS |

## Commands

```
cd apps/textbook-agent/backend
$env:PYTHONPATH='src'
uv run pytest tests/reliability/test_correction_pass.py -q --tb=line
# => 19 passed, 1 deselected
uv run pytest tests/reliability/test_correction_pass.py -m postgres -q --tb=short
# => 1 passed
```

## Live T12 summary

- Prep regenerate + teaching approve for Learn on unit `907b1dab-…`
- Learn generate `learn-out-c33ae7530662` (200)
- Builder edit marker on `learn-node:explain-b1:paragraph:3`; publish release `41a2e657-…`
- Learner attempt 200 / correct on `learn-node:orient-b1:choice:13`
- Print lectio-document edit marker + PDF export 232484 bytes `application/pdf`
- Sibling independence: Print document does not contain Learn marker

## Gate

PASS
