# Handoff: Strengthened Composition System

**Date:** 2026-04-01
**Branch:** `claude/optimistic-poitras`
**Commit:** `33c889e`
**Status:** ✅ Complete, all 192 tests passing

## What Was Built

A **4-phase enhancement** to the pipeline's composition and diagram generation system, enabling:

1. **LLM-powered composition decisions** (replacing hard-coded heuristics)
2. **Multiple interactions per section** (0-N instead of 0-1)
3. **Image generation support** (Gemini Imagen + DiagramSpec fallback)
4. **Pedagogical tracking** (interaction diversity, fallback context)

All changes are **backward-compatible** with existing templates and integrations.

---

## Implementation Overview

### Phase 1: Schema & State Changes

**Files Modified:**
- `backend/src/pipeline/types/composition.py`
- `backend/src/pipeline/types/section_content.py`
- `backend/src/pipeline/state.py`

**Key Additions:**
- `CompositionPlan`: Added `interactions: list[InteractionPlan]` (synced with singular `interaction` via `model_validator`)
- `InteractionPlan`: Added `manipulable_element`, `response_element`, `pedagogical_payoff`, `complexity`, `estimated_time_minutes`
- `DiagramPlan`: Added `fallback_from_interaction`, `interaction_intent`, `interaction_elements`
- `DiagramContent`: Added `image_url: str | None` (populated when image generation succeeds)
- `SectionContent`: Added `simulations: list[SimulationContent]` (singular `simulation` retained for backward compat)
- `TextbookPipelineState`: Added `interaction_usage: dict[str, int]` (tracks type counts per section for diversity)

**Migration Pattern:**
```python
# Old code still works:
composition.interaction.enabled  # → InteractionPlan object
section.simulation               # → SimulationContent | None

# New code also works:
composition.interactions         # → list[InteractionPlan]
section.simulations             # → list[SimulationContent]
```

---

### Phase 2: Composition Planner (LLM-Powered Decisions)

**Files Created:**
- `backend/src/pipeline/catalogs/interaction_catalog.py` — Pedagogical guidance for 6 interaction types
- `backend/src/pipeline/prompts/composition.py` — System + user prompts for LLM reasoning

**Files Modified:**
- `backend/src/pipeline/nodes/composition_planner.py` — Complete rewrite
- `backend/src/pipeline/providers/registry.py` — Added `composition_planner: FAST`

**How It Works:**

1. **Guard-Rails First** (hard constraints):
   - Check `diagram_policy` and `interaction_policy` from section plan
   - Check template slots: `diagram-block` and `simulation-block`
   - If both disabled → skip LLM, return quick result

2. **LLM Reasoning** (if constraints allow):
   - Build system prompt: includes interaction catalog + style context
   - Build user prompt: section content + interaction usage stats
   - Call pydantic-ai Agent with `CompositionDecision` output schema
   - 15-second timeout

3. **Fallback on Failure**:
   - Any LLM error → revert to existing heuristic logic
   - Heuristic preserved entirely for compatibility

4. **Diversity Tracking**:
   - Update `interaction_usage` dict with enabled interaction types
   - Pass usage stats to LLM for "prefer variety" hints

**Example Output:**
```json
{
  "diagram": {
    "enabled": true,
    "diagram_type": "concept_map",
    "key_concepts": ["derivative", "rate of change"],
    "fallback_from_interaction": false,
    "interaction_intent": null
  },
  "interactions": [
    {
      "enabled": true,
      "interaction_type": "graph_slider",
      "manipulable_element": "slope m",
      "response_element": "line steepness",
      "pedagogical_payoff": "see slope effect in real-time",
      "complexity": "simple"
    }
  ],
  "reasoning": "LLM explanation of choices",
  "confidence": "high"
}
```

**Testing:**
- 8 existing heuristic tests pass via fallback
- 6 new tests for LLM path (mocked with TestModel)
- Covers: LLM success, fallback on error, guard-rail overrides, usage tracking

---

### Phase 3A: Diagram Generator (Dual-Path: Image + Spec)

**Files Created:**
- `backend/src/pipeline/providers/gemini_image_client.py` — Gemini Imagen client
- `backend/src/pipeline/storage/image_store.py` — Local + GCS storage
- `backend/src/pipeline/prompts/diagram.py` (additions) — Image generation prompt

