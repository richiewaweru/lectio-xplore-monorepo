# Phase B — Define Minimal Document Vocabulary

## Goal
Introduce the only ordinary presentation vocabulary needed by the new generation architecture.

## Open these active files first
- `apps/textbook-agent/backend/src/print/generation/page_blocks.py`
- `apps/textbook-agent/backend/src/print/generation/whole_lesson/form_plan.py`
- `packages/lectio-page/contracts/lectio-document-v2.schema.json`
- `packages/lectio-page/contracts/object-catalogue.v1.json`
- `apps/textbook-agent/backend/src/learn/contracts/lesson_document.py`

## Implementation tasks
- Create a small shared internal document vocabulary: Paragraph, Heading, List, Figure, Table, Callout.
- Define deliberately small contracts with stable node IDs and ordered structure.
- Do not include page geometry, pagination, CSS, template IDs, component IDs, interaction scoring, video, simulation, or generic Media.
- Decide one canonical Python ownership location (recommended `backend/src/document/`) and update architecture rules accordingly.
- Add unit validation for each primitive and mixed-node sequences.

## Expected outputs
- `apps/textbook-agent/backend/src/document/__init__.py`
- `apps/textbook-agent/backend/src/document/models.py`
- `apps/textbook-agent/backend/src/document/validation.py`
- `apps/textbook-agent/backend/tests/document/...`

## Acceptance gate
All six primitive types round-trip through validation/persistence, and adding a new teaching intent does not require a new document node class.
