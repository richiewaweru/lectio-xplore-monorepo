# Prepare Lesson — forensics

**Headline: Prepare Lesson does not fail. It succeeded, returned `200`, created a
generation, persisted a real structural plan, and parked at a legitimate review gate.**

## Pre-click state

| Field | Value |
|---|---|
| URL | `http://localhost:5173/units/907b1dab-11fd-49fc-ac23-060d45b446b8` |
| Unit ID | `907b1dab-11fd-49fc-ac23-060d45b446b8` |
| Path version ID | `45fb2e18-6aeb-499b-8172-b32078869ce7` (v1, **approved**) |
| Path lesson ID | `63cc7fec-05bb-4783-b27b-2cff75550b50` (position 3, "Why Light is Essential") |
| Concept ID | `d42109c3-aaab-4881-9a5a-104acedf9dd4` |
| Objective | "Explain why light is necessary for plants to make food" |
| `primary_knowledge_type` | `conceptual` |
| Controlled lesson shape | `conceptual.first_exposure` |
| Lesson mode | First exposure |
| Browser console | clean (only pre-auth 401s and a Google COOP warning) |
| Generations in DB | 4 (none for this unit) |

The UI's "shape debug" panel showed the canonical BASE skeleton
`orient → explain → contrast → confront → check + SHARED`, with the `core`
(medium-support) variant removing `confront` via toggle
`misconception.confront_per_belief` — "No unaddressed approved misconception needs this
confrontation slot."

## The request

```
POST /api/v1/units/907b1dab-11fd-49fc-ac23-060d45b446b8
     /path/lessons/63cc7fec-05bb-4783-b27b-2cff75550b50:prepare
-> 200 OK          request_id=b74f1261
```

Clicked `15:23:54.067Z`, responded `15:24:38.814Z` — **44.75 s** of browser wait.

## Latency decomposition

| Segment | Window | Duration | Kind |
|---|---|---|---|
| Click → provider request sent | 15:23:54.067 → 15:24:06.946 | **12.88 s** | browser sequencing + backend orchestration |
| Provider TTFB | 15:24:06.946 → 15:24:07.418 | **0.47 s** | provider |
| Provider body stream | 15:24:07.419 → 15:24:38.411 | **30.99 s** | provider |
| Persist + respond | 15:24:38.411 → 15:24:38.814 | **0.40 s** | backend orchestration + persistence |
| **Total** | | **44.75 s** | |

**Provider latency is 31.47 s of the 44.75 s — 70 %.** Persistence after the model
returned cost 0.40 s. Retry latency: **zero** — one attempt, HTTP 200 first try.

Provider: DeepSeek (`openai_compatible`, `https://api.deepseek.com`), model
**`deepseek-v4-pro`**, `max_completion_tokens=120000`, `stream=False`,
`x-ds-trace-id=1a47ce2c90b4449a8ca31f9975781a0d`.

The 12.88 s before the provider call is the one segment worth attention: the frontend
was still issuing `GET .../groups` at `15:24:03.191`, i.e. 9.1 s after the click, so
much of that window is browser-side sequencing rather than backend compute.

## The eight forensic questions, answered separately

| Question | Answer |
|---|---|
| Was a generation row created? | **Yes** — `3f40587d-4846-4fdb-a07f-3eb48b0a2257`, `created_at 15:24:38.573949` |
| Was chunked state created? | **Yes** — 28,165 bytes of `chunked_state_json` |
| What stage was persisted? | `awaiting_review` (both `generations.status` and `chunked_state.stage`) |
| Was the structural planner called? | **Yes** — one DeepSeek call with the `path_structural_planner_page` prompt |
| Did the LLM return? | **Yes** — HTTP 200, complete body in 31.47 s, no retry |
| Was validation reached? | **Yes** — output parsed into a typed `PathStructuralPlan` and stored |
| Was anything persisted after validation? | **Yes** — `structural_plan` (10 keys), `section_briefs` (4), `context` (9 keys) |
| Did the browser receive the real backend error? | **N/A — there was no error.** 200 with a usable payload |

## What was persisted

```
chunked_state_json
  stage                  = "awaiting_review"
  native_whole_lesson    = true          <- native path engaged
  path_prepared          = true
  execution_started      = false         <- nothing downstream started
  structural_plan        = {10 keys}
  section_briefs         = {orient, explain, contrast, check}
  context                = {9 keys incl. scope_contract, resource_spec, lesson_mode}
  failed_sections        = []            <- empty
```

`structural_plan.document_contract_version = 2` — the LectioDocumentV2 contract, not a
legacy shape.

## Structural plan content (real, not placeholder)

Anchor: *"A sunflower seedling on a sunny windowsill grows tall and green, while another
kept in a dark closet…"*, marked for reuse across slots.

| # | Section id | Role | card_id | Title |
|---|---|---|---|---|
| 1 | `orient` | orient | null | A Tale of Two Sunflowers |
| 2 | `explain` | explain | `d42109c3…` | Light as the Energy Source for Photosynthesis |
| 3 | `contrast` | contrast | null | With Light vs. Without Light: Seeing the Boundary |
| 4 | `check` | check | null | Check Your Understanding |

Question plan: 1 item (`q-check-1 → check, cold`). Prior knowledge: 9 entries carried
from the path. Every section carries a transition note. No fixtures, no placeholders.

## Contract check: path → structural planner → stored plan

| Boundary | Producer | Consumer | Result |
|---|---|---|---|
| Path → prepare | approved `path_versions` v1 + `path_lessons` row | `prepare_path_lesson` (`planning/bridge.py:412`) | **accepted** — objective, `objective_hash`, `concept_id`, `must_establish`, `scope_contract`, `prior_established` all forwarded verbatim |
| Prepare → structural planner | lesson packet with `native_whole_lesson: true` | `deepseek-v4-pro` | **accepted** — 4 slots sent (`orient`, `explain`, `contrast`, `check`); `confront` already removed by the variant toggle upstream |
| Structural planner → stored plan | `PathStructuralPlan` JSON | chunked state | **accepted** — section `id`/`role` echoed verbatim in supplied order; `card_id` attached only to the teaching section |

No missing fields, no rejected payloads, no silent recomputation at this boundary.
The prompt explicitly forbids the planner from choosing components, page objects or
question text, and the stored plan contains none — the separation held.

## Classification

**No failure at Prepare.** Nothing to classify.

The user-visible complaint "preparing the lesson fails" is not reproduced. What
actually happens is that Prepare succeeds and stops at the **structural review gate**
(`awaiting_review`), which is a designed teacher checkpoint, not an error. The Studio
route renders that gate correctly with the full plan and Review / Adjust / Regenerate
controls.

Two real defects sit next to it and are the likely source of the impression that
Prepare fails — see `31-status-drift.md`.