**Files Modified:**
- `backend/src/pipeline/nodes/diagram_generator.py` — Complete refactor
- `backend/src/pipeline/providers/registry.py` — Added `get_image_client()`

**Architecture:**

```
diagram_generator
├─ Check: image client available?
├─ Check: should_use_image_generation() → true for visual templates + science
│
├─ IMAGE PATH (if available + routing says image):
│  ├─ Build natural-language prompt (composition-aware, with style keywords)
│  ├─ Call GeminiImageClient.generate_image()
│  ├─ Store via ImageStore (local or GCS based on ENVIRONMENT)
│  ├─ Generate caption/alt-text via quick LLM call
│  └─ DiagramContent(image_url=..., caption=..., alt_text=...)
│
└─ FALLBACK/SPEC PATH (if image unavailable or fails):
   ├─ Build JSON spec prompt
   ├─ Call Claude LLM for DiagramSpec structure
   └─ DiagramContent(spec=..., caption=..., alt_text=...)
```

**Routing Logic:**

Uses `should_use_image_generation()` to decide:
- **Image path**: visual-first templates, science subjects (biology, chemistry, earth-science, geography)
- **Spec path**: process flows, math geometry topics, or when image client not configured

**Environment Variables:**

```bash
# Image generation (optional)
IMAGE_PROVIDER=gemini
GOOGLE_API_KEY=<api-key>

# Storage
ENVIRONMENT=development  # or production
IMAGE_BASE_URL=http://localhost:8000/images  # dev only
GCS_BUCKET_NAME=textbook-diagrams  # production only
```

**Outcomes Tracked:**
- `image_success` — Image generated and stored
- `spec_success` — Spec generated (primary path)
- `image_fallback_to_spec` — Image failed, fell back to spec
- `timeout` — Generation timed out
- `error` — Other error (recoverable)
- `skipped` — Diagram not needed

**Backward Compatibility:**
- If `GOOGLE_API_KEY` not set: image client returns `None`, always uses spec path
- Existing DiagramSpec format unchanged
- Tests run both paths, all pass

---

### Phase 3B: Interaction Generator (Multi-Interaction Support)

**Files Modified:**
- `backend/src/pipeline/nodes/interaction_generator.py` — Rewritten to loop
- `backend/src/pipeline/nodes/interaction_decider.py` — Deprecated to shim
- `backend/src/pipeline/nodes/process_section.py` — Simplified phase 3

**Key Changes:**

1. **Reads composition.interactions List:**
   ```python
   enabled_plans = [p for p in composition.interactions if p.enabled]
   for plan in enabled_plans:
       spec = _build_interaction_spec(state, section, plan)
       simulations.append(SimulationContent(spec=spec, ...))
   ```

2. **Writes to Both Fields:**
   ```python
   section.simulations = simulations  # New: list
   section.simulation = simulations[0]  # Backward compat: singular
   ```

3. **Spec Building (from decider):**
   - Moved `build_interaction_spec()` to `interaction_generator` as private `_build_interaction_spec`
   - Takes `InteractionPlan` directly
   - Extracts `manipulable_element`, `response_element` from plan
   - Builds `InteractionSpec` dict

4. **Interaction Decider Shim:**
   ```python
   # interaction_decider.py now:
   async def interaction_decider(state, *, model_overrides=None):
       return {"completed_nodes": ["interaction_decider"]}

   # But re-exports for backward compat:
   from interaction_generator import build_interaction_spec
   ```

5. **Process Section Simplification:**
   - Removed `_run_interaction_path()` wrapper
   - Phase 3 is now: `diagram_generator` || `interaction_generator` (direct parallel)
   - No dependency on `interaction_decider` anymore

**Backward Compatibility:**
- Old templates expecting `section.simulation` still work (gets first item from list)
- `interaction_specs` state field still populated (needed for retry path)
- `interaction_decider` still importable (thin no-op shim)

---

## Testing & Validation

### Test Results

```
Backend tests: 192 passing (was 186, +6 new)
- All composition_planner tests pass (8 existing + 6 new)
- All integration tests pass (including process_section flow)
- All diagram_generator tests pass (image + spec paths)
- All interaction_generator tests pass (multi-interaction support)
```

### Verification Run

