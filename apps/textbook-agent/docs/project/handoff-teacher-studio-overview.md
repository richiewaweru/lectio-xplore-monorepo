# Handoff: Teacher Studio Full Implementation Overview

**PRs**: `#10`, `#11`, `#12`
**Commits**: `072190c`, `634c1fb`, `25382cc`, `92b5e92`
**Date**: `2026-03-28`
**Status**: functional on `main`

---

## What Teacher Studio Is

Teacher Studio is the teacher-facing lesson creation workflow. It replaces the old one-shot form flow with a staged experience:

1. **Intent capture** - structured topic, audience, signals, preferences, and constraints
2. **Live planning** - deterministic planning with streamed progress over SSE
3. **Review gate** - teacher-visible spec review, editing, and template swap before commit
4. **In-studio generation** - live section-by-section generation inside the studio workspace

The canonical route is `/studio`.

---

## Backend: Planning Package

**Location**: `backend/src/planning/`

| Module | Purpose |
| --- | --- |
| `models.py` | Planning request, contract, section, visual-policy, and spec models |
| `normalizer.py` | Default resolution and brief normalization |
| `template_scorer.py` | Deterministic template selection with metadata fallback |
| `section_composer.py` | Section-role, component, and budget composition |
| `visual_router.py` | Visual intent and mode selection |
| `prompt_builder.py` | Single LLM refinement pass for titles and rationale |
| `fallback.py` | Valid fallback spec assembly when refinement fails |
| `service.py` | End-to-end orchestration and event emission |

### Planning flow

```text
StudioBriefRequest
  -> normalize_brief()
  -> choose_template()
  -> compose_sections()
  -> route_visuals()
  -> refine_plan_text()
  -> PlanningGenerationSpec
```

Steps one through four are deterministic. The refinement step is the only LLM call. When refinement fails, fallback logic still returns a reviewable `PlanningGenerationSpec`.

### Streamed planning events

| Event | Purpose |
| --- | --- |
| `template_selected` | Announces the chosen template and rationale |
| `section_planned` | Streams each section plan as it arrives |
| `plan_complete` | Returns the final spec after refinement |
| `plan_error` | Returns fallback state and a warning when refinement fails |

---

## Backend: Public Routes

**Location**: `backend/src/planning/routes.py`

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/v1/brief` | `POST` | Deprecated compatibility endpoint |
| `/api/v1/brief/stream` | `POST` | Streamed planning endpoint |
| `/api/v1/brief/commit` | `POST` | Approval and generation start boundary |
| `/api/v1/contracts` | `GET` | Live template catalog for the studio |

### Generation bridge

**Location**: `backend/src/generation/routes.py`

The bridge converts `PlanningGenerationSpec` into pipeline generation requests, carries section focus and ordering forward, and builds the context string used by the pipeline.

---

## Frontend: Studio Components

**Location**: `frontend/src/lib/components/studio/`

| Component | Purpose |
| --- | --- |
| `TeacherStudioFlow.svelte` | Top-level stage orchestration and streamed planning handling |
| `IntentForm.svelte` | Teacher brief capture |
| `PlanStream.svelte` | Live planning progress and streamed section arrival |
| `PlanReview.svelte` | Editable review gate with template swap |
| `GenerationView.svelte` | In-studio live generation workspace |

### State and supporting modules

- `frontend/src/lib/stores/studio.ts`
- `frontend/src/lib/api/brief.ts`
- `frontend/src/lib/types/studio.ts`
- `frontend/src/lib/studio/template-swap.ts`
- `frontend/src/lib/studio/presentation.ts`
- `frontend/src/lib/generation/preview.ts`

---

## Route Structure

| Route | Purpose |
| --- | --- |
| `/studio` | Canonical teacher lesson-creation flow |
| `/dashboard` | Teacher landing page that now routes into `/studio` |
| `/textbook/[id]` | Standalone lesson viewer |

---

## Contract Model Notes

Planning relies on the Lectio-generated contract catalog and uses richer contract fields such as:

- `signal_affinity`
- `section_role_defaults`
- `component_budget`
- `max_per_section`
- `available_components`
- `required_components`

When contracts are sparse, the scorer falls back to metadata-based matching instead of failing closed.

---

## End-To-End Flow

1. Teacher opens `/studio`
2. Frontend loads `/api/v1/contracts`
3. Teacher submits the structured brief
4. Frontend streams planning from `/api/v1/brief/stream`
5. Backend emits `template_selected`, `section_planned`, and either `plan_complete` or `plan_error`
6. Teacher reviews and optionally edits or swaps template
7. Frontend commits the approved spec to `/api/v1/brief/commit`
8. Backend validates, persists, and starts generation
9. Frontend shows in-studio generation until completion

---

## Deferred Items

These are not blockers for the shipped rollout, but they remain optional future work:

- Component-level review editing and reordering
- Section retry and enhancement controls inside generation view
- Saved draft briefs across sessions
- Multi-lesson management inside the studio
- Native pipeline consumption of `PlanningGenerationSpec` without the bridge
- Visual asset generation from `visual_policy`
- Broader `signal_affinity` coverage across every template
- Deeper use of `prior_knowledge` inside downstream pipeline prompts
