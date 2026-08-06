# Master Grok Implementation Prompt

You are implementing the native page-oriented Xplore flow in:

- Repository: `richiewaweru/lectio-xplore-monorepo`
- Branch: `pageobject-integration`
- Inspected baseline: `0cc0ff3454f231cdbd357f4040fa27d0f2bb144e`

Read every artifact in this pack before editing code. Treat `11_ACCEPTANCE_CHECKLIST.md` as the completion contract.

## Objective

Complete a production-shaped native-only flow that produces a valid `LectioDocumentV2` end to end. Do not stop after planning, form selection, or unit tests. Finish persistence, rendering, and PDF proof.

## Existing defects you must account for

The current writer module supports only:

```text
prose, list, table, figure, worked-example, questions
```

It enriches `questions.items[]` with `options`, `correct_key`, and `answer_key_ref`. These fields violate the current Lectio `questions-content` schema. Multiple-choice content belongs in `choices`; answers belong in the top-level `answer_key`.

The current LLM writer has no typed `output_type`; it embeds a contract in the prompt and parses arbitrary JSON. Validation is delayed until document assembly.

The current writer repair path repeats the same call without including the invalid output or validation errors.

Current execution is block-parallel rather than section-oriented. Refactor the orchestration so sections are the primary parallel unit, with maximum four section jobs concurrently. Blocks within a section may be concurrent only when they have no declared dependency.

The native failure state is stored under `chunked_state_json.page_document_v2`, but the public status endpoint still reads several legacy top-level fields. Fix native status reporting.

Legacy runtime paths muddy the production flow. Disable or remove them from all new generation routing.

## Required design

### 1. One general writer engine, strict form modes

Implement a writer registry for:

```text
prose
list
table
figure
aside
worked-example
questions
choices
```

The engine may be general in subject knowledge, but the requested object selects a strict form-specific output model. Never accept arbitrary JSON.

`heading` is structural: normal Xplore section titles render as headings.

`answer-key` is structural: it is assembled at document level from assessment outputs.

### 2. Assessment generation

Generate student assessment content and answer entries in one logical pass.

- Open responses become `questions`.
- Multiple choice becomes `choices`.
- The answer entry uses the same stable ID as the student item/block.
- Merge all section answer entries into one document-level `answer_key`.
- Validate that every answer references an existing assessed item and every assessed item has exactly one answer.
- Validate MCQ answers against available option letters.

### 3. Figures

Do not require live image generation for this pass. Emit a valid pending figure:

```json
{
  "asset": {
    "kind": "image",
    "status": "pending",
    "request_id": "stable-id"
  },
  "caption": "planned visual",
  "alt_text": "meaningful description",
  "width": "main"
}
```

A pending visual must not prevent document readiness or PDF export. Render a useful placeholder.

### 4. Validation boundary

For each writer output:

```text
parse
→ validate against selected content model
→ reject unknown fields
→ persist only validated content
```

Validation must occur before saving a block/section as ready.

### 5. Repair boundary

On contract-invalid output, make one fresh repair call containing:

- original block brief;
- requested object;
- original writer contract;
- previous invalid output;
- exact validation errors;
- instruction to return the complete corrected JSON object only.

Do not count transport retries as schema repair. Persist both attempts in evidence.

### 6. Parallelism and resume

Use maximum four concurrent section jobs.

A section job:

1. receives lesson and section context;
2. generates its blocks;
3. validates every output;
4. returns assessment answer entries;
5. persists its completed outcomes independently.

Preserve planned section and block ordering regardless of completion order. Resume must skip validated completed work.

### 7. Mechanical assembly

Assembly performs no LLM calls and no content repair.

It:

```text
loads validated outcomes
→ verifies expected IDs
→ sorts by planned positions
→ builds sections
→ merges answer entries
→ checks references
→ validates LectioDocumentV2
→ persists
→ reloads and validates
```

Any assembly failure must identify the exact scope and cause.

### 8. Honest status

Expose native progress and errors from `page_document_v2`, including:

- stage;
- section totals and completed count;
- block totals and completed count;
- failed section/block IDs;
- failure scope;
- code;
- message;
- retryable;
- validation details;
- whether document exists.

Never return `failed_terminal` with `error: null`.

### 9. Native-only production routing

New generations must never enter:

- v1 document creation;
- legacy builder conversion;
- legacy stage2;
- blueprint execution;
- legacy retry-section flow;
- legacy assembly or viewer.

Historical data can remain readable if necessary, but production creation and continuation are native-only.

## Mandatory execution method

Follow `04_STAGE_GATED_IMPLEMENTATION_PLAN.md`.

For each gate:

1. inspect current code;
2. implement;
3. run targeted tests;
4. record exact commands and complete results;
5. fix failures;
6. rerun until green;
7. update `docs/evidence/native-e2e-v1/GATE_XX_REPORT.md`;
8. only then continue.

Do not claim a gate passed because code looks correct.

## Mandatory test sequence

1. Unit tests for all form models and registry.
2. Scripted mock provider tests.
3. Assessment/reference integrity tests.
4. Parallel out-of-order section tests.
5. persistence/resume tests.
6. mechanical assembly and reload tests.
7. native status API tests.
8. renderer and PDF tests.
9. all-forms mocked end-to-end lesson.
10. one real LLM smoke lesson.

Use all fixtures in `08_FIXTURES/` and all scenarios in `09_MOCK_SCENARIOS/mock_llm_scenarios.yaml`.

## Required completion outputs

Create:

```text
docs/evidence/native-e2e-v1/
├── 00_SUMMARY.md
├── GATE_01_REPORT.md ... GATE_10_REPORT.md
├── commands.log
├── pytest-targeted.log
├── pytest-native-suite.log
├── frontend-tests.log
├── mock-run-report.json
├── real-llm-run-report.json
├── generated-lectio-document-v2.json
├── reloaded-lectio-document-v2.json
├── student.pdf
├── teacher.pdf
├── student-render.png or html
├── teacher-render.png or html
├── status-timeline.json
└── legacy-reference-audit.txt
```

## Stop conditions

Do not stop with:

- “the flow should work”;
- tests that bypass persistence;
- a generated block without a full document;
- a document JSON without rendering;
- rendering without PDF;
- a real-provider failure before mocks are green;
- unexplained 500s;
- null terminal errors;
- skipped forms;
- disabled assessment answer keys.

## Final response format

Return:

1. concise implementation summary;
2. files changed;
3. tests run with pass/fail counts;
4. mock scenario table;
5. generated document and PDF paths;
6. exact real-LLM result;
7. remaining issues separated into:
   - provider-output issue;
   - application issue;
   - intentionally deferred feature.

If any acceptance item is not met, say the pass is incomplete.
