# Phase C — Extract Print Content from Print Layout

## Goal
Separate reusable information-form decisions from paper-only page behavior without weakening the Print engine.

## Open these active files first
- `apps/textbook-agent/backend/src/print/generation/selection_snapshot.py`
- `apps/textbook-agent/backend/src/print/generation/work_orders.py`
- `apps/textbook-agent/backend/src/print/generation/page_blocks.py`
- `apps/textbook-agent/backend/src/print/generation/page_projections.py`
- `apps/textbook-agent/backend/src/print/generation/whole_lesson/form_agent.py`
- `apps/textbook-agent/backend/src/print/generation/whole_lesson/form_plan.py`
- `apps/textbook-agent/backend/src/print/generation/whole_lesson/prompt_render.py`
- `apps/textbook-agent/backend/src/print/generation/whole_lesson/executor.py`
- `packages/lectio-page/contracts/object-catalogue.v1.json`
- `packages/lectio-page/contracts/lectio-document-v2.schema.json`
- `packages/lectio-page/src/lib/print/base-print.css`

## Implementation tasks
- Identify Print forms that are really Paragraph/Heading/List/Figure/Table/Callout decisions and map them to the shared vocabulary.
- Leave page-object composition, response areas, ruled lines, page breaks, geometry and PDF rules in Print.
- Keep useful Print writer/form heuristics but stop treating ordinary semantic teaching moves as distinct rendering universes.
- Write an explicit ownership map before moving code.

## Expected outputs
- `print/document mapping table`
- `shared document-form utilities extracted from Print where genuinely reusable`
- `Print-only page/treatment layer with no Learn imports`

## Acceptance gate
A dependency scan shows shared document code contains no pagination/PDF/ruled-line assumptions, while Print can still render a representative document to PDF.
