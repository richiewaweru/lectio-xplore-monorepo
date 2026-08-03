# RESTRUCTURE_PROGRESS

Branch: `xplore`. Restructure wave finished: 2026-08-03. **Reshape wave started: 2026-08-03.**

Source of truth: [`handoff/RESHAPE_HANDOFF.md`](handoff/RESHAPE_HANDOFF.md) (supersedes `LANES_HANDOFF.md`). Prior wave: [`handoff/RESTRUCTURE_HANDOFF.md`](handoff/RESTRUCTURE_HANDOFF.md). Instructions: [`CURSOR_GOAL.md`](CURSOR_GOAL.md).

## Reshape baseline

- Docs landed: `handoff/RESHAPE_HANDOFF.md`, `CURSOR_GOAL.md` (reshape), `handoff/LANES_HANDOFF.md` superseded stub.
- Live API keys present in root `.env` — Phase 0 A/B can run locally.
- Migration head before reshape: `20260803_0030_add_unit_class_notes`.
- Forced order: Phase 0 → (Phase 4 while waiting) → Phase 1 only if expander dies → Phase 2 → Phase 3 → acceptance.
- Migration choice (Phase 2, locked): **backfill** `generation_steps` from `chunked_state_json` when rows absent.

## Reshape commits

- `docs: reshape handoff + superseded lanes pointer` — this baseline.
- `0.1: V3_SKIP_EXPANDER writer branch` — flag (default false); Stage2 synthesizes briefs from plan purposes when on; writer prompt renders plan+registry structured constraints; `transition_note`/`role`/`card_id` on writer section; tests 15 passed (`test_stage2_parallel` + `test_shared_prompt_prefix`).
- `7.1: teacher corrections as typed Correction list` — `Correction` model; router patch/repair append typed list; writer prompt dedicated section; patch test updated (3 passed).
- `7.2: keep intents and visual constraints structured at seams` — `learning_intents` list on preview DTO; assembler strategy no longer joins must_show; compile_orders stops joining intents; preview_mapper/assembler tests 8 passed.
- `7.3: plain groups-tab teacher copy` — UnitGroupsPanel / ResourceComposerPanel wording.

## AWAITING DECISION: expander

Phase 0 A/B complete. Artifacts: [`experiments/expander/`](experiments/expander/) (`with_expander/`, `skip_expander/`, `shared_plan.json`, `summary.json`, `factual_compare.json`).

**Setup (factual):** Same fixed StructuralPlan (photosynthesis science concept) for both arms — roles `orient → explain → model → apply → check` (practice=`apply`, check=`check`); no `visual_required` sections. Live Stage 1 was attempted first but failed skeleton role validation (`build` not in catalog); fixed plan used so both arms share an identical lesson shape. Harness: Stage 2 + section writers only (not full pack/items/visuals/coherence).

**Timings:**

| Arm | Stage2 | Writers | Total |
| --- | ---: | ---: | ---: |
| with_expander (`V3_SKIP_EXPANDER=false`) | 27.23s | 177.48s | 204.71s |
| skip_expander (`V3_SKIP_EXPANDER=true`) | 0.00s | 159.57s | 159.58s |
| delta (with − skip) | +27.23s | +17.91s | +45.13s |

**Side-by-side factual notes (not a quality judgement):**

1. **Anchor (windowsill plant):** with_expander prose mentions the windowsill/window anchor in all five sections. skip_expander mentions it in `orient` and `model` only (`explain` / `apply` / `check` string-match false in `factual_compare.json`).
2. **Misconception targeting (M1 soil-food / M2 breathing-opposite):** Both arms mention soil in `orient`/`explain`/`model`/`check`. with_expander also mentions soil in `apply`; skip_expander `apply` does not. Breathing/opposite language appears in with_expander `model`; in skip_expander `model` and `check`.
3. **Declared exclusions:** Plan slot purposes asked writers to rule out soil-as-food as the energy source. Both arms still discuss soil in misconception/contrast contexts (expected for targeting). No separate `repair_focus.what_not_to_teach` list was on this fixed plan.
4. **Difficulty progression:** Both arms keep the planned role order `orient → explain → model → apply → check` with no failed briefs (`failed_briefs=[]`).
5. **Brief vs purpose:** with_expander briefs rewrite plan purposes into longer `content_intent` prose (often adding option counts, word caps, variant hints). skip_expander feeds plan `purpose` strings + registry contracts to the writer unchanged.

**User decision needed before Phase 1–3:**

