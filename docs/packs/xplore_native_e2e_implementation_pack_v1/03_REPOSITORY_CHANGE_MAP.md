# Repository Change Map

This is an implementation map, not a restriction. Grok must inspect current code before applying edits.

## Core writer module

### Existing
`apps/textbook-agent/backend/src/generation/page_objects/__init__.py`

### Required changes

- Extend generated object support with `aside` and `choices`.
- Replace loose `dict` writer outputs with typed form content models.
- Remove enrichment of `questions.items[]` with:
  - `options`
  - `correct_key`
  - `answer_key_ref`
- Route MCQ records to `choices`.
- Add an `AssessmentBundle` result containing student blocks and answer entries.
- Do not let the writer alter planned object, intent, ID, or position.
- Validate before returning `WriterResult`.
- Keep pending figure fallback deterministic.
- Pass previous invalid output and validation errors into repair.

### Recommended split

```text
generation/page_objects/
├── __init__.py
├── models.py
├── registry.py
├── validation.py
├── assessment.py
├── prompts.py
└── document_assembly.py
```

Avoid a single oversized module if it obscures contracts.

## Form planning

### Existing
- `apps/textbook-agent/backend/src/planning/catalogue_projections.py`
- `apps/textbook-agent/backend/src/planning/whole_lesson/form_agent.py`
- `apps/textbook-agent/backend/src/planning/whole_lesson/form_plan.py`

### Required changes

- Allow all generated forms:
  - prose, list, table, figure, aside, worked-example, questions, choices
- Keep `heading` structural for normal Xplore planning.
- Keep `answer-key` structural and generated from assessments.
- Form validation must reject an object with no registered writer.
- Add explicit assessment form rules:
  - open response → questions
  - MCQ → choices

## Model tiers

### Existing
`apps/textbook-agent/backend/src/planning/model_tiers.py`

### Required changes

- Add `aside` and `choices`.
- `questions`/`choices` may use deterministic approved item records where possible.
- Constrained JSON writer calls should disable provider reasoning if that provider can return reasoning-only responses.
- Do not silently default unknown forms to a tier.

## Execution orchestration

### Existing
- `apps/textbook-agent/backend/src/planning/whole_lesson/executor.py`
- `apps/textbook-agent/backend/src/planning/whole_lesson/worker.py`
- `apps/textbook-agent/backend/src/planning/whole_lesson/states.py`
- `apps/textbook-agent/backend/src/planning/whole_lesson/repository.py`

### Required changes

- Refactor from a flat block work queue to bounded section jobs.
- Persist section execution state and individual block outcomes.
- Keep stable planned positions.
- Validate each block before `ready`.
- Aggregate answer entries after section completion.
- Resume skips already validated outcomes.
- Section failure does not erase other completed sections.
- Correctly classify validation/contract failures as recoverable after repair is exhausted.
- Record actual stage; do not hardcode every failure as `writing_blocks`.
- Ensure every failure has a structured non-null error.

## Assembly

### Existing
`apps/textbook-agent/backend/src/generation/page_objects/document_assembly.py`

### Required changes

- Accept only validated outcomes.
- Sort by planned section/block position.
- Merge answer entries into a top-level `answer-key` block.
- Validate:
  - exact expected IDs;
  - no duplicates;
  - question-to-answer integrity;
  - MCQ answer letter exists;
  - all required sections complete.
- Make no LLM calls.
- Persist, reload, and validate again.

## Status API

### Existing
`apps/textbook-agent/backend/src/generation/v3_studio/router.py`

### Required changes

Read native state from:

```text
chunked_state_json.page_document_v2
```

Expose:

```text
stage
document_version
document_exists
sections_total
sections_ready
sections_failed
blocks_total
blocks_ready
blocks_failed
failed_section_ids
failed_block_ids
error.scope
error.code
error.message
error.retryable
error.validation_errors
```

Do not infer native status from legacy fields.

## Frontend

Likely areas:

```text
apps/textbook-agent/frontend/src/lib/types/v3.ts
native generation polling/status components
document viewer
PDF controls
```

Required behavior:

- understand `writing_sections`;
- stop polling on both terminal states;
- display recoverable error and retry action;
- never show an empty generic failure when structured details exist;
- teacher view shows answer key;
- student view hides answer key;
- pending figures show placeholders.

## Lectio package

### Contract
`packages/lectio-page/contracts/lectio-document-v2.schema.json`

No required schema change for this pass.

Lectio already supports:

- all ten objects;
- separate `questions` and `choices`;
- top-level `answer_key`;
- pending figures.

### Recommended library improvement

Add a semantic document-integrity validator for cross-references:

- answer points to existing question/choice;
- every assessed item has one answer;
- MCQ answer is an available letter.

This may live in Xplore first, but should eventually be reusable from `@lectio/page`.

## Tests to add

Suggested paths:

```text
apps/textbook-agent/backend/tests/generation/test_form_content_models.py
apps/textbook-agent/backend/tests/generation/test_writer_registry_all_forms.py
apps/textbook-agent/backend/tests/generation/test_writer_repair.py
apps/textbook-agent/backend/tests/generation/test_assessment_bundle.py
apps/textbook-agent/backend/tests/generation/test_answer_key_integrity.py
apps/textbook-agent/backend/tests/planning/test_parallel_section_execution.py
apps/textbook-agent/backend/tests/planning/test_section_resume.py
apps/textbook-agent/backend/tests/planning/test_native_status_payload.py
apps/textbook-agent/backend/tests/generation/test_native_all_forms_e2e.py
apps/textbook-agent/backend/tests/generation/test_native_pdf_exports.py
```
