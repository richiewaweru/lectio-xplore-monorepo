# Staged teaching planner

Status: planned. Nothing built yet. Branch `feat/staged-teaching-planner`, off `main` at 858c2165.

## Why

The teaching planner (`run_lesson_approach_planner`,
`backend/src/application/unit_lesson/teaching_planner.py`) is one LLM call that writes the
whole `TeachingPlanDraftV2`: title, arc, start and target states, anchor usage, misconception
focus, every section's continuity fields, and every block's brief, learner action, task mode,
sources and figure spec. A second LLM call (`review_teaching_plan_draft`) then reviews the
whole plan. It takes about 8 minutes, the longest wait in preparation.

Problems:

- **One mistake costs everything.** Any error (one invalid figure spec, one learner-action
  mismatch) regenerates the whole plan. There are only 2 attempts, so a second unrelated slip
  fails the run.
- **Nothing to show.** The teacher waits about 8 minutes with nothing on screen.

The main goal is that one failure can no longer sink the run. Speed and streaming come second.

## What changes and what doesn't

Only the teaching-plan stage changes.

```
1. Structural planner        unchanged
2. Item generation           unchanged
   Backbone                  unchanged (input to the new planner)
3. Teaching planner          REPLACED (behind a flag) by:
     3a spine call
     3b section calls, in parallel
     3c per-section review + one whole-lesson check
     3d assembly into TeachingPlanDraftV2 -> materialize_teaching_plan
4. Approval, section writers, continuity/boundary checks, media   unchanged
```

The output is the same `TeachingPlan` model as today, built by the same
`materialize_teaching_plan`. Approval, the content hash, `continuity.py`, the composer, the
writers and media can't tell which planner built it.

## Flag

`teaching_planner_mode: Literal["single", "staged"] = "single"` in
`backend/src/infra/config.py`, next to `teaching_plan_quality_gate`. The teaching-plan work
item picks `run_lesson_approach_planner` (single) or the new `run_staged_teaching_planner`
(staged). That's the only switch. Both must return the same `TeachingPlanResult`.

Exit plan: compare on fixture lessons, switch the default to `staged`, then delete the single
path and its now-unused repair helpers in one PR once it has run cleanly for an agreed period.

## 3a. Spine call

One small call that decides the lesson-wide structure.

**Input:** `packet.planner_payload()` (lesson, scope, anchor, misconceptions,
prior_established, slots, required_assessment_slots, approved item ids, limits, backbone,
item_backbone_refs), approved item stems, `slot_intent_policy`, `assessment_source_policy`,
teaching guidance (same projections the single planner builds today).

**Output (`TeachingSpineDraft`, new):**

- lesson level: `learner_title`, `arc`, `starting_state`, `target_state`, `anchor_usage`,
  `misconception_focus_ids`
- per section, in slot order: `display_title`, `specific_purpose`, `transition`,
  `entry_state`, `must_establish`, `avoid_repeating`, `bridge_from_previous`, `exit_state`
- per section assignments:
  - `misconception_ids`: which misconceptions this section confronts
  - `approved_item_ids`: which approved items this section binds
  - `figure_plan`: a short list of figures the section owns, each with a `purpose`, plus a
    `backbone_figure_id` when it reuses a backbone figure (see Visuals)

**Code checks on the spine (no LLM):**

- section count and order equal `packet.slots`
- `entry_state[n]` covered by `exit_state[n-1]` (reuse the coverage helper in `continuity.py`)
- every required approved item is placed exactly once, only in `required_assessment_slots`
  when that list is non-empty
- every `misconception_focus_ids` entry is assigned to at least one section
- `backbone_figure_id` values exist in `packet.backbone.figures`

**Backbone variants come from code, not the model:** once items are placed, a section's
variant follows from `item_backbone_refs` for its assigned items. A section with no item uses
the anchor.

**Retry:** only the spine, up to 3 attempts, with the errors attached, like today's repair
payload.

## 3b. Section calls (parallel)