```python
# Import check (all working):
from pipeline.catalogs.interaction_catalog import INTERACTION_CATALOG  # 6 entries
from pipeline.prompts.composition import build_composition_system_prompt
from pipeline.nodes.composition_planner import composition_planner
from pipeline.providers.gemini_image_client import GeminiImageClient
from pipeline.storage.image_store import get_image_store

# Schema check (all fields present):
"interactions" in CompositionPlan.model_fields  # ✓
"image_url" in DiagramContent.model_fields      # ✓
"simulations" in SectionContent.model_fields    # ✓
"interaction_usage" in TextbookPipelineState.model_fields  # ✓
```

---

## Known Limitations & Drifts

### Deliberate Drifts from Original Proposals

1. **"SVG Fallback" is actually DiagramSpec**
   - Current diagram_generator produces JSON specs, not SVG
   - Image path is NEW; spec path is EXISTING (not SVG)
   - Terminology adjusted accordingly

2. **interaction_decider Kept as Shim**
   - Safer than deleting (retry path in graph.py depends on imports)
   - Thin re-export wrapper ensures backward compat

3. **interaction_specs Field Retained**
   - Needed for `retry_interaction` in graph.py
   - Deprecated but still populated

4. **CompositionPlan.interaction + interactions Synced**
   - `model_validator` bridge ensures both fields stay consistent
   - No breaking change

5. **composition_planner Missing from Registry**
   - Was not in `NODE_MODEL_SLOTS`; added as `FAST` during implementation

6. **Cross-Section Diversity Limited**
   - Fan-out parallelism means sections can't see each other's choices
   - Mitigation: position-based hints in prompts, rely on balance across sections

---

## Integration Checklist

- [x] All imports work
- [x] All 192 tests pass
- [x] Backward compatibility verified
- [x] Commit created with detailed message
- [x] Handoff document written
- [ ] Merge to `main` (next step)

---

## Next Steps for Reviewer

1. **Review the commit:** 33c889e on `claude/optimistic-poitras`
   - 18 files changed, 1285 insertions, 195 deletions
   - New modules: catalogs, composition prompts, gemini client, image store
   - Rewrites: composition_planner, diagram_generator, interaction_generator, process_section

2. **Run tests locally:**
   ```bash
   cd backend
   uv run pytest tests/ -q
   # Expected: 192 passed
   ```

3. **Test environment setup (optional, for image generation):**
   ```bash
   export GOOGLE_API_KEY=<your-key>
   export IMAGE_PROVIDER=gemini
   export ENVIRONMENT=development
   # Diagram generator will now use image path for appropriate templates
   ```

4. **Verify schema changes:**
   - Query a generated section: check for `simulations` list
   - Check composition_plans: verify `interactions` list present
   - Check state: verify `interaction_usage` tracked

5. **Merge when ready:**
   ```bash
   git checkout main
   git merge --ff-only claude/optimistic-poitras
   ```

---

## Reference: File Changes Summary

| File | Change | Impact |
|------|--------|--------|
| `types/composition.py` | Extended schema | 🟢 Backward compatible |
| `types/section_content.py` | Added fields | 🟢 Backward compatible |
| `state.py` | Added tracking | 🟢 Backward compatible |
| `nodes/composition_planner.py` | Rewrite (LLM) | 🟢 Fallback to heuristic |
| `nodes/diagram_generator.py` | Dual-path | 🟢 Defaults to spec |
| `nodes/interaction_generator.py` | Loop over list | 🟢 Singular still works |
| `nodes/interaction_decider.py` | Deprecate shim | 🟢 Re-exports work |
| `nodes/process_section.py` | Simplify | 🟢 Same behavior |
| `prompts/composition.py` | New | 🆕 LLM support |
| `prompts/diagram.py` | Additions | 🟢 Existing untouched |
| `catalogs/interaction_catalog.py` | New | 🆕 Pedagogical data |
| `providers/gemini_image_client.py` | New | 🆕 Image generation |
| `storage/image_store.py` | New | 🆕 Image storage |
| `providers/registry.py` | Added slot | 🟢 Minimal change |

---

## Contact

For questions about:
- **LLM composition decisions:** See `nodes/composition_planner.py` + `prompts/composition.py`
- **Image generation:** See `nodes/diagram_generator.py` + `providers/gemini_image_client.py`
- **Multi-interaction support:** See `nodes/interaction_generator.py`
- **Tests:** See `tests/pipeline/test_composition_planner.py`
