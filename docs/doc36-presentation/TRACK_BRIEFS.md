# Execution briefs

All workers read doc 36 in full, doc 35, applicable AGENTS.md and standards. Source design: `C:/Users/richi/Downloads/Lesson presentation revamp.html`. Source work order: `C:/Users/richi/Downloads/36_LESSON_PRESENTATION_REVAMP.md`. Workers are not alone: preserve other edits, change only owned files, and report unexpected dependencies to the lead. Use small commits, no pushes to main. A gate checkbox requires a named artifact/test/log; report partial items honestly. Do not change shared declarations after G0 without lead review.

## A — Learn renderer, G1

Own `apps/textbook-agent/frontend/src/lib/learn/document/` renderer components/canvas/styles (exclude Phase 0 types and parsers), `learn/student/OrderedDocumentList.svelte`, learner shell metadata/title presentation, and task component markup/styles only. Own fixture-page screen preview wiring needed for screenshot tests. D owns interaction logic/feedback evaluation. Read new fields with legacy fallback. Coordinate shared task component changes with D; D branches from Phase 0 and receives your styled component before integrating logic.

Implement A1–A7 and section 3 tokens precisely, all inline strings through the frozen parser, reading prose outside cards, only tasks with dark headers, lesson map/section body headings, semantic ordered/unordered lists, ordinary blocks, responsive table/compare/equation layout. Missing assets produce no learner placeholder. Use existing display serif (Fraunces), Atkinson body; do not add libraries/colours/block kinds.

Validation: `pnpm app:test`, `pnpm app:check`, production frontend build; browser fixture screenshots at 1280 and 390; golden block checklist against artboard; legacy paragraphs/list/titles; overlong no truncation/horizontal scroll; Tab options/buttons with pressed states; DOM exact internal-identifier/debug-label search (do not flag ordinary word occurrences accidentally). Keep HTML unknown-kind fallback text-only and log once. Report commit(s), tests, screenshot paths, every G1 item and differences.

## B — Print renderer, G2

Own backend `src/print/generation/shared_document_adapter.py`, Print presentation/export plumbing and templates/styles, plus `packages/lectio-page` page contract/generated twins and renderer/print CSS needed for doc36 blocks, answer-key layout, and Print-only tests. Exclude shared models/parsers, Learn and prompts. D owns task data generation; B styles the data and teacher page. Keep adapters ordinary-text faithful.

Implement B1–B6: full-width callouts, paragraph splitting, semantic numbering, under-five-section TOC suppression, name/date/title/front matter, running subject/lesson line and title/Page n of N footer, A4 ~16mm, Atkinson 12pt and minimum 9pt, all block distinctions in greyscale. Heading binding and avoid splits for blocks that fit a page; owner-approved safe text/row continuation only for intrinsically oversized blocks. Preserve every word. Teacher-only answers/notes separated from learner pages, stable Q numbering.

Validation: adapter tests, `pnpm page:test`, `pnpm page:check`, app checks/build as required; PDF golden/legacy/overlong, greyscale page images; bounding-box clipping/overlap inspection; text search for internal labels and answer leakage; word parity with golden. Report all G2 evidence and unticked limits. Do not assume the canvas's abbreviated Print prose is authoritative.

## C — Composer/writer, G3

Own backend `document/shared_lesson/composer.py`, ordinary writer/packet/schema implementations, `resources/prompts/section-composer.md`, `shared-section-writer.md`, and composer/writer/continuity/QA length/count/advisory validators and tests. Shared declarations from Phase0 are frozen. Do not edit task contract/prompts/renderers or figure decisions. Preserve base doc35 code-owned figures and spec-bound caption authoring.

Implement C1–C5, all shaping/inline rules and target table, one dense-to-shaped photosynthesis example; carry optional node fields through provider drafts/packets. Audit all length/node-count/paragraph-run/callout shape checks and route warnings per section without readiness changes or correction calls. Distinguish schema/identity/leakage/task validity hard checks from shape advisory checks. No minimum padding. Existing node-kind/order integrity checks may remain hard only where they protect actual contract identities, not counts used as content targets; explain each retained check.

Validation: targeted backend prompt/composer/writer/continuity/QA tests, ruff; three actual fresh generations (photosynthesis, maths formula, comparison) with raw documents, call logs and advisory warnings. Check G3 wording/formatting/misconceptions/list discipline on real rendered outputs. Record each downgraded check and prove no length/shape retry/failure/truncation. Quality misses remain advisory at runtime even when G3 acceptance cannot be ticked.

## D — Tasks, G4

Own backend `curriculum/shared_task_authoring.py`, task authoring prompt, Learn shared adapter task-contract lowering, Print adapter task-data helpers (coordinate B; no ordinary mapping/style changes), frontend interaction contract type plumbing where Phase0 declarations need propagation, `InteractionShell.svelte` and retained interaction logic/feedback modules. A owns task markup/styles. Preserve backend/frontend public legacy behaviour when role is absent.

Implement D1–D4 using Phase0 declarations: short display_prompt fallback to prompt, predict saved feedback without grading state, explanatory practice/check, teacher-only wrong-option notes, identical running question numbering across all views. Do not expose evaluation/notes on learner Print pages. Retain legacy options/evaluation/attempt behaviour and answered-task compatibility. All task learner strings use frozen inline parser. Do not truncate long prompts or regenerate on targets.

Validation: shared task authoring and both adapter task tests, frontend interaction tests/check; actual fresh-task evidence and rendered predict/check interactions; legacy task answering; Q sequence cross-output checks. Report each G4 item with test/screenshot/log artifact, generic feedback equality checks scoped to fresh output (legacy defaults remain supported).

## Integration — Phase 5

One Luna executor after lead-reviewed merge order 0, A, B, D, C. Own integration/evidence tests and narrowly scoped fixes only with lead-assigned ownership. Generate photosynthesis end to end on merged branch, open Learn and export learner/teacher PDF; run repo validation and architecture checks, word parity and legacy hash/render/answer compatibility. Compare all five artboards and list every difference acceptable/to fix. Fill doc36 section5 final acceptance with artifact links, retain unticked gates, no external deployment/main push.
