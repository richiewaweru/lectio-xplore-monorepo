# Policy cleanup v4 — GATES

Statuses: `NOT_RUN` | `PASS` | `FAIL` | `BLOCKED`. Live may use `DEFERRED`. Offline mandatory gates are never `DEFERRED`.

Tested code commit: `80cbc1685f4830a55379912adfaea06302cec0c3`

| ID | Requirement | Status | Test / evidence | Command | Tested commit |
| --- | --- | --- | --- | --- | --- |
| G01 | Baseline trace locates producers, policy owners, consumers, runtime, existing gates | PASS | PLAN.md; CALLER_MAP.md; DECISIONS.md | inspect docs | 74830b4332bac1eb8f08186ed96dc464dc4ae7bd |
| G02 | Package default reaches work-order creation; changing exported default changes resolved behavior | PASS | test_g02_* | `uv run pytest -q tests/policy_cleanup/test_policy_g02_g17.py -k g02` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G03 | Explicit supplied-only and automatic-required override; unsupported/contradictions fail | PASS | test_g03_* | `uv run pytest -q tests/policy_cleanup/test_policy_g02_g17.py -k g03` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G04 | Generated exports match source; no duplicate catalogue; definition version/hash recorded | PASS | test_g04_*; learn/page export | `pnpm learn:export; pnpm page:export; pytest -k g04` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G05 | Legacy absent-policy deterministic; default changes cannot reinterpret published records | PASS | test_g05_*; G20 v1 immutable | `pytest -k g05`; G20 | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G06 | Objective-only + supplied_preferred reaches provider with empty facts, separate objective, model-knowledge instructions | PASS | test_g06_* | `pytest -k g06` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G07 | Same prep + supplied_only fails before provider (zero calls) | PASS | test_g07_*; test_r02_g05_supplied_only_* | `pytest -k g07` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G08 | Missing referenced fact IDs / prep failures fail under permissive policy (zero calls) | PASS | test_g08_* | `pytest -k g08` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G09 | Real supplied statements + source identity preserved; objective/title/arc never inserted as facts | PASS | test_g09_* | `pytest -k g09` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G10 | Blank objective / insufficient inputs fail; facts-optional + complete convert not blocked | PASS | test_g10_*; remapped r02 g05 | `pytest -k g10` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G11 | Print + Learn load selected instructions and resolved knowledge mode; no catalogue leakage | PASS | test_g11_*; Print executor allowed_facts threading | `pytest -k g11` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G12 | Repair/resume preserve policy/source revision; provider cannot alter trusted mode | PASS | test_g12_* | `pytest tests/policy_cleanup/test_policy_g12_g19.py -k g12` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G13 | Approved ShortResponse with answers preserves stem/answers/case; automatic evaluation | PASS | test_g13_* | `pytest -k g13` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G14 | Missing answer + automatic_required → typed failure; never teacher-review | PASS | test_g14_* | `pytest -k g14` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G15 | Missing answer + explicit teacher-review succeeds with guidance; no invented answer | PASS | test_g15_* | `pytest -k g15` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G16 | Missing answer + automatic_preferred fallback succeeds and records why; disallowed/conflict fail | PASS | test_g16_*; remapped r01 g04 | `pytest -k g16` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G17 | Unreferenced approved items inaccessible; missing ref fails; no first-item substitution | PASS | test_g17_*; retained R02 source resolver | `pytest -k g17` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G18 | Teacher-review submission pending; automatic checks correct/incorrect | PASS | test_g18_* | `pytest tests/policy_cleanup/test_policy_g18_g21_runtime.py -k g18` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G19 | One Unit prep → saved Print+Learn same revision; fresh DB reload content/source/policy | PASS | test_g19_*; retained R04-G01 | `pytest -k g19` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G20 | Publish v1, edit draft/policy, publish v2; v1 unchanged | PASS | test_g20_g21_* | `pytest -k g20` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G21 | Builder rejects incompatible assessment edits; valid edits retain metadata after reload | PASS | test_g20_g21_*; remapped r04_g02 malformed | `pytest -k g21` | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G22 | Regressions detect objective-as-fact and unauthorized teacher-review; positive authorized fallback | PASS | evidence/g22-mutation-failures.txt; test_g16 positive | isolated worktree mutation | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G23 | Affected earlier mandatory gates pass; skips have equivalent coverage | PASS | evidence/pytest-policy-remaining-authoring.txt (124 passed, 3 skipped) | see FINAL-REPORT | 80cbc1685f4830a55379912adfaea06302cec0c3 |
| G24 | Final verification records commit, commands, exit codes, mappings, limitations | PASS | FINAL-REPORT.md; evidence/ | report commit | 80cbc1685f4830a55379912adfaea06302cec0c3 |