One call per section, all run together with `asyncio.gather`, inside the existing
`teaching_plan` work item for now.

**Input:** the spine (whole, read-only), this section's slot, its `slot_intent_policy`
entry, its assigned approved items (ids + stems + allowed_actions from
`assessment_source_policy`), its misconceptions, its backbone target(s) and figures, and the
`reserved_assessment_scenarios`.

**Output:** that section's `blocks` (`TeachingPlanDraftBlock` list, unchanged schema),
including `visual` where the spine's `figure_plan` says so.

**Checks:** the existing block-level validators, run on this section only:
`VISUAL_SPEC_INVALID`, learner-action/source compatibility, task-mode/source contract,
unknown learner actions, object leaks, brief length, evidence refs. The deterministic
repairs (`_repair_sources_outside_structural_slots`, `_repair_incompatible_assessment_sources`,
`_repair_invalid_evidence_refs`, `_repair_briefs_missing_anchor_grounding`) also apply per
section.

**Retry:** only the failing section, up to 3 attempts. If it still fails, policy is
**flag, don't fail**: the section ships with a `plan_quality_flag` for the teacher to fix
before approval. (Configurable later; matches the advisory gates.)

## 3c. Review

- **Per section, in parallel:** the existing semantic reviewer prompt, scoped to one section
  plus the spine. Section-local codes (`task_evidence_gap`, `assessment_item_reused`,
  `misconception_unresolved`, accuracy) route back to that section's call.
- **One whole-lesson check:** cross-section repetition, coverage of `target_state`, adjacent
  handoffs, and `visual_missing_for_figure_objective` (lesson-level, advisory). Findings name
  sections, so fixes go to those sections' calls, not a full rerun.

## 3d. Assembly

Build a `TeachingPlanDraftV2` from spine + section blocks, then call
`materialize_teaching_plan`. Then run the existing whole-plan `validate_teaching_plan` and
`advisory_teaching_qc` as a final safety net. Ownership/assessment checks
(`_missing_assessment_sources` etc.) run here too; with the spine assigning items they should
already pass.

## Visuals

This is how figures work today. The staged planner must keep all of it intact.

1. **The plan decides.** `TeachingPlanBlock.visual: VisualSpec | None` is the only source of
   "this block has a figure" (`curriculum/teaching_plan/models.py`). Fields: `mode`
   (`diagram`|`image`), `purpose`, `must_show`, `labels_required`, `must_not_show`, `required`.
2. **The plan is checked.** `_visual_spec_problems` (`print/generation/whole_lesson/validation.py`)
   needs a purpose and at least one `must_show` entry. Every `labels_required` entry must appear
   inside `must_show`, the lesson objective or the packet's `scope.must_establish`. Failures
   raise `VISUAL_SPEC_INVALID`.
3. **The composer places it.** `composer.py` adds a figure node right after the block's own
   nodes, with id `shared-figure-node` hashed from `(section_slot_id, block.id)`.
4. **Media reads the plan spec.** `media.py::_plan_figure_spec` looks the block up by
   `node.teaching_block_id` and treats its `VisualSpec` as authoritative. The writer's caption
   and the sentences that refer to the figure are added as context only. The render path
   (`docs/render-figures.md`) picks a family from that spec; otherwise the image path runs.
   An unavailable figure ships flagged.
5. **Labels are checked against the text.** `figure_consistency.py` checks `labels_required`
   against the written section.

What the staged planner must guarantee:

- **Block ids stay the same.** Ids are `{slot_id}-b{position+1}`, assigned by
  `materialize_teaching_plan`. Always assemble through it; never assign ids in section calls.
  Figure node ids and media work orders depend on it.
- **`visual` stays per block, same schema.** Section calls emit `VisualSpec` on blocks exactly
  as today. No new fields are required.
- **`VISUAL_SPEC_INVALID` stays a section-local check** and only retries that section. The
  label grounding uses lesson-level text (objective, `scope.must_establish`), so a section call
  needs those in its input.
