# RESTRUCTURE_PROGRESS

Branch: `xplore`. Restructure wave finished: 2026-08-03. **Reshape wave started: 2026-08-03.**

Source of truth: [`handoff/RESHAPE_HANDOFF.md`](handoff/RESHAPE_HANDOFF.md) (**v2 post-decision**; supersedes `LANES_HANDOFF.md` and v1 reshape). Prior wave: [`handoff/RESTRUCTURE_HANDOFF.md`](handoff/RESTRUCTURE_HANDOFF.md). Instructions: [`CURSOR_GOAL.md`](CURSOR_GOAL.md).

## DECISION: expander lives

User recorded decision 2026-08-03 after three rounds (quality equal in round 2; timing non-decisive in round 3). **Keep the expander.** Remove `V3_SKIP_EXPANDER`; lanes are 3-step (`brief → prose → questions`). v1 Phase 1 (expander removal / VisualStrategySpec rehome) is cancelled. Stage 1 stays untouched. Forced order now: skip-flag cleanup → handoff §4 storage → §5 lanes → §9 acceptance. Migration choice remains **backfill** `generation_steps` from `chunked_state_json` when rows absent.

## Reshape baseline

- Docs: `RESHAPE_HANDOFF.md` v2, post-decision `CURSOR_GOAL.md`, `LANES_HANDOFF.md` superseded stub.
- Live API keys present in root `.env`.
- Migration head before reshape: `20260803_0030_add_unit_class_notes`.
- Migration choice (locked): **backfill** `generation_steps` from `chunked_state_json` when rows absent.

## Reshape commits

- `docs: reshape handoff v2 post-decision + expander-lives` — this entry.
- `1.0: remove V3_SKIP_EXPANDER keep expander` — deleted skip flag/branch; STRUCTURED CONSTRAINTS + anchor fields retained on brief writer path; tests 14 passed (`test_stage2_parallel` + `test_shared_prompt_prefix`).
- `docs: reshape handoff + superseded lanes pointer` — v1 baseline (superseded).
- `0.1: V3_SKIP_EXPANDER writer branch` — flag (default false); Stage2 synthesizes briefs from plan purposes when on; writer prompt renders plan+registry structured constraints; `transition_note`/`role`/`card_id` on writer section; tests 15 passed (`test_stage2_parallel` + `test_shared_prompt_prefix`).
- `7.1: teacher corrections as typed Correction list` — `Correction` model; router patch/repair append typed list; writer prompt dedicated section; patch test updated (3 passed).
- `7.2: keep intents and visual constraints structured at seams` — `learning_intents` list on preview DTO; assembler strategy no longer joins must_show; compile_orders stops joining intents; preview_mapper/assembler tests 8 passed.
- `7.3: plain groups-tab teacher copy` — UnitGroupsPanel / ResourceComposerPanel wording.
- `0b.1: fair skip-writer constraints + anchor.example plumbing` — AnchorPlan.example; WriterSection misconceptions/exclusions/anchor fields; STRUCTURED CONSTRAINTS list in skip writer path; tests 10 passed.

## Phase 0C — timing repeat (done)

Measurement-only per [`handoff/PHASE_0C_HANDOFF.md`](handoff/PHASE_0C_HANDOFF.md): 3× with_expander + 3× skip interleaved on `shared_plan.json`; no product/prompt changes. Aggregate: [`experiments/expander/round3/timings.json`](experiments/expander/round3/timings.json).

## AWAITING DECISION: expander (round 3 — timing)

Timing repeat only (quality closed in round 2). Identical plan [`shared_plan.json`](experiments/expander/shared_plan.json); section ids `orient → explain → model → apply → check`. Harness: [`experiments/expander/run_round3.py`](experiments/expander/run_round3.py). No product/prompt diffs. All six runs OK (`affected_runs=[]`).

### Six runs (start times UTC)

| Order | Arm | Run | started_at | Stage2 | Writers | Total |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| 1 | with_expander | 1 | 2026-08-03T15:47:15Z | 28.30s | 162.77s | 191.10s |
| 2 | skip_expander | 1 | 2026-08-03T15:50:26Z | 0.00s | 211.89s | 211.89s |
| 3 | with_expander | 2 | 2026-08-03T15:53:58Z | 32.38s | 207.41s | 239.80s |
| 4 | skip_expander | 2 | 2026-08-03T15:57:58Z | 0.00s | 432.65s | 432.65s |
| 5 | with_expander | 3 | 2026-08-03T16:05:10Z | 13.48s | 167.99s | 181.47s |
| 6 | skip_expander | 3 | 2026-08-03T16:08:12Z | 0.00s | 169.91s | 169.91s |

skip/run2 had a single-section spike: `model` writer **280.93s** (other skip model writers 47.49 / 38.86).

### Per-arm medians and spreads

| Arm | Stage2 median (min–max) | Writers median (min–max) | Total median (min–max) |
| --- | --- | --- | --- |
| with_expander | **28.30s** (13.48–32.38) | **167.99s** (162.77–207.41) | **191.10s** (181.47–239.80) |
| skip_expander | **0.00s** (0–0) | **211.89s** (169.91–432.65) | **211.89s** (169.91–432.65) |

