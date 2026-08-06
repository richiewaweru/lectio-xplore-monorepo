# Test Strategy and Commands

Adapt paths only if repository scripts differ. Record every exact command and exit code.

## Environment

From repository root:

```bash
git status --short
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
python --version
node --version
pnpm --version
```

Backend:

```bash
cd apps/textbook-agent/backend
python -m pip install -e ".[dev]"
```

## Existing contract tests

```bash
python -m pytest tests/contracts/test_lectio_page_contracts.py -q
python -m pytest tests/generation/test_page_object_writers.py -q
python -m pytest tests/generation/test_question_wall_and_visuals.py -q
```

## New targeted tests

```bash
python -m pytest   tests/generation/test_form_content_models.py   tests/generation/test_writer_registry_all_forms.py   tests/generation/test_writer_repair.py   tests/generation/test_assessment_bundle.py   tests/generation/test_answer_key_integrity.py   -q
```

```bash
python -m pytest   tests/planning/test_parallel_section_execution.py   tests/planning/test_section_resume.py   tests/planning/test_native_status_payload.py   -q
```

```bash
python -m pytest   tests/generation/test_native_all_forms_e2e.py   tests/generation/test_native_pdf_exports.py   -q
```

## Existing durability and worker tests

```bash
python -m pytest   tests/planning/test_phase02_failure_classification.py   tests/planning/test_phase02_worker_failure_policy.py   tests/planning/test_phase02_queue_and_lease.py   tests/generation/test_v3_pump_durability.py   -q
```

## Native backend suite

Run all native-related tests selected by path or marker. Then run the complete offline backend suite:

```bash
python -m pytest -q
```

The repository's pytest configuration excludes integration and postgres tests by default.

## Lint

```bash
python -m ruff check src tests
```

## Lectio package

From repository root:

```bash
pnpm install
pnpm page:check
pnpm page:test
pnpm page:pdf
```

## Frontend

```bash
pnpm app:check
pnpm app:test
```

## Contract synchronization

After any intentional Lectio contract update:

```bash
pnpm contracts:sync
git diff --exit-code   packages/lectio-page/contracts/lectio-document-v2.schema.json   apps/textbook-agent/backend/contracts/lectio-page/lectio-document-v2.schema.json
```

No schema change is expected for the main implementation.

## Mock E2E command

Grok should add a deterministic driver such as:

```bash
cd apps/textbook-agent/backend
python tools/run_native_e2e_fixture.py   --fixture ../../../xplore_native_e2e_implementation_pack_v1/08_FIXTURES/lesson_request_all_forms.json   --scenarios ../../../xplore_native_e2e_implementation_pack_v1/09_MOCK_SCENARIOS/mock_llm_scenarios.yaml   --output ../../../docs/evidence/native-e2e-v1
```

The driver must call the real application services/state machine, not directly construct the final document.

## Real smoke command

Add or use a driver that takes the same route but swaps only the provider:

```bash
python tools/run_native_e2e_fixture.py   --fixture <small-real-lesson.json>   --provider real   --output ../../../docs/evidence/native-e2e-v1/real
```

## Assertions that must be automated

- no legacy functions called;
- max section concurrency <= 4;
- output section order is canonical;
- invalid writer output never saved as ready;
- repair prompt includes exact errors and prior output;
- every answer points to an existing assessment;
- every assessment has one answer;
- pending figure does not block ready;
- persisted and reloaded documents validate;
- terminal statuses always have errors;
- student output excludes answer key;
- teacher output includes answer key.
