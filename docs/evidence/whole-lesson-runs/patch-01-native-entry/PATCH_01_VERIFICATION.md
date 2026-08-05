# Patch 01 Verification Checklist

**Branch:** `whole-lesson-native-e2e`  
**Date:** 2026-08-05  
**Authority:** xplore-native-entry-pack-v1.1

## Contract boundary

- [x] `body` cannot cause `ConceptCard` validation failure.
- [x] `must_establish` cannot cause `ConceptCard` validation failure.
- [x] misconception `rationale` cannot cause validation failure.
- [x] planner `concept_id` cannot override the approved concept ID.
- [x] generated objective cannot override or paraphrase the approved path objective.
- [x] id-only / empty misconception shells are dropped before strict validation.

## Native routing

- [x] `scope="all"` returns true for conceptual first exposure.
- [x] `scope="all"` returns true for factual first exposure.
- [x] `scope="all"` returns true for procedural or another available shape.
- [x] new runs set `document_contract_version=2`.
- [x] new runs do not call `resume_stage2()`.

## Skeleton-derived packet

- [x] conceptual packet has its conceptual slots in structural order.
- [x] factual packet has `orient/organise/guided/independent/check`.
- [x] procedural packet matches its actual selected skeleton.
- [x] validation compares plan sections with packet slots.
- [x] no global conceptual slot constant decides non-conceptual validity.

## Permissive architecture behavior

- [x] missing `typical_intents` does not block reaching the teacher gate.
- [x] missing block bounds use safe defaults.
- [x] incomplete must-establish evidence coverage is advisory, not gate-blocking.
- [x] unknown intents remain rejected.
- [x] excluded intents remain rejected.
- [x] slot order cannot be changed by the LLM.
- [x] English word `questions` in teaching prose is not treated as an object leak.

## Question wall

- [x] questions blocks still require approved item IDs in validation (unchanged contract).
- [x] no writer-side question invention added in this patch.

## Smoke evidence

| Shape | Generation ID | Skeleton | Sections | dcv | Final Patch-01 stage | Pass |
|---|---|---|---|---|---|---|
| conceptual | `208f45d5-fd2c-4d7b-8f3b-18c3dc895d92` | `conceptual.first_exposure` | orient, explain, contrast, check | 2 | awaiting_teaching_approval | yes |
| factual | `56331eb7-72de-4cd7-9d3c-9affbbd91fa9` | `factual.first_exposure` | orient, organise, guided, independent, check | 2 | awaiting_teaching_approval | yes |
| procedural | `030c6461-5b2d-4d2f-9f9f-3603fb88adc7` | `procedural.first_exposure` | orient, recall, model, guided, check | 2 | awaiting_teaching_approval | yes |

Supporting artifacts:

- [`smoke-results.json`](smoke-results.json)
- [`db-verification.json`](db-verification.json)
- smoke console logs in this folder

DB checks for each generation:

- native `page_document_v2` present
- lesson_packet slots == structural roles == teaching_plan sections
- stage `awaiting_teaching_approval`
- teaching plan persisted

Legacy path:

- no Builder redirect for these native prepares
- no new-generation `resume_stage2` / legacy section-brief / booklet-pack assembly observed for these runs

## Explicitly deferred to Patch 02

- [ ] background worker
- [ ] lease/heartbeat
- [ ] resume completed blocks
- [ ] isolate failed blocks
- [ ] bounded parallel writers
- [ ] assemble from DB state
- [ ] authoritative terminal state
- [ ] complete native PDFs

## Known limitations (expected in Patch 01)

1. Slots without `typical_intents` produce weak/generic briefs.
2. Factual guided/independent/check may compete for a thin approved-item pool.
3. Teaching briefs and form choices may be repetitive.
4. Writers may still fail after teaching approval (Patch 02).
5. Native execution still lacks resume and failure isolation (Patch 02).
6. Conceptual YAML includes `contrast`; some prepares omit `confront` when misconception count is zero (existing skeleton/toggle behavior).

## Deviations from the pack prompt

1. Conceptual evidence uses repo YAML order including `contrast` (often 4 slots when confront is toggled off), not the pack diagram’s simplified `orient/explain/confront/check`.
2. Beyond the five listed file edits, Patch 01 also required:
   - native variant materialization without legacy component selections
   - empty-`typical_intents` departure permissiveness
   - OBJECT_LEAK false-positive fix for English words like `questions`
   - `MUST_ESTABLISH_UNCOVERED` made advisory
   - empty misconception shell coercion
3. Local smoke used the API driver (`scripts/patch01_native_entry_smoke.py`) rather than full browser UI clicks; teacher-gate stage and teaching-plan persistence were verified via API + DB.
4. Broader `tests/planning/` has one pre-existing unrelated failure: `test_phase5_prompts_are_verbatim[component-selector-v1.txt]` (prompt header / encoding drift). Focused Patch 01 suites: **34 passed**.

## Recommended Patch 02 starting point

1. Writers: save failed markers and continue siblings instead of raising.
2. Resume: load saved block results; skip ready; retry failed/missing.
3. Assembly: reload from DB, never from the in-memory results list.
4. Background teaching approval with a DB-backed lease worker.
5. One authoritative terminal stage written in a finally block.
