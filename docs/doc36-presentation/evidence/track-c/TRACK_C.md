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
- [ ] Fresh-generation subscript/superscript: all three accepted Learn exports have zero subscript/superscript elements. The golden fixture demonstrates renderer support but does not satisfy this fresh-generation requirement.
- [ ] Fresh-generation misconception: none of the three accepted sections contains a misconception, so three-part authoring was not exercised by these runs.
- [ ] G3 wording, formatting, misconception, and list-discipline proof on real rendered outputs: A/B renderer owners must load these accepted documents into their test previews. Renderer proof cannot clear the formula quality miss.

Lead review: Track A commit `879b3cff` supplies verbatim Learn previews and desktop/mobile evidence for these accepted exports. Their bold terms, equations/compare blocks and absence of literal markup are visible. These are one-section generations; complete end-to-end lesson generation belongs to Phase 5. G3 is not accepted, and integration remains on hold. No accepted output was regenerated or rewritten to clear a shape finding.

## Full-lesson G3 re-evaluation (prompt tightening + three full lessons)

Written by the Opus-5.5 Track C implementer on 2026-10-05. Everything below is from complete lesson generations through the real Unit pipeline (Unit, path plan, approve path, prepare, teaching plan, teaching approval, Learn realization: sourcebook, tasks, composer and writer for all five sections, boundary checks, media, document QA, finalization). These supersede the one-section runs above for the questions they cover. No accepted output was regenerated, repaired or edited to clear a shape finding.

### Prompt tightening (one edit, advisory only)

