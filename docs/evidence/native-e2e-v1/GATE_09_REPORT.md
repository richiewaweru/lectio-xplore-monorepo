# Gate 9 — Mocked full native E2E

## Pass

Mocked native path produces a validating LectioDocumentV2 with all 8 forms, answer key, pending figure, student/teacher HTML+PDF renders, status timeline, persist/reload hash equality, and the full pack scenario matrix.

## Implementation

| Artifact | Path |
|---|---|
| E2E driver | `apps/textbook-agent/backend/tools/run_native_e2e_fixture.py` |
| Views helper | `apps/textbook-agent/backend/src/generation/page_objects/views.py` |
| E2E tests | `tests/generation/test_native_all_forms_e2e.py` |
| PDF tests | `tests/generation/test_native_pdf_exports.py` |

## Commands

```bash
cd apps/textbook-agent/backend
.venv\Scripts\python.exe -m pytest tests/generation/test_native_all_forms_e2e.py tests/generation/test_native_pdf_exports.py -q --tb=short
.venv\Scripts\python.exe tools\run_native_e2e_fixture.py --scenario all --provider mock --output C:\Projects\lectio\docs\evidence\native-e2e-v1
```

## Results

### Pytest

**7+ passed** (native E2E + PDF suite green; combined with writer suite: 15 passed)

### Mock driver (`--scenario all`)

| Metric | Count |
|---|---|
| passed | 11 |
| failed | 0 |
| skipped | 0 |

Scenarios: `all_valid_out_of_order`, `invalid_json_then_valid`, `wrong_schema_then_valid`, `questions_extra_fields_then_valid`, `permanently_invalid_questions`, `transport_then_valid`, `orphan_answer`, `missing_answer`, `invalid_mcq_answer`, `figure_missing_alt_then_valid`, `partial_resume`.

### Evidence artifacts

- `generated-lectio-document-v2.json`
- `reloaded-lectio-document-v2.json`
- `mock-run-report.json`
- `status-timeline.json`
- `student-render.html` / `teacher-render.html`
- `student.pdf` / `teacher.pdf`
- `legacy-reference-audit.txt`
- `provider-calls.json`
