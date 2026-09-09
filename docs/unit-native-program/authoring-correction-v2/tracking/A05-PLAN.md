# A05 Plan — Selection and upstream ownership

## Scope
- Remove backend semantic fallback maps (`INTENT_CONTENT_FALLBACKS`).
- Rank closed Print and Learn shortlists with package `choose_when` / `reject_when` guidance.
- Preserve eligibility exclusions for assets, budgets, readiness, policy and writer support.
- Keep teaching ownership fail-closed for incompatible approved sources.
- Add A05 gate tests and A00 first-content / fallback-budget regressions.

## Checklist
- [x] Delete `INTENT_CONTENT_FALLBACKS` and fallback reinclusion in `learn/resources/selection.py`.
- [x] Add `rank_print_form_candidates` and semantic `select_print_deterministically`.
- [x] Extend Learn production selection with `rank_learn_content_candidates`.
- [x] Add `tests/authoring_correction/test_a05_selection.py` for A05-G01..G06.
- [x] Fix A00 fallback-budget regression to use complete writer cards.
- [x] Record evidence under `evidence/a05/` and update gate tracking.