Median-to-median deltas (skip − with): stage2 **−28.30s**; writers **+43.90s**; total **+20.79s**.

### Per-section writer medians (both arms)

| Section | with median (min–max) | skip median (min–max) |
| --- | --- | --- |
| orient | 27.35s (26.09–43.75) | 18.59s (18.33–22.79) |
| explain | 25.17s (14.75–27.80) | 50.21s (27.73–74.36) |
| model | 31.69s (21.86–63.63) | 47.49s (38.86–280.93) |
| apply | 43.68s (33.65–55.29) | 49.36s (40.63–59.85) |
| check | 36.13s (33.34–53.99) | 24.88s (18.41–42.03) |

Skip is not uniformly slower on every section: orient and check medians are faster on skip; explain/model/apply medians are slower.

### Factual mapping to §4 (no dies/lives recommendation)

- Total median delta is **+20.79s** (skip slower) — slightly above the ~15s “within noise” band, **not** “skip median faster.”
- That +20.79s is **smaller than each arm’s own total min–max spread** (with ≈58s; skip ≈263s, dominated by skip/run2). So the numbers do **not** meet the §4 bar for (b) (“slower by a margin larger than each arm’s own spread”).
- Closest factual read: **(a) noise** — timing remains non-decisive; decision rests on the architectural case (and round-2 quality already closed).
- Report-only note (lanes): expander stage-2 cost parallelizes per lane; a slower writer call sits on every lane’s critical path. Do not treat raw sequential totals as the final architecture wall.

**Decision recorded:** expander lives (see `## DECISION: expander lives`). Timing remains non-decisive; no deletion/retention recommendation from timing alone.

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

**Decision recorded:** expander lives — remove `V3_SKIP_EXPANDER`; lanes 3-step; v1 Phase 1 cancelled. Phase 4 (§7.1–7.3) already landed while awaiting.

## AWAITING DECISION: expander (round 2)

Fair retest per [`handoff/PHASE_0B_HANDOFF.md`](handoff/PHASE_0B_HANDOFF.md). Artifacts: `with_expander/` (r1), `with_expander_v2/`, `skip_expander_v2/`, [`factual_compare_v2.json`](experiments/expander/factual_compare_v2.json), [`summary_v2.json`](experiments/expander/summary_v2.json). Identical plan: [`shared_plan.json`](experiments/expander/shared_plan.json).

**What changed vs round 1:** skip writer now receives structured ANCHOR / MISCONCEPTIONS / EXCLUSIONS / ROLE / TRANSITION / purpose+registry bullets; `anchor.example` plumbed through blueprint → work order (was previously dropped).

### Three-arm table

| Arm | Anchor hits | apply M1 (soil) | apply M2 (breath/opposite) | Stage2 | Writers | Total |
| --- | ---: | --- | --- | ---: | ---: | ---: |
| with_expander (r1) | **5 / 5** | yes | no | 27.23s | 177.48s | 204.71s |
| with_expander_v2 | **5 / 5** | yes | no | 27.43s | 131.48s | 158.91s |
| skip_expander_v2 | **5 / 5** | yes | no | 0.00s | 207.59s | 207.59s |

Round-1 skip (for contrast, not in v2 table): anchor **2 / 5**, apply M1 **no**.

Role order preserved on all three arms; `failed_briefs=[]`. Exclusions declared on plan: **none** (`repair_focus` null) — no exclusion-violation checks apply.

### Factual reading of §1 explanations

- **Primary signal (anchor):** skip_expander_v2 reaches **5 / 5**, matching both expander arms. Round-1 skip shortfall (2 / 5) is consistent with explanation **(b)** — the writer was not asked — not with irreversible consolidation by the expander.
- **Secondary signal (apply misconception):** skip_expander_v2 apply mentions soil (M1), matching expander arms. Round-1 skip apply lacked M1.
- Timings are not decisive (handoff §1): Stage2 expander cost ~27s; writer times vary across runs (skip writers were slower this round).

**Factual recommendation from §4 rule:** numbers support explanation **(b)** → expander as middleman; handoff says **it dies**. Prose quality remains the user's read (`skip_expander_v2/prose.json` vs `with_expander_v2/prose.json`).

**Decision recorded:** expander lives (see `## DECISION: expander lives`). Round-2 quality equality stands; dies recommendation from §4 rule was superseded by the user's keep decision.

## KNOWN DEFECTS

- **Stage 1 emits non-skeleton role `build`.** Round-1 live Stage 1 failed validation: section role `build` is not in `skeletons.yaml` slot ids (`apply`, `check`, `close`, `confront`, `contrast`, `criteria`, `explain`, `guided`, `independent`, `model`, `organise`, `orient`, `recall`). That forced substitution of the fixed plan in [`experiments/expander/shared_plan.json`](experiments/expander/shared_plan.json). This is the failure class reshape §8.1 (derive role sequence from `skeletons.yaml` by lookup) makes structurally impossible. **Not fixed in Phase 0B** — touches stage 1 schema; belongs with §8.1.

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