- **Backbone figures become the default source** (an improvement, not just parity). On `main`
  the backbone has `figures` (`id`, `purpose`, `must_show`, `labels_required`, `data`), but no
  code links them to plan `VisualSpec`s; the prompt only tells the planner to "build around the
  anchor and its figures". With the spine assigning `backbone_figure_id` per figure, the section
  call copies that figure's `purpose` / `must_show` / `labels_required` into the block's
  `VisualSpec`, so the same figure looks the same in every section. A code check confirms the
  copy matches. Figures with no backbone link are written freely, as today.
- **`visual_missing_for_figure_objective`** moves to the whole-lesson check (it is lesson-level
  and advisory today).

### Coordination: `feat/backbone-figures-reuse`

Another session has this branch in progress (uncommitted as of 2026-10-06, worktree
`C:/Projects/lectio-wt-figures`). It adds `BackboneFigure.mode` (`diagram`|`image`, `None`
means diagram), rewrites `BACKBONE_TEACHING_GUIDANCE` in `prompt_render.py`, and edits the
semantic reviewer prompt about reusing the anchor versus approved items.

- Reuse `BACKBONE_TEACHING_GUIDANCE` by import in the spine and section prompts; don't copy
  the text.
- Reuse the semantic reviewer prompt; scope it with a section wrapper rather than forking it.
- When copying a backbone figure into a `VisualSpec`, map `effective_mode` to `VisualSpec.mode`
  once that branch lands.
- Rebase onto `main` after it merges, before phase 3.

## Phases

| # | What | Touches existing code |
|---|---|---|
| 0 | Baseline: timings and attempt counts from recent preparation runs (planner vs reviewer vs retry). Pick 5-8 fixture lessons across subjects and lesson shapes. | No |
| 1 | Finalize this spec: `TeachingSpineDraft` schema, section-call I/O, prompt outlines. | No |
| 2 | Split the validators by scope: section-local vs lesson-wide, with no behaviour change. The single planner keeps calling the same combined function. | Yes, refactor only, existing tests must pass |
| 3 | Spine: schema, prompt (`resources/prompts/teaching-spine.md` + manifest), code checks, variant derivation, retry. | No |
| 4 | Section calls: prompt (`teaching-section.md`), run in parallel, per-section validation + deterministic repairs + retry + flag fallback. | No |
| 5 | Assembly + final gate via `materialize_teaching_plan` + `validate_teaching_plan`. | No |
| 6 | Review split: per-section review + whole-lesson check + routing fixes to a section. | No |
| 7 | Compare `single` vs `staged` on the fixtures: wall-clock, attempts, flags, plan quality side by side, and that figure specs reach media with matching ids. | No |
| 8 | Streaming: `teaching_spine` and `teaching_section:{slot}` work items with progress; plan page shows the spine first, then sections as they land, marked "draft" until the whole-lesson check passes. | Runtime + frontend |
| 9 | Flip default; delete the single path after the agreed period. | Yes, deletion |

Phases 3-6 run inside the existing `teaching_plan` work item (parallelism via
`asyncio.gather`), so the runtime and UI don't change until phase 8.

## Tests

- Unit: spine code checks (state chaining, item placement, misconception coverage, figure
  ids); variant derivation from `item_backbone_refs`; assembly gives the same block ids as
  `materialize_teaching_plan`.
- Unit: one failing section retries alone; others are not re-called (count calls on a fake
  model).
- Unit: section that exhausts retries ships flagged, plan still materializes.
- Integration: staged plan through composer -> figure nodes -> `_plan_figure_spec` resolves
  every `visual` block.
- Existing planner tests stay green with `teaching_planner_mode="single"`.

## Open questions

- Retry budget per piece (3 proposed) and overall wall-clock cap.
- Whether item placement is fully code-assigned (deterministic) or spine-proposed and
  code-checked. Start with spine-proposed + checks; switch if the spine misplaces items.
- Does the plan page already subscribe to per-work-item progress (affects phase 8 size)?
