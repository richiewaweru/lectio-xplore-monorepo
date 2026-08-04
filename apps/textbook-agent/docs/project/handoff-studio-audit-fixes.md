# Handoff: Teacher Studio + Planning Layer Audit Fixes

**PR**: [#12](https://github.com/richiewaweru/text-book-generator/pull/12)
**Commit**: `92b5e92` - `fix(studio): harden planning layer and teacher studio integration`
**Date**: `2026-03-28`
**Status**: merged to `main`

---

## Context

Teacher Studio landed across three PRs:

| PR | Commit(s) | Scope |
| --- | --- | --- |
| `#10` | `072190c` | Initial teacher studio planning flow |
| `#11` | `634c1fb`, `25382cc` | Full planning backend and frontend rollout |
| `#12` | `92b5e92` | Audit fixes and hardening |

This follow-up handoff covers the bugs fixed after a deeper audit against the studio and planning proposals plus the implemented UI states.

---

## What Was Fixed

### High severity

#### 1. `VisualPolicy` accepted invalid required state
- **File**: `backend/src/planning/models.py`
- **Bug**: `required=True` could coexist with missing `mode` or `intent`
- **Fix**: Added a model validator that rejects required visual policies unless both `mode` and `intent` are present

#### 2. `/api/v1/brief/commit` was missing template and preset validation
- **File**: `backend/src/planning/routes.py`
- **Bug**: Invalid template and preset combinations could reach generation and fail too late
- **Fix**: Added explicit validation before enqueueing generation so the route returns `422` with a clear error

### Medium severity

#### 3. Generation bridge focus text could collapse to empty
- **File**: `backend/src/generation/routes.py`
- **Bug**: The bridge could theoretically emit an empty focus string when optional fields were blank
- **Fix**: Added a final fallback of `Section {order}`

#### 4. Planning progress never reached `100%`
- **File**: `frontend/src/lib/components/studio/PlanStream.svelte`
- **Bug**: The progress bar capped below completion even after `plan_complete`
- **Fix**: Completion now forces the progress bar to `100%`

#### 5. Unknown planning SSE events were treated as hard errors
- **File**: `frontend/src/lib/components/studio/TeacherStudioFlow.svelte`
- **Bug**: Any future event shape could be cast as `plan_error`
- **Fix**: Error handling now only runs for the explicit `plan_error` event type, preserving forward compatibility

#### 6. Prior-knowledge collapse state used a non-reactive initializer
- **File**: `frontend/src/lib/components/studio/IntentForm.svelte`
- **Bug**: The initial collapse state used a snapshot instead of the reactive draft store
- **Fix**: Switched the initializer to use the reactive store-backed value

### Low severity

#### 7. `visual_router.py` return types were too loose
- **File**: `backend/src/planning/visual_router.py`
- **Fix**: Tightened helper return annotations to `PlanningVisualMode` and `PlanningVisualIntent`

#### 8. Refined section titles needed explicit non-empty validation
- **File**: `backend/src/planning/prompt_builder.py`
- **Fix**: Empty titles from the LLM now trigger retry validation

#### 9. Spatial keyword coverage was too narrow
- **File**: `backend/src/planning/visual_router.py`
- **Fix**: Expanded the spatial keyword set to better catch geography, anatomy, weather, engineering, and astronomy-style prompts

#### 10. Store behavior needed an explicit status override note
- **File**: `frontend/src/lib/stores/studio.ts`
- **Fix**: Added a clarifying comment on the intentional `reviewed` status override after planning completes

#### 11. Constraint checkbox wiring was rechecked
- **File**: `frontend/src/lib/components/studio/IntentForm.svelte`
- **Result**: Confirmed the existing checkbox handlers were already wired correctly, so no change was required there

---

## Tests Added Or Updated

| Test | File | Coverage |
| --- | --- | --- |
| `test_visual_policy_rejects_mode_none_when_required` | `backend/tests/planning/test_planning.py` | Rejects invalid required visual state |
| `test_section_count_boundaries` | `backend/tests/planning/test_planning.py` | Keeps section composition within bounds |
| `test_empty_signal_affinity_scoring_uses_metadata` | `backend/tests/planning/test_planning.py` | Confirms metadata fallback scoring |
| `test_section_focus_fallback_in_bridge` | `backend/tests/planning/test_planning.py` | Confirms generation bridge fallback focus |
| `test_commit_brief_starts_generation_with_committed_planning_spec` | `backend/tests/interface/test_brief.py` | Updated for validation-aware commit flow |
| `test_commit_brief_rejects_invalid_template_preset_combination` | `backend/tests/interface/test_brief.py` | Confirms invalid combinations return `422` |

---

## Files Changed In The Hardening Pass

- `backend/src/planning/models.py`
- `backend/src/planning/prompt_builder.py`
- `backend/src/planning/visual_router.py`
- `backend/src/planning/routes.py`
- `backend/src/generation/routes.py`
- `backend/tests/interface/test_brief.py`
- `backend/tests/planning/test_planning.py`
- `frontend/src/lib/components/studio/IntentForm.svelte`
- `frontend/src/lib/components/studio/PlanStream.svelte`
- `frontend/src/lib/components/studio/TeacherStudioFlow.svelte`
- `frontend/src/lib/stores/studio.ts`

---

## Known Non-Blocking Notes

- `backend/contracts/` is generated from the sibling Lectio repo and is intentionally not committed
- Local frontend type-check and validation depend on a supported Node version
- A stale `.claude/worktrees/distracted-haibt` directory may remain on disk if Windows still holds a file handle, but it is no longer a registered git worktree

---

## Architecture Notes

- `backend/src/planning/` remains isolated from `pipeline/`
- The shell imports both planning and pipeline code
- The generation bridge in `routes/generation.py` maps `PlanningGenerationSpec` into pipeline request types
- Richer planning roles are preserved at the bridge boundary instead of forcing planning code to depend on pipeline internals
