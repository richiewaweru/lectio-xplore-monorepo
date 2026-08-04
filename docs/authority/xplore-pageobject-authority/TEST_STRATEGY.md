# Test and Verification Strategy

## 1. Test pyramid

### Contract tests

- page package JSON Schema validates canonical examples;
- Python generated models accept the same valid examples and reject shared invalid examples;
- catalogue intent/object IDs and versions match across package/backend snapshots;
- compatibility parity fixtures return the same result in TypeScript and Python;
- section-title heading behavior is identical in screen and print render.

### Planning tests

- resource × skeleton intersection is deterministic;
- excluded intents never reach the planner;
- heading never reaches first-slice object candidates;
- `answer-key` is non-selectable;
- every candidate intent has at least one implemented compatible object;
- empty intersection reports exact configuration path;
- legacy `StructuralPlan` still parses;
- v2 `SectionPlan.blocks` positions are contiguous;
- v2 bridge never invokes component selector.

### Prompt contract tests

Build the exact user payload and assert it contains:

- resource ID/label/purpose;
- lesson mode;
- actual prior established knowledge;
- scope exclusions and terminology;
- closed candidate matrix;
- objective and concept card;
- section purpose and block bounds;
- no full catalogue outside the matrix;
- no generic `student_arrives_with` stance text.

### Writer tests

Per object:

- valid content fixture;
- minimum/maximum capacity boundaries;
- prohibited extra fields;
- scope/terminology propagation;
- wrong output type rejected;
- writer cannot change object/intent;
- retry feedback contains validation error but not alternative object catalogue.

### Wall tests

Use two lessons with identical concept cards but radically different generated prose. Assert item-generation input hashes and resulting mocked item requests are identical.

Assert question assembler receives only:

- item records;
- planned source IDs;
- audience/answer presentation policy;
- no section prose or block briefs.

### Document lifecycle tests

- assemble valid document;
- persist and reload normalized equality;
- duplicate IDs rejected;
- position mismatch rejected;
- pending figure accepted with request ID;
- ready figure requires safe asset;
- question reference integrity;
- legacy and v2 reads coexist.

### Frontend tests

- v1 payload still chooses legacy renderer;
- v2 payload chooses `LectioDocumentView`;
- section title appears once;
- all first-slice objects render;
- pending/failed/ready figure states render intentionally;
- teacher/student policy is applied outside Lectio package;
- no client-side reorder.

### PDF tests

Generate from the application route, not only the page-package fixture.

Check:

- A4 size;
- non-empty PDF;
- expected document/section titles;
- all expected block IDs represented in DOM before print;
- no schema/semantic errors;
- no horizontal overflow;
- no clipped answer lines/tables;
- page count captured as evidence, not used as a hard quality target;
- printBackground on/off does not alter pagination unexpectedly unless explicitly accepted.

## 2. Golden fixture

Primary fixture: conceptual, first-exposure photosynthesis lesson.

It must exercise:

- orient prose;
- build list/table;
- mechanism prose or figure;
- worked example or guided application where pedagogically honest;
- question placement from generated item IDs;
- one pending→ready figure transition.

Do not force every object into one lesson merely to exercise catalogue coverage. Separate contract fixtures cover unused objects.

## 3. Evaluation set for the planner

Before expanding scope, collect at least 30 section cases across:

- conceptual mechanism;
- conceptual classification;
- procedural method;
- factual organization;
- misconception confrontation;
- guided practice;
- independent check.

Human review records:

- intent fit;
- object fit;
- evidence specificity;
- brief specificity;
- section composition;
- repetition;
- `slot_concern` correctness.

This evaluation decides whether the planner should split into two calls. Do not decide by intuition alone.

## 4. Phase verification commands

Cursor must discover actual repository commands in Phase 0 and populate `scripts/verify-phase.ps1`. Minimum categories:

```text
page package: test, check, build, fixture PDF
backend: focused pytest, full pytest, Ruff, architecture guard
frontend: check, unit tests, build
contract sync: clean git diff after second run
browser: targeted Playwright route test
```

## 5. Evidence requirements

Every phase report includes:

- commands and exit codes;
- test counts;
- changed files;
- fixture/result paths;
- screenshots or PDF paths where relevant;
- pre-existing failures separated from new failures;
- exact blockers;
- rollback command/commit.

“Tests pass” without commands and output summary is not sufficient.
