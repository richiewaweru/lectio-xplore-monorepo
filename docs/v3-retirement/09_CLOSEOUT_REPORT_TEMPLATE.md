# V3 Retirement Closeout Report

## Summary

- Branch: `chore/retire-v3-legacy`
- Base SHA: `802b4f98`
- Final SHA: uncommitted
- Date: 2026-09-23
- Overall result: PARTIAL

One-paragraph summary:
```text
Legacy section writer, Stage 2 runner, Studio creation page, and $lib/api/v3 are deleted.
Current visual contracts now live in media.generation.contracts. The unit plan page,
Print editor, persisted ProductionBlueprint, and /api/v1/v3 chunked/document/PDF routes
remain as the live compatibility surface. Headed walk of How Shadows Form confirmed
preparation, Teaching Plan, and approval. Learn was admitted and then failed in the
current shared task writer. Print was not created. This branch is not ready for the
shared-writer architecture until that native path is green.
```

---

## Final canonical path

```text
Unit / path lesson
  -> Preparation
  -> Structural Plan
  -> Teaching Plan
  -> teacher approval
  -> native Learn realization  (application/unit_lesson + learn.*)
  -> native Print realization  (application/unit_lesson + print.*)
Live HTTP URLs for plan/approve/document/PDF stay /api/v1/v3
Print editor stays /studio/print/[id]
```

---

## What moved

| Old path | New path | Why current |
|---|---|---|
| `v3_execution.config.models` / llm helpers | `infra/authoring/model_policy`, `infra/authoring/structured_provider` | Live LLM slots used by native planning |
| `v3_execution` timeouts/retries/retry_runner | `infra/execution` | Shared retry used by visuals |
| item generator / errors / prompt | `curriculum/items` | Native preparation item generation |
| planning models / persistence / skeletons | `curriculum/planning` | Unit structural + teaching plan |
| visual executor / prompt / work-order types | `media/generation` (+ `contracts.py`) | Learn/Print figure pipeline |
| current `/v3` lesson-approach, realize, document, visuals | `application/unit_lesson/native_http.py` | Native realization HTTP |

---

## What was deleted

| Deleted path / subsystem | Zero-caller evidence | Replacement/current path |
|---|---|---|
| `v3_execution.executors/{section_writer,question_writer,answer_key_generator}` and Stage 2 runner/lanes | production imports removed; app starts without them | none — native pipeline does not write sections |
| `/generate/start`, repair, traces, signals, propose-intent studio routes | stripped from `v3_studio/router.py` | unit plan + native realize |
| `routes/studio/+page.svelte`, `routes/studio/generations`, V3 canvas/input/preview, `$lib/api/v3` | no remaining frontend imports | unit `/plan` `/learn` `/print`; PDF via `$lib/api/realizations` |

---

## Native routes migrated

| Old route/location | New route/location | Compatibility wrapper retained? |
|---|---|---|
| lesson-approach / realize-learn / realize-print / lectio-document / visuals | `native_lesson_router` still mounted at `/api/v1/v3` | yes — live clients keep the URL |
| chunked plan/status/approve/document/PDF | still `v3_studio_router` at `/api/v1/v3` | yes — unit plan + Print editor still call these |

---

## Frontend migrated

| Old API/component/route | New location or deleted | Evidence |
|---|---|---|
| `/studio?generation_id=` | deleted; unit page uses `/units/.../lessons/.../plan` | headed walk: Open Lesson href is `/plan` |
| `$lib/api/v3` | deleted | Print PDF uses `downloadGenerationPdf` |
| V3BlueprintPreview / V3SignalConfirmation | deleted | no remaining imports |
| `/studio/print/[id]` | kept | current Print editor |

---

## Remaining `v3` names

| Match | Why it remains | Safe/inert? | Future removal needed? |
|---|---|---|---|
| `/api/v1/v3` chunked + document + PDF + pack routes | unit plan page and Print editor still call these URLs | live adapter | yes, after URL rename |
| `print/http/v3_studio/*` | owns those live adapters + generation writer | live | rename later, not this cut |
| `v3_blueprint.models.ProductionBlueprint` | persisted generation blueprint / preview | persisted compatibility | yes, after record migration |
| `v3_blueprint.planning.retry` via `resume_stage2` | not invoked for new lessons; shutdown test requires the helper | inert for new gens | yes |
| `v3_execution.booklet_status` | generation writer booklet status | live | move with writer |
| `v3_execution.models` leftover writer/draft types | tests + booklet preview | mixed | yes |
| frontend `$lib/types/v3.ts`, `print/studio/v3-*` | Print document mapping | live | rename later |
| `/studio/print/[id]` | current Print editor | live | rename later |

