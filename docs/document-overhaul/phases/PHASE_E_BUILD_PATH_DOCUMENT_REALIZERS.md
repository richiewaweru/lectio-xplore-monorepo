# Phase E — Build Path Document Realizers

## Goal
Replace ordinary capability selection with a small reasoning stage that chooses document forms and, only when needed, path-specific learner-task mechanisms.

## Open these active files first
- `apps/textbook-agent/backend/src/print/generation/selection_snapshot.py`
- `apps/textbook-agent/backend/src/print/resources/selection.py`
- `apps/textbook-agent/backend/src/learn/generation/native_selection.py`
- `apps/textbook-agent/backend/src/learn/resources/selection.py`
- `apps/textbook-agent/backend/src/infra/authoring/capability_selector.py`

## Implementation tasks
- Introduce a Print realizer and Learn realizer that consume an approved Teaching Plan.
- Normal-content choices are limited to Paragraph, Heading, List, Figure, Table, Callout.
- Learn may additionally choose one retained interaction when the learner task requires behavior.
- Print may additionally choose a Print task treatment/response form.
- Separate `choose the form` from `write the payload`.
- Keep decision snapshots/hashes if they remain useful for reproducibility, but simplify them to the new vocabulary.
- Do not expose every interaction schema to the first LLM selection call.

## Expected outputs
- `apps/textbook-agent/backend/src/print/generation/document_realizer.py`
- `apps/textbook-agent/backend/src/learn/generation/document_realizer.py`
- `new compact realization decision schemas`

## Acceptance gate
A representative Teaching Plan produces a compact composition plan containing only allowed document primitives plus path-legal task mechanisms; no old ordinary component ID is selectable.
