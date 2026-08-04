# Lectio Page-Object Architecture Pack

## Purpose

This pack specifies a direct, experimental cutover from Lectio's component-first document model to a page-object-first document model.

This is **not** an adapter migration. The new path does not convert `SectionContent` into page objects, and it does not retain the old component model as an internal compatibility layer.

The experiment asks one concrete question:

> Can Lectio define a print-native document grammar that the textbook generator plans, writes, stores, reviews, and prints directly?

The old implementation remains available only as a versioned historical path for existing documents. New documents use `document_version: 2`.

## Architectural decision

- Lectio v2 owns the canonical `LectioDocument` contract, page objects, pedagogical intent catalogue, validation, rendering, page geometry, and print styling.
- The textbook generator retains unit planning, learning paths, learner groups, skeletons, writers, streaming, persistence, visual generation, QC orchestration, and PDF export machinery.
- The textbook generator stops planning named Lectio components and stops assembling wide `SectionContent` records.
- Writers emit ordered document blocks.
- The merge layer preserves `position`.
- The frontend consumes `LectioDocument` directly.
- Only `aside` may have a border or background.
- The target intent catalogue is deliberately rich: 32 intents for 10 objects.
- Chromium remains the PDF engine for this experiment.

## Included artifacts

1. `artifacts/A_FORK_PLAN.md`
2. `artifacts/B_CONTRACT_AND_INTENT_CATALOGUE.md`
3. `contracts/lectio-document-v2.schema.json` (pack copy; synced from repo root)
4. Intent + object catalogues — canonical at repo-root [`contracts/intent-catalogue.v1.json`](../../../contracts/intent-catalogue.v1.json) and [`contracts/object-catalogue.v1.json`](../../../contracts/object-catalogue.v1.json) (not duplicated in this pack)
5. `artifacts/C_CONTRACT_VALIDATION_TEST.md`
6. `fixtures/planner-palette-v2.txt`
7. `fixtures/planner-comparison-topic.json`
8. `artifacts/D_PAGE_OBJECT_SPECS.md`
9. `contracts/base-print.css`
10. `artifacts/E_BASE_PRINT_STYLESHEET.md`
11. `artifacts/F_BACKEND_REWIRING_MAP.md`
12. `artifacts/G_PHASING_PLAN.md`
13. `SOURCE_MANIFEST.md`
14. `AUDIT_CHECKLIST.md`
15. Uploaded reference files under `references/uploaded/`

## Non-negotiable fork rules

1. No adapter from `SectionContent` to v2.
2. No saved-document migration.
3. No boxes outside `aside`.
4. No object-name labels in student output.
5. No screen-first markup that must be stripped for print.
6. No collapse to a thin intent vocabulary.
7. No PDF-engine replacement during the page-object experiment.
8. No changes to queues, workers, providers, retries, timeouts, or admission control.
9. One independently verifiable commit per phase.
10. The v2 print stylesheet starts small and must remain positive-rule-only.

## Repository basis

The architecture was grounded against:

- `richiewaweru/lectio`, branch `xplore`
- `richiewaweru/text-book-generator`, branch `xplore`

The inspected textbook branch already separates path planning, knowledge types, lesson modes, skeletons, learner groups, execution, visual generation, review, and resource composition. The cutover therefore targets the resource vocabulary and assembly boundary, not the entire product architecture.

## Document version

**PACK VERSION:** 1.0  
**LAST UPDATED:** 2026-08-04  
**STATUS:** Ready for Claude architecture audit and Codex implementation planning
