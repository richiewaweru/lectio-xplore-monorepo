# R04 Report — Real offline integration and rendering

Phase/status: **PASS**

Plan: `tracking/R04-PLAN.md`

## Production fixes (pre-test commit)

- `print/generation/native_production.py`: use `LessonIdentity.objective` for `lesson_title` (field `title` does not exist).
- `learn/generation/native_execution.py`: merge `shared_preparation_packet` from generation chunked state when building `LearnPreparationContext` (page-only state omitted pinned facts).

## Gate results

| Gate | Status | What it actually exercises |
| --- | --- | --- |
| R04-G01 | PASS | P08 Unit prep + approve; **MOCK** Print writer + Learn provider; `execute_after_teaching_approval` + `produce_learn_from_approved_teaching`; **fresh** `async_session_factory` reload; `assert_identical_consumer_handoffs`, realizations, meaningful content |
| R04-G02 | PASS | Envelope closed production document; POST publish v1; PUT Builder edit; publish v2; fresh API + DB reads; publish rejects empty sequence config |
| R04-G03 | PASS | Envelope sequence document; runtime attempt API; correct/incorrect outcomes; forged score 422; fresh DB on attempts + instance release binding |
| R04-G04 | PASS | Print writer failure injection + requeue/retry; Learn sibling realization intact; no duplicate print block ids after recovery |
| R04-G05 | PASS | **Offline rendering**: vitest mounts all eight core `@lectio/learn` shells with envelope-shaped contracts; keyboard/submit |
| R04-G06 | PASS | Instruction text mutation → writer request hash change; MOCK closed production captures provider call; published v1 release hash immutable after draft regen |

## A06 supersession

- Removed/skipped false-pass integrated tests (deepcopy reload, hash-only publish, dispatch-only dual-path, evaluator-only interactions).
- `authoring-correction-v2/tracking/A06-REPORT.md` updated to point at R04 gates.

## Commands

```text
cd apps/textbook-agent/backend
uv run pytest -q tests/remaining_fixes/test_r04_g01_dual_path_persistence.py tests/remaining_fixes/test_r04_g02_publish_builder.py tests/remaining_fixes/test_r04_g03_runtime_attempts.py tests/remaining_fixes/test_r04_g04_writer_failure_retry.py tests/remaining_fixes/test_r04_g06_instruction_regeneration.py

cd packages/lectio-learn
npm run test -- src/lib/learn/interaction-shells.r04.test.ts
```

Evidence:

- `evidence/r04/pytest-r04-all.txt` — 8 passed
- `evidence/r04/vitest-r04-g05.txt` — 9 passed

## Deferred

- Live browser acceptance journeys.
- Live model quality of authored distractors/feedback.

Completion wording: **Remaining fixes verified offline for R04; live/model-quality verification deferred.**
