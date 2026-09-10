# Policy cleanup v4 — GATES

Statuses: `NOT_RUN` | `PASS` | `FAIL` | `BLOCKED`. Live may use `DEFERRED`. Offline mandatory gates are never `DEFERRED`.

| ID | Requirement | Status | Test / evidence | Command | Tested commit |
| --- | --- | --- | --- | --- | --- |
| G01 | Baseline trace locates producers, policy owners, consumers, runtime, existing gates | NOT_RUN | PLAN.md; CALLER_MAP.md; DECISIONS.md | inspect docs | |
| G02 | Package default reaches work-order creation; changing exported default changes resolved behavior | NOT_RUN | | | |
| G03 | Explicit supplied-only and automatic-required override; unsupported/contradictions fail | NOT_RUN | | | |
| G04 | Generated exports match source; no duplicate catalogue; definition version/hash recorded | NOT_RUN | | | |
| G05 | Legacy absent-policy deterministic; default changes cannot reinterpret published records | NOT_RUN | | | |
| G06 | Objective-only + supplied_preferred reaches provider with empty facts, separate objective, model-knowledge instructions | NOT_RUN | | | |
| G07 | Same prep + supplied_only fails before provider (zero calls) | NOT_RUN | | | |
| G08 | Missing referenced fact IDs / prep failures fail under permissive policy (zero calls) | NOT_RUN | | | |
| G09 | Real supplied statements + source identity preserved; objective/title/arc never inserted as facts | NOT_RUN | | | |
| G10 | Blank objective / insufficient inputs fail; facts-optional + complete convert not blocked | NOT_RUN | | | |
| G11 | Print + Learn load selected instructions and resolved knowledge mode; no catalogue leakage | NOT_RUN | | | |
| G12 | Repair/resume preserve policy/source revision; provider cannot alter trusted mode | NOT_RUN | | | |
| G13 | Approved ShortResponse with answers preserves stem/answers/case; automatic evaluation | NOT_RUN | | | |
| G14 | Missing answer + automatic_required → typed failure; never teacher-review | NOT_RUN | | | |
| G15 | Missing answer + explicit teacher-review succeeds with guidance; no invented answer | NOT_RUN | | | |
| G16 | Missing answer + automatic_preferred fallback succeeds and records why; disallowed/conflict fail | NOT_RUN | | | |
| G17 | Unreferenced approved items inaccessible; missing ref fails; no first-item substitution | NOT_RUN | | | |
| G18 | Teacher-review submission pending; automatic checks correct/incorrect | NOT_RUN | | | |
| G19 | One Unit prep → saved Print+Learn same revision; fresh DB reload content/source/policy | NOT_RUN | | | |
| G20 | Publish v1, edit draft/policy, publish v2; v1 unchanged | NOT_RUN | | | |
| G21 | Builder rejects incompatible assessment edits; valid edits retain metadata after reload | NOT_RUN | | | |
| G22 | Regressions detect objective-as-fact and unauthorized teacher-review; positive authorized fallback | NOT_RUN | | | |
| G23 | Affected earlier mandatory gates pass; skips have equivalent coverage | NOT_RUN | | | |
| G24 | Final verification records commit, commands, exit codes, mappings, limitations | NOT_RUN | | | |