---

## Verification

### Backend
```text
pytest tests/v3_execution/test_v3_execution_core.py
      tests/media/test_visual_qc_prompt.py
      tests/planning/test_phase05_visual_dispatch.py
      tests/v3_execution/test_visual_provider_telemetry.py
      tests/v3_execution/test_visual_prompt_style.py
-> 38 passed

Earlier: tests/planning/test_pre_worker_failure_sync.py
         tests/planning/test_native_status_payload.py
-> 20 passed after skeleton path fix
```

### Frontend
```text
Deleted Studio creation + $lib/api/v3. Grep shows no remaining imports of
V3BlueprintPreview, V3SignalConfirmation, or $lib/api/v3.
Frontend unit test suite was not re-run after the last deletions.
```

### App startup
```text
uvicorn app:app --app-dir src --host 127.0.0.1 --port 8000
Application startup complete after visual-contract move.
Vite on 5173 with VITE_API_TARGET=http://127.0.0.1:8000.
```

### Static searches
```text
Current Learn/Print visual callers import media.generation.contracts.
Remaining v3_execution / v3_blueprint / v3_studio hits are the adapters listed above.
```

---

## E2E proof

### Unit / lesson
```text
Unit a5b9e24f-9c88-407b-bde3-71a9d27e3dd2 How Shadows Form Science Grade 6
Lesson 0fc47fa7-fd86-4e6e-9f58-e89d0eafe8fa Light Travels in Straight Lines and Can Be Blocked
Generation 913d086a-d1ef-4119-90f4-33e6aa0a08e1
Headed session v3-retire as richard maina, 2026-09-23 ~17:52 UTC+3
```

### Preparation -> Structural Plan
```text
Unit page: lesson 1 status "prepared", workspace "Approved".
Plan page checklist: Structural plan ✓.
```

### Teaching Plan
```text
Plan page checklist: Teaching plan ✓, Approval ✓.
Heading "Teaching plan approved". Review: Status approved, revision 2,
verified approved revision 1, hash
c530b26f42ebe8312f8bce6580941e02453772c0eaa836466cb14875591be9d6.
Pedagogical arc and orient/explain/contrast/check slots rendered.
```

### Learn
```text
Plan header: Learn · failed.
Learn page heading "Learn needs attention":
"shared task writer must return exactly one task per response-bearing block"
Retry Learn present. This is current native authoring, not leftover Studio.
```

### Print
```text
Plan header: Print · not created.
Create Print button present on the plan page. Print was not started in this walk.
Print tab click stayed on the Learn body (URL did not change). A later
playwright-cli open of /print started a new Chrome and dropped the Google session.
```

### Visuals
```text
Not reached. Learn failed before a Learn document; Print was not created.
```

### Retries
```text
Retry Learn button observed, not pressed (same writer would fail again).
```

### Negative legacy proof
```text
Open Lesson / Open Learn / Open Print go to /units/.../plan|learn|print,
not /studio?generation_id=. Studio creation page is deleted. Section writer
and /generate/start are deleted from the running API.
```

---

## Commits

```text
none — work is uncommitted on chore/retire-v3-legacy
```

---

## Known issues left intentionally

```text
/api/v1/v3 URL prefix and /studio/print editor path kept because live clients
still call them. ProductionBlueprint kept for persisted generations.
resume_stage2 kept only because the shutdown test asserts the helper exists.
```

Learn writer failure is **not** leftover Studio and is **not** acceptable
canonical-path debt. It blocks a PASS closeout.

---

## Ready for next architecture?

NO

Next planned undertaking:

```text
Shared content realization:
Teaching Plan
 -> section continuity contracts
 -> shared section/content writer
 -> canonical document
 -> Learn / Print path-specific realization
```
