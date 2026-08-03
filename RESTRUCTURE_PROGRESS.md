# RESTRUCTURE_PROGRESS

Branch: `xplore`. Started: 2026-08-03. Finished implementation wave: 2026-08-03.

Source of truth: [`handoff/RESTRUCTURE_HANDOFF.md`](handoff/RESTRUCTURE_HANDOFF.md). Unattended instructions: [`CURSOR_GOAL.md`](CURSOR_GOAL.md).

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
- **A2+A3:** expander reasoning `low`; ~80-word `content_intent` cap in prompt + `validate_section_brief`; fixture tests updated.
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
- [x] `validate_section_brief` word cap + fixture test
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
7. Full suites — targeted suites green; full-suite run may need clean SQLite (Windows lock flakiness noted).
8. Wall unchanged — grep evidence recorded above.

## Summary

**Shipped:** Stage2 one-wave + env speed knobs, nominated merge critic, prompt packaging with teacher overlays and settings page, constructor/readback + chat plan edit + teacher-language unit/studio UI.

**Deferred:** Live lesson timing/brief side-by-side (needs API keys); expander→FAST trial (explicitly after low-reasoning quality check).

## BLOCKED

(none)