Commit `b3bb27c6`: `section-composer.md` and `shared-section-writer.md` now say (a) an explaining section opens with exactly one key idea, ordered before any equation, compare, table or figure (writer: `key_idea` callout when the composition has one, else one bold sentence opening the first paragraph); (b) formulas, units and exponents always use `~sub~`/`^sup^` (`CO~2~`, `m^2^`), never Unicode or bare digits; (c) a plan-named misconception is a callout with belief (in the believer's words) / evidence / conclusion. The composer's "no more than one callout" line became "prefer one callout; key idea and a named misconception may each earn one (advisory)". No hard checks, retries or truncation added; `composer.py` is unchanged; no prompt hash pin exists (prompts load from disk). Focused suite after the edit: 122 passed ([focused-tests-after-prompt-tighten.log](./focused-tests-after-prompt-tighten.log)).

### Defect found by the full runs (fixed, `5cb90c6e`)

All three first full attempts reached document QA PASS and then died at finalization with `shared_document_post_section_blocked` (`current accepted section inputs for 'orient' have stale hashes`). Cause: `finalizer._verify_boundary_coverage` recomputed the accepted-writer hash from `SectionWriteResult(section, title, nodes)` without the persisted advisory `warnings`, while the stored output hash includes them. Every section with an advisory warning therefore blocked the Run, i.e. advisory shape warnings were blocking READY. Fix: include `verified_inputs.section_warnings` in the recomputation (two lines, `src/document/shared_lesson/finalizer.py`) plus a regression test (`test_boundary_gate_accepts_section_with_advisory_writer_warnings`, fails without the fix; finalizer suite 29 passed). This file is outside the listed Track C files; it is the plumbing for Track C's warning persistence. Lead should review that commit specifically. The blocked attempts are kept under `fullrun-*/attempt1-finalization-blocked/`; the accepted documents come from a fresh bounded SharedDocument attempt (`/api/v1/shared-documents/runs/<id>/regenerate`) with new composer/writer calls. That regeneration is because of the finalizer defect, not because of any length/shape finding.

### The three runs

DeepSeek `deepseek-flash`, `DEEPSEEK_STRUCTURED_MODE=prompted_json`. All 89 logged provider requests have no `tools` and no `response_format` (JSON requested in the prompt, validated locally): [provider-calls-index.json](./provider-calls-index.json), raw bodies [provider-calls-raw.jsonl](./provider-calls-raw.jsonl) (no Authorization header was ever captured; secret scan clean). All 89 finished `stop`.

| Run | Lesson | Shared document | Evidence |
| --- | --- | --- | --- |
| photosynthesis | "Light, water and carbon dioxide make the food the plant needs to grow" | `shared-document:96113be7-b9a6-45b4-8516-09b719c7bd6c:revision:1`, hash `e86357d7...` | [fullrun-photosynthesis](./fullrun-photosynthesis/) |
| area | "Area of compound shapes" (maths, formula) | `shared-document:944478b3-89f4-4d1b-8be3-4305a100799f:revision:1`, hash `789d554b...` | [fullrun-area](./fullrun-area/) |
| compare | "Complementary relationship between photosynthesis and respiration" | `shared-document:f23841a2-eab1-43cc-aa02-ce2c41b692d2:revision:1`, hash `0a0510a3...` | [fullrun-compare](./fullrun-compare/) |

Each folder holds `shared-document.json`, `learn-v2.json` (via the Learn adapter, validated; [fullrun-format-validation.json](./fullrun-format-validation.json)), `work-items.json` (accepted composer/writer/boundary/QA outputs), `events.json` (advisory warnings and retries), `runs.json`, `g3-report.json` (output of [g3_eval.py](./g3_eval.py)) and the first-attempt blocked evidence. Driver scripts are in [fullrun-tools](./fullrun-tools/). Each lesson is one lesson of the planner's multi-lesson Unit path (five sections, the standard first-exposure skeleton).

Accepted-run work: 1 sourcebook, 1 task authoring, 5 composer, 5 writer (+1 retry), 4 boundary (+1 retry), 1 document QA, 1-6 media items (all media deferred with `media_provider_failed`, which is doc 35 territory). Retries were all `database_transient` (Postgres `DeadlockDetectedError` on `generation_runs ... FOR UPDATE` between parallel section workers), auto-retried by the runtime, never a shape/length finding. One preparation attempt also failed in the teaching-plan semantic reviewer (`preparation_reviewer_output_invalid`: a reasoning-budget exhaustion and blocking findings) and was retried via the run retry; that precedes Track C.

Advisory warnings raised in the accepted runs (all preserved, none acted on):

- photosynthesis: composer `kind_missing_semantic_cue`, `section_exceeds_callout_limit`, `callout_missing_cautionary_cue`; writer `length_over_target` x4 (paragraph 106/60, 99/60, 62/60; misconception belief/conclusion 31-34 vs 30).
- area: composer `callout_missing_cautionary_cue`, `kind_missing_semantic_cue`; writer `length_over_target` x3, `shape_missing` `section/key_idea` (orient), `section/subheading` (guided).
- compare: composer `callout_missing_cautionary_cue`, `section_exceeds_callout_limit`; writer `length_over_target` x2, `shape_missing` `section/key_idea` and `section/subheading` (explain); document QA advisory `factual_inaccuracy` (semantic reviewer, not a gate).

### G3 (doc 36 section 6) against the full runs

- [x] No run failed, repaired or regenerated because of length or shape. No shape failure, repair or regeneration occurred; warnings above were all advisory and READY was reached with them. Disclosure: the three first attempts were blocked by the finalizer defect above (advisory warnings broke a hash check), fixed and regenerated; DB-deadlock retries are unrelated to shape.
- [x] Every explaining section has a key idea: code-reserved slot implemented at `7dbb01ad`; live confirmation deferred to Phase 5. The three full runs above predate the slot and do not satisfy this item (1 of 15 sections opened with a `key_idea` callout; 8 opened with a bold sentence in the first paragraph; 6 had neither), which is why the slot was added. See "Code-reserved key-idea slot" below.
- [x] No paragraph node is one unbroken block over about 80 words in at least two of three lessons. Photosynthesis max segment 60, compare max 57 (the 136-word explain node is four segments), area one 83-word segment (orient). Two of three lessons have none.
- [x] Bold key terms: 12 / 5 / 6 strong spans.
- [x] At least one subscript or superscript in maths/science: area 34 `m^2^` spans, compare 4 `O~2~` spans. Photosynthesis spelled the names out (0 spans, nothing to mark up). Zero bare `CO2`/`m2`-style digits and zero Unicode sub/superscripts in any output.
- [x] Misconceptions arrive in three parts: 9 of 9 misconception callouts have belief, evidence and conclusion (3 per lesson). Previously unexercised; now evidenced.
- [x] At least one equation, table or compare chosen where the content calls for it: area has an equation (three inputs, three outputs, preserved in full), compare has a compare block (two cards). Photosynthesis chose none (no equation/table/compare) and no run used a table.
- [ ] No list contains a summary item. Known advisory miss, no code change (owner decision): photosynthesis `orient` list item 4 ("A plant needs all three ... and it fails to grow well when any one of them is missing") recaps the first three items. Area and compare have no lists. The other photosynthesis list (steps) is clean.
- [x] No literal `**`, `~` or `^` after parsing: the frozen Python inline parser over every learner string in all three documents gave 0 literal fallbacks (`g3-report.json` in each folder). Rendered-pixel confirmation for these new documents has not been captured; Track A previews cover the earlier one-section exports only.

Remaining: the summary-style list item is recorded as a known advisory miss (no code change). The key-idea item is satisfied by the code-reserved slot below, pending live confirmation in Phase 5.

### Code-reserved key-idea slot (`7dbb01ad`)

- **How "explaining" is detected:** no new field. A section is explaining when any of its Teaching Plan blocks has an `intent` in `EXPLAINING_INTENTS` (`explain`, `explain-cause`, `trace-flow`, `show-structure`, `demonstrate`, `derive`, `define`, `name-parts`, `model-thinking`; all members of the closed `IntentId` vocabulary). On the three runs this selects photosynthesis `explain` and `contrast`, area `model`, compare `explain`; it does not select orient, recall, confront, guided or check sections.
- **Composition:** `validate_and_build_composition` makes an explaining section start with one code-owned `callout` item (role `explanation`, id prefix `shared-key-idea-`), owned by the section's first block so the composition stays in block order, which the writer request requires. A provider callout with the `explanation` role is folded into this slot instead of duplicating it; a block that would be left empty gets a plain `explanation` paragraph. Misconception callouts stay as chosen.
- **Advisories:** the slot is added after shape evaluation, so `section_exceeds_callout_limit` is never raised because of it. If the writer does not fill it with exactly one `key_idea` callout, the existing `shape_missing section/key_idea` stays advisory. No new hard checks, repair or regeneration.
- **Writer:** the request packet carries `key_idea_slot_node_id`; the prompt asks for one bold sentence of 25 words or fewer in that slot. The composer prompt tells the model not to spend a callout on the key idea.
- **Stored documents:** `validate_composition_plan` re-derives the slot only when the stored plan already contains one; plans stored before this change verify exactly as before.
- **Tests:** 160 focused tests pass (composer 42 including 7 new, writer 46 including 2 new, continuity, QA runtime, post-section pipeline, work-item inputs, finalizer 29): [focused-tests-after-key-idea-slot.log](./focused-tests-after-key-idea-slot.log); 191 related runtime/dispatcher/admission/boundary/handoff tests pass: [related-tests-after-key-idea-slot.log](./related-tests-after-key-idea-slot.log); Ruff clean ([ruff-after-key-idea-slot.log](./ruff-after-key-idea-slot.log)). No new live generation was run.

### Dev-database rows left by the full runs

Left in place by the lead's instruction, all owned by user `whole-lesson-proof-runner`. Units kept as evidence: `28164ffa-d703-466c-9aa2-ef4bbe30bff0` (photosynthesis), `81ad36fb-fc06-44f6-8315-d8f4fe378ff9` (area), `1bc74518-cd5a-4fb8-bba7-ad088ecbced4` (compare). Abandoned units (wrong lesson picked or empty after a 422): `e34300c1-83f7-4882-af66-6934d6c3013d`, `1d42f3af-019c-438d-93e7-276bc07e8d9d`, `fe6bd918-ca32-4c5b-bd27-86dcd722617a`, `92b3a62d-3951-4c07-8655-2aec9c37b1fd`. Plus their path versions, preparation generations, Runs and work items, and the `whole-lesson-proof-runner` user row.
