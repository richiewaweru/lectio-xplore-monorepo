# A05 Report — Selection and upstream ownership

> **R00 reopen (2026-09-09, reviewed HEAD `db157f0`):** A05 gates are **REOPENED**. Historical PASS evidence under `evidence/a05/` is preserved as historical only. Production selection uses keyword `rank_learn_*_candidates[0]` without configured model selector on current HEAD.

Status: REOPENED (historical report below recorded PASS at prior HEAD)

## Summary
Backend semantic fallback maps were removed. Learn eligibility no longer reincludes content via `INTENT_CONTENT_FALLBACKS` when the closed shortlist is empty. Print production selection ranks forms with package guidance instead of tuple index zero. Learn production selection ranks content capabilities with the same choose_when / reject_when mechanism already used for interactions.

Out-of-shortlist decisions remain rejected by validators. Budget-, readiness- and policy-excluded candidates stay excluded. Teaching-stage compatibility checks continue to fail closed on incompatible approved sources; order-items blocks keep empty source lists unless teaching supplies them.

## Gates
- A05-G01 PASS: `test_a05_g01_semantic_selector_and_sole_candidate`
- A05-G02 PASS: `test_a05_g02_out_of_set_rejected_and_reorder_invariant`
- A05-G03 PASS: `test_a05_g03_required_interactions_persist_optional_explicit_none`
- A05-G04 PASS: `test_a05_g04_fallback_cannot_restore_excluded_candidates`
- A05-G05 PASS: `test_a05_g05_missing_source_fails_at_owning_stage`
- A05-G06 PASS: `test_a05_g06_shared_teaching_revision_across_paths`

## Evidence
- `docs/unit-native-program/authoring-correction-v2/evidence/a05/backend-a05-tests.txt`

Validation commands:
- `cd apps/textbook-agent/backend; uv run pytest -q tests/authoring_correction/test_a05_selection.py tests/authoring_correction/test_a00_first_content_selection.py tests/authoring_correction/test_a00_fallback_budget.py` -> 8 passed

Completion wording: Offline corrective gates passed; live/model-quality verification deferred.
