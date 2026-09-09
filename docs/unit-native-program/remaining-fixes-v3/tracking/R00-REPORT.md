# R00 Report — Reopen gates and reproduce

Status: PASS  
Tested commit: `db157f00731602c35ec1ec1e71fd5cc5d21e655b`  
Branch: `feat/unit-print-learn`

## Summary

R00 recorded the db157f0 baseline, mapped normal Print and Learn production callers, reopened unsupported Authoring Correction v2 A02/A04/A05/A06 PASS claims without deleting historical evidence, and added five focused regressions under `tests/remaining_fixes/` that fail on current HEAD for the intended R1–R4 defect reasons. No product fixes were implemented.

## Gate results

| Gate | Result | Evidence |
| --- | --- | --- |
| R00-G01 | PASS | `tracking/R00-BASELINE.md`, `tracking/R00-CALLER_MAP.md` |
| R00-G02 | PASS | `tests/remaining_fixes/` → `evidence/r00/pytest-r00-all.txt` (5 failed) |
| R00-G03 | PASS | v2 `GATE_RESULTS.csv` + A02/A04/A05/A06 report reopen banners |

## Regression failures (intended on db157f0)

| Test | Failure reason |
| --- | --- |
| `test_r00_numeric_generate_preserves_provider_question_feedback_and_facts` | `interaction_contract_from_authoring_result` sets `prompt` from planning brief instead of provider-authored student question |
| `test_r00_no_ref_work_order_does_not_bind_first_pool_item` | `run_learn_authoring` selects `convert-approved` when `approved_items[0]` exists despite empty `approved_item_ids` |
| `test_r00_explicit_q2_excludes_q1_sentinel_from_model_visible_inputs` | conversion inputs include full approved pool; q1 sentinel leaks into model-visible JSON |
| `test_r00_build_closed_learn_production_passes_preparation_facts` | `build_closed_learn_production_async` hardcodes `allowed_facts=[]` |
| `test_r00_ambiguous_shortlist_uses_model_selector_not_keyword_rank` | `build_learn_selection_snapshot` picks keyword `ranked[0]` (`summary-block`) instead of semantic selector choice (`explanation-block`) |

## v2 reopen

- Updated `authoring-correction-v2/tracking/GATE_RESULTS.csv`: A02, A04, A05, A06 gates → `REOPENED`
- Updated `authoring-correction-v2/tracking/STATE.json`: status `A06_REOPENED_BY_R00`
- Prepended reopen notes to `A02-REPORT.md`, `A04-REPORT.md`, `A05-REPORT.md`, `A06-REPORT.md`
- Historical evidence paths unchanged and labelled historical in gate notes

## Commands

```powershell
cd apps/textbook-agent/backend
uv run pytest -q tests/remaining_fixes/
```

Exit: 5 failed in 0.28s (expected on db157f0)

## Next phase

R01 is unblocked for product fixes to complete interaction authoring (R1). R00 regressions should flip to PASS as R01–R04 land.
