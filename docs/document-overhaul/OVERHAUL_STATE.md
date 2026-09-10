# Document + Interaction Overhaul — State

**Classification**: major  
**Branch**: `refactor/document-model-overhaul`  
**Baseline SHA**: `1dabd746af65ac9d9272fcb7c49f000632407754`  
**Backup tag**: `backup/document-overhaul-precut-2026-09-10`  
**Started**: 2026-09-10  
**Closed**: 2026-09-11 (Phases A–O complete in working tree; see reports)

## Progress

- [x] Documented scope and pack copied to `docs/document-overhaul/`
- [x] Mapped current dependencies (see pack repo-map)
- [x] Established baseline (commands below — Phase O)
- [x] Phase A — Shared instructional contracts
- [x] Phase B — Minimal document vocabulary
- [x] Phase C — Extract Print content from layout
- [x] Phase D — Explicit single-path admission
- [x] Phase E — Path document realizers
- [x] Phase F — Rebuild Learn generation
- [x] Phase G — Rationalize Learn interactions
- [x] Phase H — Align Print realization
- [x] Phase I — Learn document renderer/editor
- [x] Phase J — Writers and prompts
- [x] Phase K — Persistence and releases
- [x] Phase L — Frontend path UX
- [x] Phase M — Hard delete legacy → `reports/PHASE_M_LEGACY_DELETION.md`
- [x] Phase N — Repo/package cleanup → `reports/PHASE_N_REPO_CLEANUP.md`
- [x] Phase O — Full verification → `reports/PHASE_O_VERIFICATION.md`

## Interaction KEEP / DELETE (locked)

**KEEP:** `choice`, `multi-select`, `fill-blank`, `classify`, `match-pairs`, `sequence`, `numeric`, `short-response`  
**DELETE:** `image-hotspot`, `drag-label`, `image-choice`/`image-block`, `video-embed`, spatial actions

## Deferred debt

- Full `@lectio/learn` package removal is **deferred** until interactions are fully moved to the app. Root `learn:test` / `learn:export` scripts remain so the workspace stays installable.
- Ordinary content components still present inside `@lectio/learn` (ExplanationBlock, DefinitionCard, SectionContent templates, etc.) are not the production generation path; strip tracked in Phase N report.

## Baseline / Phase O Evidence

| Command | Result | Notes |
| --- | --- | --- |
| `pnpm contracts:test` | PASS | 20 tests |
| `pnpm contracts:check` | PASS | Fixed TS18048 in `vocabulary.test.ts` during Phase O |
| `pnpm page:test` | PASS | 64 tests |
| Backend document/learn/print/curriculum pytest slice | PASS | 36 passed |
| Zero-legacy `rg` | RECORDED | Matches justified in Phase O report; RuledLines=0; production `component_lectio` deleted |

## Phase Gate Log

| Phase | Status | Evidence |
| --- | --- | --- |
| A–L | complete | Working tree on `refactor/document-model-overhaul` (`document/`, realizers, FE canvas, interactions) |
| M | complete | `reports/PHASE_M_LEGACY_DELETION.md` |
| N | complete | `reports/PHASE_N_REPO_CLEANUP.md` |
| O | complete | `reports/PHASE_O_VERIFICATION.md` — **PASS with deferred debt** |
