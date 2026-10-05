# Track C evidence

Checkpoint commit: `074bc571` (`feat(doc36): make section shaping advisory`).

## G3 provider evidence

The three fresh plans used unique evidence run, job, and document identities. Each used the live composer provider once and the live writer provider once. The provider responses and requests are retained in the per lesson JSON records; no lesson rows or WorkItems were created.

| Plan | Provider result | Calls | Advisory record |
| --- | --- | ---: | --- |
| Photosynthesis | writer accepted | 2 | none |
| Area of a rectangle | writer accepted | 2 | `shape_missing` at `section/key_idea` |
| Photosynthesis and respiration | writer accepted | 2 | none |

Summary: [provider-run-summary.json](./provider-run-summary.json). Raw records: [photosynthesis.json](./photosynthesis.json), [formula.json](./formula.json), and [comparison.json](./comparison.json). The records contain only structured plan/provider payloads, accepted documents, and redacted errors; a secret-pattern scan found no credential values.

Validated post-generation exports, built from these accepted SectionWriteResults without provider reruns: [photosynthesis SharedLessonDocument](./photosynthesis-shared-document.json), [formula SharedLessonDocument](./formula-shared-document.json), [comparison SharedLessonDocument](./comparison-shared-document.json), and the corresponding [photosynthesis LearnDocument v2](./photosynthesis-learn-v2.json), [formula LearnDocument v2](./formula-learn-v2.json), and [comparison LearnDocument v2](./comparison-learn-v2.json). [format-validation.json](./format-validation.json) records frozen SharedLessonDocument hashes, node counts, and zero LearnDocument validation errors.

## Advisory audit

- Composer paragraph runs, node ceilings, callout ceilings, semantic cue misses, and heading cue misses are recorded in `SectionCompositionPlan.warnings`. They do not alter provider choices or invoke repair. The former soft auto-fix helper and all call sites were removed.
- Writer paragraph, list-item, table-cell, callout, misconception, equation-input/output, and comparison-card targets are recorded in `SectionWriteResult.warnings`. Full written text, equation terms, and comparison cards remain in the accepted result.
- Writer task-answer and unsupported-number findings retain the established bounded repair and final-attempt warning behavior. Identity, schema, leakage, and task correctness remain actionable.
- Inline vocabulary is preserved in both prompts and request payloads: strong, emphasis, subscript, superscript, and paragraph breaks. The frozen inline AST prevents `CO~2~` and `m^2^` notation from creating numeric-fact warnings while malformed markers remain checked.
- Composition warnings are loaded with verified work-item inputs, merged with writer warnings by the post-section pipeline, persisted in QA dispatch, and emitted as teacher-visible quality flags. Advisory warning paths retain the actual code, structural path, observed count/value, and target where applicable.
- Synthetic composer/writer shape warnings are excluded from semantic blocking. A semantic reviewer returning a shape finding is also advisory under a blocking gate; mixed shape plus synthetic leakage keeps the leakage issue and drops only the shape finding from the actionable issue list.
- Continuity expected-node declarations include `equation`, `quote`, and `compare`. Exact count, identity, order, and ownership checks remain contract checks for code-owned node identity; presentation count and run targets are advisory.

## Focused validation

Using the repository backend virtualenv and a test JWT secret:

```text
python -m pytest tests/document/test_section_composer.py tests/document/test_section_writer.py tests/document/test_shared_lesson_continuity.py tests/document/test_shared_qa_runtime.py tests/document/test_shared_lesson_post_section_pipeline.py tests/document/test_shared_lesson_work_item_inputs.py -q
122 passed in 58.91s

python -m ruff check <owned Track C source and test files>
All checks passed!

python -m compileall -q src/document/shared_lesson
passed
```

The focused QA suite after the mixed semantic-shape regression is 12 passed. The separate writer suite is 44 passed, composer suite 35 passed, and continuity suite 18 passed.

Raw command output: [focused-tests.log](./focused-tests.log) and [ruff.log](./ruff.log).

## G3 quality checklist

- [x] Targeted backend prompt/composer/writer/continuity/QA tests and Ruff.
- [x] Three actual fresh composer/writer provider generations.
- [x] Photosynthesis, maths formula, and comparison coverage.
- [x] Raw documents, provider-call logs, and advisory warnings retained.
- [x] Accepted outputs exported as valid SharedLessonDocuments and LearnDocument v2 JSON.
- [x] Every downgraded length/count/paragraph-run/callout check is advisory; no shape retry, failure, truncation, padding, or READY change occurred in the fresh calls.
- [x] Hard identity/schema/leakage/task checks remain bounded and actionable.
- [ ] Formula quality miss: the formula section explains a formula but has no key-idea callout (`shape_missing section/key_idea`). This remains an explicit advisory miss.
- [ ] G3 wording, formatting, misconception, and list-discipline proof on real rendered outputs: A/B renderer owners must load these accepted documents into their test previews. Renderer proof cannot clear the formula quality miss.
