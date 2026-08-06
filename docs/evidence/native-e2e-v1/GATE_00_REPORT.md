# Gate 0 — Baseline and Evidence Directory

## Environment

| Item | Value |
|---|---|
| Branch | `pageobject-integration` |
| HEAD | `0cc0ff3454f231cdbd357f4040fa27d0f2bb144e` |
| Python | 3.13.14 |
| Node | v23.5.0 |
| pnpm | 10.14.0 |
| Date | 2026-08-06 |

## Commands

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
python --version
node --version
pnpm --version
cd apps/textbook-agent/backend
python -m pytest tests/contracts/test_lectio_page_contracts.py tests/generation/test_page_object_writers.py tests/generation/test_question_wall_and_visuals.py -q --tb=line
```

## Results

- Baseline targeted pytest: **13 passed** in 0.96s
- Working tree: untracked phase-02 pack and prior whole-lesson evidence only (no dirty tracked sources at baseline)

## Known baseline gaps (documented, not ignored)

1. Writers support only 6 forms; missing `aside` and `choices`.
2. `assemble_questions` enriches items with `options` / `correct_key` / `answer_key_ref`, which violate Lectio `questions-content` (`additionalProperties: false`).
3. LLM writer has no typed output model; repair is a blind re-call without prior output/errors.
4. Execution is block-parallel (`MAX_WRITER_CONCURRENCY = 3`), not section-parallel max 4.
5. Status DTO projects legacy `next_action` map; does not surface `page_document_v2` section/block progress.
6. Some entry points remain legacy-capable (`retry-section`, non-page bridge, v3 visual regenerate).

## Pass

Gate 0 pass: evidence directory created; baseline commit and targeted test results recorded; known failures documented.
