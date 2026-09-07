# Phase 03 execution plan (fresh after Phase 02 PASS)

## Goal
Extend LessonDocument sections with learner-facing metadata and add a student lesson shell (tabs/stages) without replacing Builder or writing learner state into documents.

## Inspected facts
- `LessonDocument` / `DocumentSection` in `packages/lectio-learn/src/lib/teacher/document.ts` (version 1).
- Builder route: `frontend/src/routes/builder/[id]/+page.svelte`.
- Render path: `LectioDocumentView` + templates from `@lectio/learn`.
- Visual tokens: Fraunces/Inter + `--paper|--surface|--rule|--ink|--accent|--amber` in app + `@lectio/learn/theme.css`.

## Steps
1. EXTEND `DocumentSection` with optional learner metadata (label, intent, required, nav/completion policy, assessmentMode, conceptRefs) — no attempt/runtime state.
2. Add helpers to derive canonical ordered sections and default learner labels from titles.
3. NEW student shell components under `frontend/src/lib/learn/` + route `frontend/src/routes/learn/lessons/[id]/+page.svelte` (preview of authored document).
4. Desktop/tablet: section tabs/stages; phone: compact stage nav. Reuse existing Xplore tokens.
5. Tests: document metadata round-trip; shell navigation order; breakpoint classes.
6. Gate: Builder tests still green; `@lectio/learn` + page green.

## Non-goals
No persistent attempts, publishing DB, classes, new editor.
