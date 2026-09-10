# Phase F — Rebuild Learn Generation

## Goal
Make Learn generate an ordered editable document with optional interactive islands instead of a registry of teaching-content components.

## Open these active files first
- `apps/textbook-agent/backend/src/learn/generation/native_production.py`
- `apps/textbook-agent/backend/src/learn/generation/native_execution.py`
- `apps/textbook-agent/backend/src/learn/generation/work_orders.py`
- `apps/textbook-agent/backend/src/learn/generation/ordered_assemble.py`
- `apps/textbook-agent/backend/src/learn/generation/authoring_adapter.py`
- `apps/textbook-agent/backend/src/learn/generation/canonical.py`
- `apps/textbook-agent/backend/src/learn/contracts/lesson_document.py`
- `apps/textbook-agent/backend/src/learn/generation/component_lectio/`

## Implementation tasks
- Define the new LearnDocument ordered-node shape around the six primitives and an explicit Interaction node.
- Replace content capability work orders with simple document-node writing work.
- Preserve teaching block/section provenance on the document so intent and learner-task ownership remain traceable.
- Keep interaction work separate and invoke it only after an interaction type has been selected.
- Remove component/template IDs from the new Learn document contract unless a concrete retained interaction requires an ID.
- Stop new Learn production from calling `component_lectio`.

## Expected outputs
- `new LearnDocument contract`
- `new Learn document assembly`
- `new Learn native production flow`
- `tests proving passive and interactive mixed lessons`

## Acceptance gate
A fresh Learn generation completes with zero calls into `learn/generation/component_lectio` and zero ordinary legacy component IDs in persisted output.