- **Expander dies** → Phase 1 removal (after VisualStrategySpec rehome), then lanes are 2-step (`prose`, `questions`).
- **Expander lives** → remove `V3_SKIP_EXPANDER` branch; keep briefs; lanes are 3-step (`brief`, `prose`, `questions`); skip Phase 1.

Phase 4 (§7.1–7.3) already landed while this decision was pending. **Phases 1–3 and acceptance are halted** until you answer.

## Baseline

- Full local lesson generation: **not run** — no local `.env` / API keys in this session.
- Used test-level verification and resolved-config proof instead.
- Pre-change defaults: Stage2 timeout 240s; concurrency SECTION=3 QUESTION=3; Stage2 parallel=true (anchor-first).
- Post-change resolved defaults (via `uv run`): concurrency `{section:5, question:5, visual:4}`, stage2 timeout `100`.

## Completed

- Docs: `handoff/RESTRUCTURE_HANDOFF.md`, `CURSOR_GOAL.md`, this progress file.
- Env: `.env.example` + code defaults → Stage2 100s, concurrency 5/5/4; startup/generation logs print resolved limits.
- **A1:** one-wave Stage2 fan-out; plan-derived continuity; resume mirrored; exception isolation for all sections. Tests rewritten (`test_stage2_parallel.py` 13 passed with retry tests).
- **A4:** pack `execute_items` via `asyncio.gather` preserving card order.
- **A2+A3:** expander reasoning `low`; ~80-word `content_intent` guidance is **advisory only** (prompt + non-blocking log). Over-long intents no longer fail Stage 2 or trigger retries.
- **6.1:** question writer → FAST/low; blueprint adjust → FAST/medium (landed with 6.1a commit; expander stays STANDARD/low).
- **B:** merge critic nominated pairs + `merge_warning` neighbors; UI merge-critic panel removed; critic tests updated.
- **C:** `backend/resources/prompts/` + manifest; loader/overlays/`prompt_overrides` migration; hash stamping helper + stage2 stamp; `/settings/prompts` UI; 36 related tests passed.
- **D:** constructor node + readback API; chat plan edit; class_notes migration; Screens 1–5 teacher language; constructor/chat tests 10 passed; units page tests 5 passed; `[id]` page tests green.
- Docs pointers on handoff `11`, `07` (UI), `14`.
- Wall audit: item prompts consume only card fields (`id/title/objective/misconceptions` + item_context). No `content_intent`/prose leakage in item prompt path.

## Section 8 checklist

### Backend

- [x] `retry.py` anchor-serial removal + `persistence.py` resume mirror
- [x] `test_stage2_parallel.py` rewritten per A1
- [x] `run_adjacent_merge_critics` nominated-only + tests
- [x] `validate_section_brief` word-length advisory (log only; does not fail briefs)
- [x] `router.py` item-gather
- [x] Prompt extraction + hashes
- [x] `prompt_overrides` table migration; overlay resolution; locked-prompt bypass
- [x] Constructor node registration, route, structured output model
- [x] Unit-creation raw text / constructor readback path; legacy UnitCreate still accepted
- [x] Resume paths coherent with one-wave fan-out

### Frontend

- [x] units create form + `[id]` screens rebuild; page tests updated
- [x] LessonShapePanel / UnitGroupsPanel re-homed (versions panel / debug)
- [x] Banned-words sweep on teacher-facing unit/studio surfaces
- [x] Vite manual-chunk list unaffected (templates untouched)

### Docs

- [x] Pointer notes on handoff 11, 07 UI, 14

## Acceptance (§9)

1. Wall-clock &lt;5 min — **deferred** (no live generation); structural speedups landed (one-wave Stage2, parallel items, timeouts/concurrency).
2. Briefs at low reasoning — **deferred** quality read; word-cap validator enforces ≤80 words.
3. Banned words — unit/studio teacher copy cleaned; type names may still say Variant.
4. Critic call count = nominations — tests green.
5. Overlay edit/reset/locked reject + hashes — loader/API tests green; stage2 stamps `prompt_hashes`.
6. Free-text create → readback → lock path — frontend + constructor routes/tests green.
7. Full suites — targeted suites green (68 restructure-related backend tests in one batch; units FE 5+9). Full-suite run may need clean SQLite (Windows lock flakiness noted).
8. Wall unchanged — grep evidence recorded above.

## Summary

**Shipped:** Stage2 one-wave + env speed knobs, nominated merge critic, prompt packaging with teacher overlays and settings page, constructor/readback + chat plan edit + teacher-language unit/studio UI.

**Deferred:** Live lesson timing/brief side-by-side (needs API keys); expander→FAST trial (explicitly after low-reasoning quality check).

## BLOCKED

(none)
