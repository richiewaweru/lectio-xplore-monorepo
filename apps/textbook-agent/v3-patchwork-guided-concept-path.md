# v3 Patchwork — Switch to guided-concept-path Template

## What and why

The v3 backend hardcodes `"diagram-led"` as the template in two places.
The correct template for all v3 generations is `"guided-concept-path"` —
the same one enabled in v2 (captured via `v2_capture`).

The `guided-concept-path` contract defines:
- `always_present`: section-header, hook-hero, explanation-block, what-next-bridge
- `available_components`: 28 components including worked-example-card,
  practice-stack, definition-card, pitfall-alert, diagram-block, diagram-series etc.

The Lesson Architect must also know it is planning for this template specifically
so it only selects components that are actually available in it.

---

## File 1 — router.py

**File:** `backend/src/generation/v3_studio/router.py`

Change the hardcoded `template_id` in `post_blueprint`:

```python
# Before
template_id = "diagram-led"

# After
template_id = "guided-concept-path"
```

One line. Two occurrences — check `post_blueprint` and `post_blueprint_adjust`
both use `"diagram-led"` as a fallback and change both.

---

## File 2 — preview_mapper.py

**File:** `backend/src/generation/v3_studio/preview_mapper.py`

Change the default parameter:

```python
# Before
def blueprint_to_preview_dto(
    *,
    blueprint_id: str,
    blueprint: ProductionBlueprint,
    template_id: str = "diagram-led",
) -> BlueprintPreviewDTO:

# After
def blueprint_to_preview_dto(
    *,
    blueprint_id: str,
    blueprint: ProductionBlueprint,
    template_id: str = "guided-concept-path",
) -> BlueprintPreviewDTO:
```

---

## File 3 — prompts.py

**File:** `backend/src/generation/v3_studio/prompts.py`

Update `_manifest_block()` to:
1. Load the `guided-concept-path` contract from `contracts/guided-concept-path.json`
2. Filter the manifest to only show components available in that contract
3. Mark `always_present` components explicitly so the Architect knows they are required

```python
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _load_guided_concept_contract() -> dict:
    path = Path(__file__).parents[3] / "contracts" / "guided-concept-path.json"
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _manifest_block() -> str:
    """
    Extract only what the Lesson Architect needs for planning.
    Filtered to components available in guided-concept-path.
    Format per component: slug [section_field]: role — cognitiveJob

    always_present components are marked as REQUIRED.
    Excludes: print, capacity, shadcn_primitive, behaviour_modes, subjects, capabilities.
    """
    manifest = get_manifest()
    contract = _load_guided_concept_contract()

    always_present = set(contract.get("always_present", []))
    available = set(contract.get("available_components", []))
    # always_present are also available
    all_available = always_present | available

    lines = [
        "TEMPLATE: guided-concept-path",
        "AVAILABLE COMPONENTS (use only these slugs):",
        f"REQUIRED in every section: {', '.join(sorted(always_present))}",
        "",
    ]

    for phase_id, phase in manifest["phases"].items():
        phase_components = [
            c for c in phase["components"]
            if c["id"] in all_available
        ]
        if not phase_components:
            continue

        lines.append(f"Phase {phase_id} — {phase['name']}:")
        for c in phase_components:
            slug = c["id"]
            section_field = c.get("section_field") or "—"
            role = c.get("role", "")
            cognitive_job = c.get("cognitive_job", "")
            required_tag = " [REQUIRED]" if slug in always_present else ""
            lines.append(
                f"  {slug} [{section_field}]{required_tag}: {role} — {cognitive_job}"
            )

    return "\n".join(lines)
```

Also update `build_architect_system_prompt()` to include the template
and component budget rules from the contract:

```python
def build_architect_system_prompt() -> str:
    contract = _load_guided_concept_contract()
    component_budget = contract.get("component_budget", {})
    max_per_section = contract.get("max_per_section", {})

    budget_rules = ""
    if component_budget:
        budget_rules = "\nCOMPONENT BUDGETS (max across entire lesson):\n"
        for slug, limit in component_budget.items():
            budget_rules += f"  {slug}: max {limit}\n"

    section_rules = ""
    if max_per_section:
        section_rules = "\nPER-SECTION LIMITS:\n"
        for slug, limit in max_per_section.items():
            section_rules += f"  {slug}: max {limit} per section\n"

    return f"""You are a lesson architect. Output ONLY a valid ProductionBlueprint matching the schema.

{_manifest_block()}

CONSTRAINT: Each section_field (shown in brackets above) may appear at
most once per section. Never plan two components with the same section_field
in the same section.
{budget_rules}{section_rules}
{_lens_block()}

Rules:
- Only use component slugs listed above. Never invent slugs.
- metadata: version "3.0", title, subject
- lesson: lesson_mode first_exposure|consolidation|repair|retrieval|transfer
- applied_lenses: min 1 lens, lens_id must match a lens above, effects non-empty
- voice: register simple|balanced|formal, optional tone
- anchor: reuse_scope string
- sections: min 1, each section_id, title, role, visual_required bool,
  components (slugs from above only) with content_intent
- question_plan: min 1, each question_id, section_id,
  temperature warm|medium|cold|transfer, prompt, expected_answer, diagram_required
- visual_strategy: visuals list for sections where visual_required=true
- answer_key: style e.g. concise_steps or answers_only
"""
```

---

## File 4 — V3Canvas.svelte (and wherever templateId is passed)

**File:** `frontend/src/routes/studio/+page.svelte`

The `V3Canvas` and `V3LectioSectionEmbed` components receive `templateId`.
Change any default or hardcoded `"diagram-led"` to `"guided-concept-path"`:

```typescript
// In handleBlueprintApproved or wherever canvas is initialised:
// Before
templateId: blueprint.template_id ?? 'diagram-led'

// After
templateId: blueprint.template_id ?? 'guided-concept-path'
```

Also in `V3Canvas.svelte` if it has a fallback:
```svelte
<!-- Before -->
<V3LectioSectionEmbed templateId={templateId ?? 'diagram-led'} ... />

<!-- After -->
<V3LectioSectionEmbed templateId={templateId ?? 'guided-concept-path'} ... />
```

Search the entire frontend for `"diagram-led"` and replace all occurrences
with `"guided-concept-path"`. It may also appear in:
- `V3CanvasSection.svelte`
- `V3LectioSectionEmbed.svelte`
- `v3-studio.svelte.ts` store
- Any print route

---

## Verification

```
□ POST /api/v1/v3/blueprint response has template_id = "guided-concept-path"
□ Blueprint component slugs are all in guided-concept-path available_components
□ always_present slugs (section-header, hook-hero, explanation-block,
  what-next-bridge) appear in every section of the blueprint
□ No "diagram-led" string remains anywhere in v3 code paths
□ V3LectioSectionEmbed renders using guided-concept-path template registry
□ diagram-block appears at most twice per lesson (component_budget rule)
□ worked-example-card appears at most once per section (max_per_section rule)
```
