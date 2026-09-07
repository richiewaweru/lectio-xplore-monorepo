# D6A Report — Unit → Print Integration

Status: PASS

## Starting state
- branch: `refactor/domain-ownership`
- sha: `c2f8a5cf0202bb1d52658a077a20de68f77e38d7`
- dirty_state: D6 docs + new D6A test uncommitted
- prior program: D0–D5 PASS

## Test flow implemented
Canonical Unit fixture `grade4-photosynthesis-path.json` → `create_unit` / `persist_path_plan` / `approve_path` → production `prepare_path_lesson` → production `build_packet_for_generation` → deterministic teaching/form plans (provider fakes) → `write_form_blocks` with recoverable failure → requeue → `execute_after_teaching_approval` → reload SHA256 → `validate_document` → `render_document_pdf` + pypdf parse.

## Production services exercised
- `application.unit_lesson.prepare_path_lesson`
- `curriculum.service` create/persist/approve path
- `print.generation.whole_lesson.service.build_packet_for_generation`
- `print.generation.whole_lesson.repository.PageDocumentRepository`
- `print.generation.whole_lesson.executor.write_form_blocks` / `execute_after_teaching_approval`
- `print.contracts.lectio_page.validate_document`
- `print.rendering.page_objects.views.render_document_pdf`

## External dependencies mocked
- Structural planner / component selector (path prepare fakes)
- Writer boundary: `dispatch_writer_async` → deterministic `WriterOutcome` (prose/figure)
- Teaching/form LLM planners not invoked; plans supplied as deterministic fakes matching packet legality

## Assertions
- Unit prepare yields `native_whole_lesson` + `path_prepared` generation
- At least one `failed_recoverable` block under failure injection
- After retry: status `ready` or `awaiting_visuals`
- Persisted document reloads with stable SHA256
- `validate_document` returns `[]`
- PDF starts with `%PDF`, non-empty, ≥1 page, extractable text

## Failures found
| Failure | Classification | Canonical owner | Debt ID |
|---|---|---|---|
| (none blocking) | — | — | — |

Note: check-slot typical intents (`check-understanding`) disallow prose; test selects prose-compatible intents from the legality snapshot so assembly stays deterministic without approved assessment items. Not a product defect for D6A.

## Minimal fixes made
- Added `tests/planning/test_d6a_unit_print_integration.py` only.

## Commands/results
```
uv run pytest tests/planning/test_d6a_unit_print_integration.py -q
→ 1 passed
```

## Ending state
- safe for next subphase: YES
