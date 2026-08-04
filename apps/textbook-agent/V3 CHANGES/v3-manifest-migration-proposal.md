# V3 Manifest Migration Proposal
## Replace fragmented Lectio contract files with unified `lectio-content-contract.json`

**Scope:** Backend only — Textbook Generator (V3 execution path)  
**Lectio version:** Bump consumer to **0.4.2** and sync all contracts and generated Python classes  
**Pre-condition:** Lectio 0.4.2 must be published to GitHub Packages before this proposal is executed  

> **Goal:** Replace every read of `manifest.json`, `component-registry.json`, `component-field-map.json`, and `guided-concept-path.json` in the V3 execution path with reads of `lectio-content-contract.json`. Give the section writer LLM compact, writer-appropriate field contracts instead of raw registry blobs. Add Pydantic validation gates so every generated block and every assembled section is schema-validated before it leaves the executor. The pipeline (v1/v2) path must continue working throughout — do not touch anything outside V3.

---

## Step 0 — Bump Lectio to 0.4.2 and sync all contracts

This is the first thing to do. All subsequent steps depend on the new contract files being present.

### 0a — Update Lectio version in `frontend/package.json`

Open `frontend/package.json`. Find the `lectio` entry in `dependencies` and change it to `0.4.2`:

```json
{
  "dependencies": {
    "lectio": "0.4.2"
  }
}
```

Then run from the `frontend/` directory:

```bash
npm install
```

This updates both `package-lock.json` and `pnpm-lock.yaml`. Commit both lockfiles alongside `package.json`. The `frontend-lockfile-sync.yml` CI workflow will validate they are in sync.

### 0b — Run `tools/update_lectio_contracts.py`

This script syncs the exported contract files from the installed Lectio package into `backend/contracts/` and regenerates `backend/src/pipeline/types/section_content.py`.

From the repository root:

```bash
uv run python tools/update_lectio_contracts.py
```

The script must copy the following files from the Lectio 0.4.2 package into `backend/contracts/`:

- `lectio-content-contract.json` — the new unified contract
- `section-content-schema.json` — JSON Schema for SectionContent

It must also regenerate `backend/src/pipeline/types/section_content.py` from `section-content-schema.json` using `datamodel-code-generator`. The regenerated file must have an `AUTO-GENERATED` header in its first 8 lines.

**If `lectio-content-contract.json` is not copied by the script:** open `tools/update_lectio_contracts.py`, find the list of files the script copies, and add `"lectio-content-contract.json"` to it. The file lives at `contracts/lectio-content-contract.json` inside the Lectio npm package.

### 0c — Verify the new contract has the expected shape

After running the sync script, open `backend/contracts/lectio-content-contract.json` and confirm:

- Top-level keys: `version`, `source`, `formatting_policy`, `templates`, `planner_index`, `component_cards`
- `planner_index.phase_map["1"]` has `name`, `description`, and `components` keys
- `planner_index.phase_map["1"].name` equals `"Orient"`
- `component_cards["explanation-block"]` has `section_field`, `field_contracts`, `component_constraints`, `examples`
- `component_cards["explanation-block"].section_field` equals `"explanation"`
- `component_cards["diagram-block"]` exists and has `section_field` equals `"diagram"`

If any of these checks fail, stop and raise the issue — the contract is not correctly formed and proceeding will cause silent failures.

### 0d — Verify `section_content.py` is current

Open `backend/src/pipeline/types/section_content.py`. Check:

- Line 1–8 contains `AUTO-GENERATED`
- `ExplanationContent`, `PracticeContent`, `HookHeroContent`, `SectionContent`, `DiagramContent` are all present as Pydantic `BaseModel` subclasses
- `SectionContent` has fields: `header`, `hook`, `explanation`, `definition`, `worked_example`, `practice`, `quiz`, `diagram`, `summary`

If the file is outdated or missing models, the Pydantic validation gates in later steps will silently pass through invalid content. Do not proceed until this is correct.

---

## Step 1 — Extend `pipeline/contracts.py` with unified contract loaders

**File:** `backend/src/pipeline/contracts.py`

### Goal

Add four new public functions that read from `lectio-content-contract.json`. Keep all existing functions — `get_manifest()`, `get_component_registry_entry()`, `get_section_field_for_component()`, etc. — completely unchanged. The pipeline (v1/v2) path depends on them and must not be affected.

### 1a — Add `"lectio-content-contract"` to `_META_FILES`

Find the `_META_FILES` set near the top of the file:

```python
_META_FILES = {
    "classification",
    "component-examples",
    "component-field-map",
    "component-registry",
    "component-schemas",
    "manifest",
    "preset-registry",
    "print-rules",
    "section-content-schema",
}
```

Add one entry so the new file is not mistaken for a template ID:

```python
_META_FILES = {
    "classification",
    "component-examples",
    "component-field-map",
    "component-registry",
    "component-schemas",
    "lectio-content-contract",    # ← add this
    "manifest",
    "preset-registry",
    "print-rules",
    "section-content-schema",
}
```

### 1b — Add the loader and four public accessors

Add the following block immediately after the existing `_load_manifest()` function. Do not change anything above or below this insertion point.

```python
@lru_cache(maxsize=None)
def _load_lectio_content_contract() -> dict:
    """Load the unified Lectio content contract (lectio-content-contract.json)."""
    path = _contracts_dir() / "lectio-content-contract.json"
    if not path.exists():
        raise FileNotFoundError(
            "lectio-content-contract.json not found in backend/contracts/. "
            "Run: uv run python tools/update_lectio_contracts.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def get_component_card(component_id: str) -> dict | None:
    """
    Return the full component card for the given component_id from
    lectio-content-contract.json, or None if the component is unknown.

    A card contains: component_id, section_field, role, cognitive_job,
    capacity, capabilities, field_contracts, component_constraints, examples,
    print_behavior.

    Use this instead of get_component_registry_entry() in V3 code paths.
    """
    return _load_lectio_content_contract().get("component_cards", {}).get(component_id)


def get_planner_index() -> dict:
    """
    Return the planner_index from lectio-content-contract.json.

    Shape:
      {
        "component_ids": [...],
        "phase_map": {
          "1": { "name": "Orient", "description": "...", "components": [...] },
          ...
        }
      }

    Use this in the architect prompt instead of reading manifest.json phases.
    """
    return _load_lectio_content_contract().get("planner_index", {})


def get_template_contract(template_id: str) -> dict | None:
    """
    Return template metadata from lectio-content-contract.json for the given
    template_id, or None if the template is unknown.

    Shape:
      {
        "always_present": [...],
        "available_components": [...],
        "component_budget": { "diagram-block": 2, ... },
        "max_per_section": { "worked-example-card": 1, ... }
      }

    Use this instead of reading guided-concept-path.json directly.
    """
    return _load_lectio_content_contract().get("templates", {}).get(template_id)


def get_formatting_policy() -> dict:
    """
    Return the format type legend from lectio-content-contract.json.

    Keys are format type names (e.g. "block_markdown", "plain_phrase_list").
    Values are human-readable descriptions of what each format means.

    Emit this once at the top of the section writer prompt as a legend,
    not per-component.
    """
    return _load_lectio_content_contract().get("formatting_policy", {})
```

### 1c — Add cache clear for the new loader

Find the `clear_cache()` function at the bottom of `contracts.py`:

```python
def clear_cache() -> None:
    _load_contract_raw.cache_clear()
    _load_field_map.cache_clear()
    _load_component_registry.cache_clear()
    _load_preset_registry.cache_clear()
    _load_section_content_schema.cache_clear()
```

Add one line:

```python
def clear_cache() -> None:
    _load_contract_raw.cache_clear()
    _load_field_map.cache_clear()
    _load_component_registry.cache_clear()
    _load_preset_registry.cache_clear()
    _load_section_content_schema.cache_clear()
    _load_lectio_content_contract.cache_clear()    # ← add this
```

### Verification for Step 1

Run from `backend/`:

```bash
uv run python -c "
from pipeline.contracts import clear_cache, get_component_card, get_planner_index, get_template_contract, get_formatting_policy
clear_cache()
card = get_component_card('explanation-block')
assert card is not None, 'explanation-block card missing'
assert card['section_field'] == 'explanation', f'wrong section_field: {card[\"section_field\"]}'
assert 'field_contracts' in card, 'field_contracts missing from card'
assert 'body' in card['field_contracts'], 'body missing from field_contracts'
planner = get_planner_index()
assert planner['phase_map']['1']['name'] == 'Orient', 'phase 1 name wrong'
template = get_template_contract('guided-concept-path')
assert template is not None, 'guided-concept-path template missing'
assert 'always_present' in template, 'always_present missing from template'
policy = get_formatting_policy()
assert 'block_markdown' in policy, 'block_markdown missing from formatting_policy'
print('Step 1 OK')
"
```

All assertions must pass before proceeding.

---

## Step 2 — Replace the architect manifest block

**File:** `backend/src/generation/v3_studio/prompts.py`

### Goal

Replace `_manifest_block()` (which reads `manifest.json` + `guided-concept-path.json`) with `_planner_index_block()` that reads only from `lectio-content-contract.json` via the new `pipeline.contracts` accessors. The architect prompt output must be identical in structure to what it is today: named phases, component slugs with section fields, REQUIRED tags, budget rules.

### 2a — Remove the old guided concept contract loader

Find and delete the entire `_load_guided_concept_contract()` function:

```python
# DELETE THIS ENTIRE FUNCTION:
@lru_cache(maxsize=1)
def _load_guided_concept_contract() -> dict:
    path = Path(__file__).parents[3] / "contracts" / "guided-concept-path.json"
    return json.loads(path.read_text(encoding="utf-8"))
```

### 2b — Remove the `get_manifest` import

At the top of `prompts.py`, find:

```python
from pipeline.contracts import get_manifest
```

Replace with:

```python
from pipeline.contracts import get_component_card, get_planner_index, get_template_contract
```

Also remove the `from pathlib import Path` import if `Path` is no longer used anywhere else in the file after removing `_load_guided_concept_contract()`. Check before removing.

### 2c — Replace `_manifest_block()` with `_planner_index_block()`

Delete the entire existing `_manifest_block()` function and replace it with `_planner_index_block()`:

```python
@lru_cache(maxsize=1)
def _planner_index_block() -> str:
    """
    Build the component palette block for the lesson architect prompt.

    Reads from lectio-content-contract.json via pipeline.contracts accessors.
    Produces the same structure the architect currently sees from manifest.json:
    named phases, component slugs with section fields, [REQUIRED] tags,
    component budgets, and per-section limits.

    The cache is intentional — this is called once per server process.
    If contracts change, restart the server or call clear_cache() first.
    """
    template = get_template_contract("guided-concept-path") or {}
    planner = get_planner_index()

    always_present = set(template.get("always_present", []))
    available = set(template.get("available_components", []))
    all_available = always_present | available

    component_budget: dict = template.get("component_budget", {})
    max_per_section: dict = template.get("max_per_section", {})

    lines: list[str] = [
        "TEMPLATE: guided-concept-path",
        f"REQUIRED in every section: {', '.join(sorted(always_present)) or 'none'}",
        "AVAILABLE COMPONENTS (use only these slugs):",
    ]

    phase_map: dict = planner.get("phase_map", {})
    for phase_num in sorted(phase_map.keys(), key=lambda k: int(k)):
        phase = phase_map[phase_num]
        phase_name = phase.get("name", f"Phase {phase_num}")
        lines.append(f"\nPhase {phase_num} — {phase_name}:")
        for cid in phase.get("components", []):
            if cid not in all_available:
                continue
            card = get_component_card(cid) or {}
            field = card.get("section_field", "—")
            role = card.get("role", "")
            cj = card.get("cognitive_job", "")
            req = " [REQUIRED]" if cid in always_present else ""
            lines.append(f"  {cid} [{field}]{req}: {role} — {cj}")

    if component_budget:
        lines.append("\nCOMPONENT BUDGETS (max across entire lesson):")
        for slug, limit in component_budget.items():
            lines.append(f"  {slug}: max {limit}")

    if max_per_section:
        lines.append("\nPER-SECTION LIMITS:")
        for slug, limit in max_per_section.items():
            lines.append(f"  {slug}: max {limit} per section")

    return "\n".join(lines)
```

### 2d — Update `build_architect_system_prompt()` to call `_planner_index_block()`

Find `build_architect_system_prompt()`. It currently:
1. Calls `_load_guided_concept_contract()` to get `component_budget` and `max_per_section`
2. Calls `_manifest_block()` to get the component list block
3. Assembles budget lines separately

Replace all of that with a single call to `_planner_index_block()`. The budgets are now included inside the block itself, so remove the separate budget assembly:

```python
def build_architect_system_prompt() -> str:
    """System prompt for the lesson architect, including live Lectio manifest and lenses."""
    from generation.v3_lenses.loader import format_lenses_for_prompt

    planner_block = _planner_index_block()   # budgets are included inside this block now
    lenses_block = format_lenses_for_prompt()

    return f"""You are a lesson architect. Output ONLY a valid ProductionBlueprint matching the schema.

{planner_block}

CONSTRAINT: Each section_field (shown in brackets above) may appear at
most once per section. Never plan two components with the same
section_field in the same section.

{lenses_block}

Rules:
- Only use component slugs from the component list above. Never invent new slugs.
- metadata: version "3.0", title, subject (from teacher subject)
- lesson: lesson_mode first_exposure|consolidation|repair|retrieval|transfer, resource_type lesson|mini_booklet
- applied_lenses: min 1 lens with lens_id and effects (non-empty strings); choose lens_ids from the pedagogical lenses section where possible
- voice: register (simple|balanced|formal etc), optional tone
- anchor: reuse_scope string
- sections: min 1, each section_id, title, role, visual_required bool,
  components min 1 with component slug from the list above and content_intent
- question_plan: min 1 items with question_id, section_id, temperature
  warm|medium|cold|transfer, prompt, expected_answer, diagram_required
- visual_strategy: visuals list (can match sections needing visuals)
- answer_key: style string (e.g. concise_steps, answers_only)
- teacher_materials, prior_knowledge lists allowed
Use sensible IDs like orient, model, practice, summary for sections when appropriate."""
```

### 2e — Update tests in `backend/tests/generation/test_v3_studio_prompts.py`

Find `test_manifest_block_is_guided_concept_filtered`. Update it to call `_planner_index_block()` instead of `_manifest_block()`:

```python
def test_manifest_block_is_guided_concept_filtered() -> None:
    from generation.v3_studio.prompts import _planner_index_block
    block = _planner_index_block()
    assert "TEMPLATE: guided-concept-path" in block
    assert "AVAILABLE COMPONENTS (use only these slugs):" in block
    assert "REQUIRED in every section:" in block
    # Phase names must be present (from planner_index.phase_map)
    assert "Orient" in block
    # Known required components with correct section fields
    assert "hook-hero [hook]" in block
    assert "explanation-block [explanation]" in block
    # Non-V3 component slugs must not appear
    assert "concept_intro [explanation]" not in block
```

Find `test_architect_prompt_includes_contract_limits`. The budget lines are now inside `_planner_index_block()` so the assertions still hold:

```python
def test_architect_prompt_includes_contract_limits() -> None:
    from generation.v3_studio.prompts import build_architect_system_prompt
    prompt = build_architect_system_prompt()
    assert "COMPONENT BUDGETS (max across entire lesson):" in prompt
    assert "diagram-block: max" in prompt
    assert "PER-SECTION LIMITS:" in prompt
    assert "worked-example-card: max" in prompt
```

Remove any import of `_manifest_block` from the test file.

### Verification for Step 2

```bash
uv run pytest backend/tests/generation/test_v3_studio_prompts.py -v
```

All tests must pass. Additionally confirm manually:

```bash
uv run python -c "
from generation.v3_studio.prompts import _planner_index_block, build_architect_system_prompt
block = _planner_index_block()
assert 'Orient' in block
assert 'manifest' not in block.lower()
prompt = build_architect_system_prompt()
assert 'COMPONENT BUDGETS' in prompt
print('Step 2 OK')
print('First 40 lines of planner block:')
print('\n'.join(block.splitlines()[:40]))
"
```

Confirm no import of `get_manifest` remains in `prompts.py` and no reference to `guided-concept-path.json` or `_load_guided_concept_contract` remains anywhere in the file.

---

## Step 3 — Replace `manifest_components` → `component_cards` throughout V3 execution

**Files:**
- `backend/src/v3_execution/models.py`
- `backend/src/v3_execution/compile_orders.py`
- `backend/src/v3_execution/executors/section_writer.py`
- `backend/src/v3_execution/runtime/validation.py`

### Goal

Rename `manifest_components` to `component_cards` on `SectionWriterWorkOrder`. Replace `_manifest_for_components()` in `compile_orders.py` with `_component_cards_for_components()` that reads from `get_component_card()`. Update every site that constructs, reads, or passes `manifest_components`.

Because `SectionWriterWorkOrder` has `model_config = ConfigDict(extra="forbid")`, this rename is a hard breaking change — if any site still uses the old field name, Pydantic will raise a validation error at runtime. All four files must be updated atomically.

### 3a — Rename the field in `models.py`

Find `SectionWriterWorkOrder` in `backend/src/v3_execution/models.py`. Change:

```python
manifest_components: dict[str, Any] = Field(default_factory=dict)
```

To:

```python
component_cards: dict[str, Any] = Field(
    default_factory=dict,
    description=(
        "Component cards from lectio-content-contract.json keyed by component_id. "
        "Each card contains section_field, field_contracts, component_constraints, "
        "role, cognitive_job, and one compact example. "
        "Used by the section writer prompt and validation layer."
    ),
)
```

Do not change any other field on `SectionWriterWorkOrder`.

### 3b — Replace `_manifest_for_components()` in `compile_orders.py`

Find the function in `backend/src/v3_execution/compile_orders.py`:

```python
def _manifest_for_components(component_ids: list[str], template_id: str) -> dict[str, object]:
    from pipeline.contracts import get_component_registry_entry

    manifest: dict[str, object] = {}
    for cid in component_ids:
        entry = get_component_registry_entry(cid) or {}
        manifest[cid] = entry
    _ = template_id
    return manifest
```

Delete it entirely and replace with:

```python
def _component_cards_for_components(component_ids: list[str]) -> dict[str, dict]:
    """
    Fetch Lectio component cards for the given component IDs from
    lectio-content-contract.json. Raises ValueError for any unknown component.

    Cards are keyed by component_id and contain: section_field, field_contracts,
    component_constraints, role, cognitive_job, capacity, and one compact example.

    These cards are attached to SectionWriterWorkOrder and used by both the
    section writer prompt builder and the validation layer.
    """
    from pipeline.contracts import get_component_card

    cards: dict[str, dict] = {}
    for cid in component_ids:
        card = get_component_card(cid)
        if card is None:
            raise ValueError(
                f"Unknown Lectio component: '{cid}'. "
                "The component is not present in lectio-content-contract.json. "
                "Check that Lectio is at 0.4.2 and contracts are up to date: "
                "uv run python tools/update_lectio_contracts.py"
            )
        cards[cid] = card
    return cards
```

### 3c — Update the `SectionWriterWorkOrder` construction call in `compile_orders.py`

Find the `wo = SectionWriterWorkOrder(...)` call inside `compile_execution_bundle()`. Change:

```python
manifest_components=_manifest_for_components(
    [canonical_component_id(c.component) for c in sec.components],
    template_id,
),
```

To:

```python
component_cards=_component_cards_for_components(
    [canonical_component_id(c.component) for c in sec.components],
),
```

### 3d — Update `validate_component_batch()` call in `section_writer.py`

In `backend/src/v3_execution/executors/section_writer.py`, find:

```python
errs = validate_component_batch(
    blocks,
    order,
    manifest_components=order.manifest_components,
)
```

Change to:

```python
errs = validate_component_batch(
    blocks,
    order,
    component_cards=order.component_cards,
)
```

### 3e — Update `validation.py` to use `component_cards`

In `backend/src/v3_execution/runtime/validation.py`, find `validate_component_block()`:

```python
def validate_component_block(
    block: GeneratedComponentBlock,
    work_order: SectionWriterWorkOrder,
    manifest_components: dict | None = None,
) -> list[str]:
```

Change the signature and body:

```python
def validate_component_block(
    block: GeneratedComponentBlock,
    work_order: SectionWriterWorkOrder,
    component_cards: dict | None = None,
) -> list[str]:
    errors: list[str] = []

    planned_ids = [c.component_id for c in work_order.section.components]
    if block.component_id not in planned_ids:
        errors.append(f"Unplanned component: {block.component_id}")

    # Derive expected section_field from the card (snake_case key, not camelCase)
    expected_field: str | None = None
    if component_cards and block.component_id in component_cards:
        card = component_cards[block.component_id] or {}
        expected_field = card.get("section_field")
    else:
        # Fall back to the field map for components not in the card dict
        from pipeline.contracts import get_section_field_for_component
        expected_field = get_section_field_for_component(block.component_id)

    if expected_field and block.section_field != expected_field:
        errors.append(
            f"section_field mismatch for {block.component_id}: "
            f"expected '{expected_field}', got '{block.section_field}'"
        )

    for comp in work_order.section.components:
        if comp.uses_anchor_id:
            errors.extend(
                check_anchor_units_present(
                    block.data,
                    work_order.source_of_truth,
                    comp.uses_anchor_id,
                )
            )
    return errors
```

Find `validate_component_batch()` in the same file:

```python
def validate_component_batch(
    blocks: Iterable[GeneratedComponentBlock],
    work_order: SectionWriterWorkOrder,
    manifest_components: dict | None = None,
) -> list[str]:
```

Change:

```python
def validate_component_batch(
    blocks: Iterable[GeneratedComponentBlock],
    work_order: SectionWriterWorkOrder,
    component_cards: dict | None = None,
) -> list[str]:
    errors: list[str] = []
    for block in blocks:
        errors.extend(validate_component_block(block, work_order, component_cards=component_cards))
    return errors
```

### Verification for Step 3

```bash
uv run python -c "
from v3_execution.compile_orders import _component_cards_for_components
cards = _component_cards_for_components(['explanation-block', 'practice-stack'])
assert 'explanation-block' in cards
assert cards['explanation-block']['section_field'] == 'explanation'
assert 'practice-stack' in cards
print('_component_cards_for_components OK')
try:
    _component_cards_for_components(['nonexistent-component'])
    raise AssertionError('Should have raised ValueError')
except ValueError as e:
    print(f'Unknown component raises correctly: {e}')
"
```

```bash
uv run pytest backend/tests/v3_execution/ -v -k "not integration"
```

Confirm `manifest_components` does not appear anywhere in `models.py`, `compile_orders.py`, `section_writer.py` (executor), or `validation.py`.

---

## Step 4 — Rewrite the section writer prompt

**File:** `backend/src/v3_execution/prompts/section_writer.py`

### Goal

Replace the "MANIFEST SCHEMA HINT" block, which dumps raw registry entries as JSON, with a "LECTIO COMPONENT CONTRACTS" block that gives the writer LLM only what it needs: the target field, the format type for each sub-field, constraints, and one compact example. The output shape `{"fields": {...}}` must not change.

### 4a — Add helper: `format_formatting_policy_legend()`

Add this helper before `build_section_writer_prompt()`:

```python
def format_formatting_policy_legend(policy: dict) -> str:
    """
    Emit the format type vocabulary once at the top of the prompt.
    This tells the writer what 'block_markdown', 'plain_phrase_list', etc. mean
    so it does not need to be repeated per-component.
    """
    if not policy:
        return ""
    lines = ["FORMAT TYPE LEGEND (referenced in component contracts below):"]
    for fmt_name, fmt_desc in policy.items():
        lines.append(f"  {fmt_name}: {fmt_desc}")
    return "\n".join(lines)
```

### 4b — Add helper: `format_component_contract_for_writer()`

Add this helper immediately after `format_formatting_policy_legend()`:

```python
def format_component_contract_for_writer(card: dict, content_intent: str) -> str:
    """
    Format a single component card into a compact writer-facing contract block.

    Includes: component ID, target section field, intent, purpose, cognitive job,
    field-level contracts (format, description, constraints), component-level
    constraints, and one compact example.

    Does NOT include: render behavior, print behavior, status, capabilities,
    or any rendering metadata. The writer does not need those.
    """
    cid = card.get("component_id", "")
    field = card.get("section_field", "")
    role = card.get("role", "")
    cj = card.get("cognitive_job", "")
    field_contracts: dict = card.get("field_contracts", {})
    constraints: list = card.get("component_constraints", [])
    examples: list = card.get("examples", [])

    lines = [
        f"{cid} → section field: {field}",
        f"Intent: {content_intent}",
        f"Purpose: {role}",
        f"Cognitive job: {cj}",
    ]

    if field_contracts:
        lines.append("Field contracts:")
        for fname, fdef in field_contracts.items():
            fmt = fdef.get("format", "")
            desc = fdef.get("description", "")
            fconstraints: list = fdef.get("constraints", [])
            # Mark fields that are not strictly required
            optional_tag = " (optional)" if fdef.get("required") is False else ""
            lines.append(f"  {fname}{optional_tag} [{fmt}]")
            if desc:
                lines.append(f"    {desc}")
            for fc in fconstraints:
                lines.append(f"    constraint: {fc}")
    else:
        lines.append("Field contracts: none declared — follow section_field name as the key.")

    if constraints:
        lines.append("Component constraints:")
        for c in constraints:
            lines.append(f"  - {c}")

    if examples:
        import json as _json
        ex = examples[0]
        lines.append(f"Example output:")
        lines.append(f"  {_json.dumps(ex, ensure_ascii=False)}")

    return "\n".join(lines)
```

### 4c — Rewrite `build_section_writer_prompt()`

Replace the entire function body. The function signature stays the same. The output shape `{"fields": {...}}` stays the same. Only the contract block changes.

```python
def build_section_writer_prompt(order: SectionWriterWorkOrder) -> str:
    from pipeline.contracts import get_formatting_policy

    # One-line summary per component for the COMPONENTS TO WRITE block
    components_list = "\n".join(
        f"- {c.teacher_label or c.component_id} ({c.component_id}): {c.content_intent}"
        for c in order.section.components
    )

    # Format type legend — emitted once, not per-component
    policy = get_formatting_policy()
    policy_block = format_formatting_policy_legend(policy)

    # Per-component writer contracts — compact, writer-appropriate only
    contract_blocks = "\n\n".join(
        format_component_contract_for_writer(
            order.component_cards.get(c.component_id, {}),
            c.content_intent,
        )
        for c in order.section.components
    )

    return f"""You are a section writer, not a lesson planner.

Your job is to generate component content for one section of a lesson.
You have been given a precise work order. Follow it exactly.

SECTION: {order.section.title}
SECTION_ID: {order.section.id}
LEARNING INTENT: {order.section.learning_intent}

COMPONENTS TO WRITE:
{components_list}

REGISTER:
- Level: {order.register_spec.level}
- Sentence length: {order.register_spec.sentence_length}
- Vocabulary: {order.register_spec.vocabulary_policy}
- Tone: {order.register_spec.tone}
- Avoid: {", ".join(order.register_spec.avoid) or "none"}

LEARNER PROFILE:
{order.learner_profile.level_summary}
Reading load: {order.learner_profile.reading_load}
Language support: {order.learner_profile.language_support}
Pacing: {order.learner_profile.pacing}

SUPPORT ADAPTATIONS:
{format_support_adaptations(order.support_adaptations)}

ANCHOR FACTS (do not change these):
{format_source_of_truth(order.source_of_truth)}

CONSISTENCY RULES:
{format_consistency_rules(order.consistency_rules)}

SECTION CONSTRAINTS:
{chr(10).join(f"- {c}" for c in order.section.constraints) or "- none"}

{policy_block}

LECTIO COMPONENT CONTRACTS:
{contract_blocks}

STRICT RULES:
- Generate only the components listed above. Do not add others.
- Do not add diagrams, questions, or visuals. Those are handled separately.
- Do not change anchor facts, units, or fixed terms.
- Do not change question difficulty or numbering.
- Each section_field key in your output must exactly match the
  "section field" shown in the component contract above.
Return JSON ONLY with this exact shape:
{{"fields": {{
  "<section_field snake_case>": {{ ...matching component schema }},
  ...
}}}}
"""
```

### 4d — Update imports at the top of `section_writer.py`

The file currently imports nothing from `pipeline.contracts`. The `get_formatting_policy` call is inside the function body using a local import, which is fine. However, remove the `import json` at the module level if it is only used for the old `field_map` dump — the new code does not need a module-level `json` import (it uses one inside `format_component_contract_for_writer`).

### Verification for Step 4

```bash
uv run python -c "
from v3_execution.models import (
    SectionWriterWorkOrder, WriterSection, WriterSectionComponent,
    RegisterSpec, LearnerProfileSpec,
)
from pipeline.contracts import get_component_card, clear_cache
clear_cache()

card = get_component_card('explanation-block')
order = SectionWriterWorkOrder(
    work_order_id='test-001',
    section=WriterSection(
        id='s-orient',
        title='Test Section',
        learning_intent='Understand photosynthesis',
        components=[
            WriterSectionComponent(
                component_id='explanation-block',
                teacher_label='Explanation',
                content_intent='explain the light-dependent reactions',
            )
        ],
    ),
    register=RegisterSpec(),
    learner_profile=LearnerProfileSpec(),
    component_cards={'explanation-block': card},
    template_id='guided-concept-path',
)

from v3_execution.prompts.section_writer import build_section_writer_prompt
prompt = build_section_writer_prompt(order)

assert 'MANIFEST SCHEMA HINT' not in prompt, 'Old manifest block still present'
assert 'LECTIO COMPONENT CONTRACTS' in prompt, 'New contract block missing'
assert 'explanation-block → section field: explanation' in prompt, 'Component contract missing'
assert 'FORMAT TYPE LEGEND' in prompt, 'Formatting policy legend missing'
assert 'manifest' not in prompt.lower(), 'Manifest language still in prompt'
print('Step 4 OK')
"
```

---

## Step 5 — Add Pydantic validation gate in `execute_section()`

**Files:**
- new `backend/src/v3_execution/runtime/lectio_validation.py`
- `backend/src/v3_execution/executors/section_writer.py`

### Goal

Before a `GeneratedComponentBlock` is created, validate the raw writer output against the generated Pydantic model for that section field. Validation errors are collected and surfaced — the block is still created with the original data so repair routing can proceed. Nothing is silently swallowed.

### 5a — Create `backend/src/v3_execution/runtime/lectio_validation.py`

Create this file from scratch. Do not reuse or import from `runtime/validation.py`.

```python
"""
v3_execution.runtime.lectio_validation

Pydantic-based validation gates for V3 section generation.

validate_lectio_field_payload() — validates a single field's data against
  the generated Pydantic model for that section field.

validate_section_content() — validates a fully assembled section bucket
  against the top-level SectionContent model.

Both functions return (data_or_none, list_of_error_strings).
Errors are descriptive and surfaced to the coherence reviewer — they
do not cause generation to abort.
"""

from __future__ import annotations

from pydantic import ValidationError

# Import all field models from the generated adapter.
# If a model is missing here, field validation silently passes through for
# that field — check section_content.py and add the missing import.
from pipeline.types.section_content import (
    SectionContent,
)

# Attempt to import all known field models.
# Add new ones here as Lectio adds new components.
_FIELD_MODELS: dict[str, type] = {}

def _try_import_field_models() -> None:
    """
    Populate _FIELD_MODELS from the generated section_content module.
    Uses individual try/except so a missing model does not block others.
    Each key is the section_field name (snake_case) as it appears in
    lectio-content-contract.json component cards.
    """
    from pipeline.types import section_content as sc

    field_model_candidates = {
        "header":          "SectionHeaderContent",
        "hook":            "HookHeroContent",
        "explanation":     "ExplanationContent",
        "definition":      "DefinitionContent",
        "worked_example":  "WorkedExampleContent",
        "practice":        "PracticeContent",
        "quiz":            "QuizContent",
        "reflection":      "ReflectionContent",
        "summary":         "SummaryBlockContent",
        "comparison_grid": "ComparisonGridContent",
        "timeline":        "TimelineContent",
        "fill_in_blank":   "FillInBlankContent",
        "student_textbox": "StudentTextboxContent",
        "short_answer":    "ShortAnswerContent",
        "what_next":       "WhatNextContent",
        "prerequisite":    "PrerequisiteStripContent",
        "key_fact":        "KeyFactContent",
        "insight":         "InsightStripContent",
        "pitfall":         "PitfallAlertContent",
        "callout":         "CalloutBlockContent",
    }

    for field_name, class_name in field_model_candidates.items():
        model_cls = getattr(sc, class_name, None)
        if model_cls is not None:
            _FIELD_MODELS[field_name] = model_cls


_try_import_field_models()


def validate_lectio_field_payload(
    field_name: str,
    data: dict,
) -> tuple[dict, list[str]]:
    """
    Validate a single field's writer output against its Pydantic model.

    Returns (validated_data, errors).
    - If a model exists for field_name: runs model_validate(), returns
      model_dump(exclude_none=True) on success, or original data + errors on failure.
    - If no model exists for field_name: returns (data, []) — pass-through.

    The caller should always use the returned data (not the input data)
    when creating GeneratedComponentBlock, so validation coercion applies.
    """
    model_cls = _FIELD_MODELS.get(field_name)
    if model_cls is None:
        # No Pydantic model for this field — pass through without error.
        # This is expected for newly added components not yet in section_content.py.
        return data, []

    try:
        validated = model_cls.model_validate(data)
        return validated.model_dump(exclude_none=True), []
    except ValidationError as exc:
        errors = [
            f"{field_name}.{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        # Return original data so the block is still created for repair routing
        return data, errors


def validate_section_content(bucket: dict) -> tuple[dict | None, list[str]]:
    """
    Validate a fully assembled section bucket against SectionContent.

    Returns (validated_bucket, errors).
    - On success: returns (validated_dict, []).
    - On failure: returns (None, errors). The caller should flag the section
      with _schema_warnings but still append it to the output — do not drop it.
    """
    try:
        validated = SectionContent.model_validate(bucket)
        return validated.model_dump(exclude_none=True), []
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        return None, errors
```

**Important:** After creating this file, run:

```bash
uv run python -c "
from v3_execution.runtime.lectio_validation import _FIELD_MODELS, validate_lectio_field_payload, validate_section_content
print(f'Field models loaded: {sorted(_FIELD_MODELS.keys())}')
assert 'explanation' in _FIELD_MODELS, 'ExplanationContent not loaded'
assert 'practice' in _FIELD_MODELS, 'PracticeContent not loaded'
print('lectio_validation module OK')
"
```

If `_FIELD_MODELS` is empty or missing key models, open `pipeline/types/section_content.py` and find the correct class names, then update `field_model_candidates` in `_try_import_field_models()` to match.

### 5b — Add validation gate in `execute_section()`

In `backend/src/v3_execution/executors/section_writer.py`, add the import at the top:

```python
from v3_execution.runtime.lectio_validation import validate_lectio_field_payload
```

Find the loop that creates `GeneratedComponentBlock` objects inside `_attempt()`:

```python
for position, component in enumerate(order.section.components):
    field_name = get_section_field_for_component(component.component_id)
    if field_name is None:
        errors.append(f"No manifest mapping for component {component.component_id}")
        continue
    data = fields.get(field_name)
    if data is None:
        errors.append(f"Missing field output for {field_name}")
        continue
    blocks.append(
        GeneratedComponentBlock(
            block_id=str(uuid.uuid4()),
            section_id=order.section.id,
            component_id=component.component_id,
            section_field=field_name,
            position=position,
            data=data if isinstance(data, dict) else {"value": data},
            source_work_order_id=order.work_order_id,
        )
    )
```

Replace with:

```python
for position, component in enumerate(order.section.components):
    # Resolve section_field from the component card first, fall back to field map
    card = order.component_cards.get(component.component_id, {})
    field_name = card.get("section_field") or get_section_field_for_component(component.component_id)

    if field_name is None:
        errors.append(
            f"No section_field mapping for component '{component.component_id}'. "
            "Check that lectio-content-contract.json is up to date."
        )
        continue

    raw_data = fields.get(field_name)
    if raw_data is None:
        errors.append(f"Writer produced no output for field '{field_name}' ({component.component_id})")
        continue

    # Normalise to dict
    data_dict = raw_data if isinstance(raw_data, dict) else {"value": raw_data}

    # Pydantic validation gate — validates shape against generated model
    validated_data, field_errors = validate_lectio_field_payload(field_name, data_dict)
    if field_errors:
        errors.extend(field_errors)
        # Use original data for block creation so repair routing has something to work with
        validated_data = data_dict

    blocks.append(
        GeneratedComponentBlock(
            block_id=str(uuid.uuid4()),
            section_id=order.section.id,
            component_id=component.component_id,
            section_field=field_name,
            position=position,
            data=validated_data,
            source_work_order_id=order.work_order_id,
        )
    )
```

### Verification for Step 5

```bash
uv run python -c "
from v3_execution.runtime.lectio_validation import validate_lectio_field_payload

# Valid payload — should return validated data and no errors
good_data = {'body': 'Photosynthesis is the process...', 'emphasis': ['chlorophyll', 'ATP']}
out, errs = validate_lectio_field_payload('explanation', good_data)
assert errs == [], f'Unexpected errors: {errs}'
print('Valid payload: OK')

# Invalid payload — emphasis is a string, not a list
bad_data = {'body': 'Photosynthesis...', 'emphasis': 'chlorophyll'}
out, errs = validate_lectio_field_payload('explanation', bad_data)
assert len(errs) > 0, 'Should have produced validation errors'
print(f'Invalid payload errors caught: {errs}')

# Unknown field — should pass through without error
out, errs = validate_lectio_field_payload('unknown_field', {'foo': 'bar'})
assert errs == [], f'Unknown field should not error: {errs}'
print('Unknown field pass-through: OK')
print('Step 5 OK')
"
```

---

## Step 6 — Whole-section validation after assembly

**File:** `backend/src/v3_execution/assembly/section_builder.py`

### Goal

After each section bucket is fully assembled (components + questions + visuals merged), run `validate_section_content()` against the complete bucket. If invalid, add a `_schema_warnings` key to the bucket — do not drop the section. This key is picked up by the coherence reviewer in Step 7.

### 6a — Add import

At the top of `section_builder.py`, add:

```python
from v3_execution.runtime.lectio_validation import validate_section_content
```

### 6b — Add validation call after bucket assembly

Find the point in the section builder where the final bucket dict is complete and is about to be appended to the output list. The exact location depends on the builder's structure — look for the line that resembles `sections.append(bucket)` or `section_list.append(bucket)`.

Immediately before that append, add:

```python
# Validate complete section bucket against Lectio SectionContent schema.
# Invalid sections are flagged with _schema_warnings but are not dropped —
# the coherence reviewer uses these warnings to route repairs.
_validated_bucket, _schema_errors = validate_section_content(bucket)
if _schema_errors:
    bucket["_schema_warnings"] = _schema_errors
elif _validated_bucket is not None:
    # Use the validated (coerced) bucket if validation passed
    bucket = _validated_bucket
```

### Verification for Step 6

Create a temporary test to confirm the flow:

```bash
uv run python -c "
from v3_execution.runtime.lectio_validation import validate_section_content

# Valid minimal bucket
valid_bucket = {
    'section_id': 's-01',
    'template_id': 'guided-concept-path',
}
validated, errors = validate_section_content(valid_bucket)
# May have errors if required fields are missing — that is expected
print(f'Minimal bucket errors (expected some): {errors[:2]}')

# Deliberately malformed bucket
bad_bucket = {
    'section_id': 123,   # wrong type
    'template_id': None,
}
validated, errors = validate_section_content(bad_bucket)
assert errors, 'Should have caught type errors'
print(f'Malformed bucket errors caught: {errors[:2]}')
print('Step 6 OK')
"
```

---

## Step 7 — Update the coherence reviewer

**Files:**
- `backend/src/v3_review/reviewer.py`
- `backend/src/v3_review/deterministic_checks.py`
- `backend/src/v3_review/repair_router.py`
- `backend/src/v3_execution/runtime/runner.py`
- `backend/tests/v3_execution/test_v3_execution_core.py`

### Goal

Remove the `manifest: dict[str, Any]` parameter from `run_coherence_review()` and `route_repairs()`. Replace `check_component_ids_in_manifest()` with `check_component_ids_in_lectio_contract()` that uses `get_component_card()`. Replace JSON Schema validation in `check_lectio_schema_validity()` with Pydantic via `validate_section_content()`. Surface `_schema_warnings` from assembly.

### 7a — Replace `check_lectio_schema_validity()` in `deterministic_checks.py`

Find `check_lectio_schema_validity()`. It currently uses `Draft202012Validator` from `jsonschema`. Delete it and replace:

```python
def check_lectio_schema_validity(draft_pack: DraftPack) -> list[ReviewIssue]:
    """
    Validate each section in the draft against the SectionContent Pydantic model.

    Also surfaces _schema_warnings added during assembly (Step 6).
    The manifest parameter has been removed — validation is now Pydantic-based.
    """
    from v3_execution.runtime.lectio_validation import validate_section_content

    issues: list[ReviewIssue] = []
    for sec in draft_pack.sections:
        if not isinstance(sec, dict):
            continue
        sid = sec.get("section_id", "<unknown>")

        # Surface warnings flagged during assembly
        for warn in sec.get("_schema_warnings", []):
            issues.append(
                _issue(
                    severity="minor",
                    category="schema_violation",
                    message=f"Section '{sid}' assembly schema warning: {warn}",
                    generated_ref=sid,
                    executor="assembler",
                )
            )

        # Run full Pydantic validation on the section
        _, errors = validate_section_content(sec)
        for err in errors[:12]:   # cap at 12 to avoid flooding the review
            issues.append(
                _issue(
                    severity="major",
                    category="schema_violation",
                    message=f"Section '{sid}': {err}",
                    generated_ref=sid,
                    executor="assembler",
                )
            )
    return issues
```

Remove the `from jsonschema import Draft202012Validator` import if it is only used in this function. Remove the `get_section_content_schema` import from `pipeline.contracts` if it is only used here.

### 7b — Replace `check_component_ids_in_manifest()` in `deterministic_checks.py`

Find `check_component_ids_in_manifest()` and rename it, updating its body:

```python
def check_component_ids_in_lectio_contract(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    """
    Verify that every component slug planned in the blueprint is a known
    Lectio component (present in lectio-content-contract.json).

    Replaces check_component_ids_in_manifest() which used the old registry.
    """
    from pipeline.contracts import get_component_card
    from v3_execution.component_aliases import canonical_component_id

    issues: list[ReviewIssue] = []
    for sec in blueprint.sections:
        for comp in sec.components:
            cid = canonical_component_id(comp.component)
            if get_component_card(cid) is None:
                issues.append(
                    _issue(
                        severity="blocking",
                        category="unknown_component",
                        message=(
                            f"Component '{cid}' in blueprint section '{sec.section_id}' "
                            "is not present in lectio-content-contract.json. "
                            "Check component slugs and Lectio version."
                        ),
                        blueprint_ref=sec.section_id,
                        executor="assembler",
                        repair_target_id=sec.section_id,
                    )
                )
    return issues
```

Remove the now-unused import of `get_component_registry_entry` and `get_section_field_for_component` from `deterministic_checks.py` if they are only used in the replaced functions.

### 7c — Update `run_coherence_review()` in `reviewer.py`

Find `run_coherence_review()`. It currently accepts a `manifest: dict[str, Any]` parameter. Remove it:

```python
# Before:
async def run_coherence_review(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
    manifest: dict[str, Any],
    emit_event: ...,
    **kwargs,
) -> CoherenceReport:

# After:
async def run_coherence_review(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
    emit_event: ...,
    **kwargs,
) -> CoherenceReport:
```

Inside the function body, update the call to `check_component_ids_in_manifest()`:

```python
# Before:
issues += check_component_ids_in_manifest(blueprint, draft_pack, manifest)

# After:
issues += check_component_ids_in_lectio_contract(blueprint, draft_pack)
```

Update the call to `check_lectio_schema_validity()` — remove the `manifest` argument:

```python
# Before:
issues += check_lectio_schema_validity(draft_pack, manifest)

# After:
issues += check_lectio_schema_validity(draft_pack)
```

Update the import at the top of `reviewer.py`:

```python
# Before:
from v3_review.deterministic_checks import (
    check_component_ids_in_manifest,
    check_lectio_schema_validity,
    ...
)

# After:
from v3_review.deterministic_checks import (
    check_component_ids_in_lectio_contract,
    check_lectio_schema_validity,
    ...
)
```

### 7d — Update `route_repairs()` in `repair_router.py`

Find `route_repairs()`. Remove the `manifest` parameter from its signature and from all lambdas or check calls inside it that pass `m` or `manifest`:

```python
# Before:
def route_repairs(blueprint, draft_pack, manifest, ...) -> ...:
    ...
    RECHECK_MAP = {
        "schema_violation": lambda b, dp, m: check_lectio_schema_validity(dp, m),
        ...
    }

# After:
def route_repairs(blueprint, draft_pack, ...) -> ...:
    ...
    RECHECK_MAP = {
        "schema_violation": lambda b, dp: check_lectio_schema_validity(dp),
        ...
    }
```

### 7e — Update the `run_coherence_review()` call in `runner.py`

Find the call site in `backend/src/v3_execution/runtime/runner.py`:

```python
# Before:
await run_coherence_review(
    blueprint,
    draft_pack,
    manifest=_load_component_registry(),
    emit_event=emit_event,
    ...
)

# After:
await run_coherence_review(
    blueprint,
    draft_pack,
    emit_event=emit_event,
    ...
)
```

Remove any import of `_load_component_registry` from `runner.py` if it is only used for this call.

### 7f — Update the test stub in `test_v3_execution_core.py`

Find `stub_coherence_review` in `backend/tests/v3_execution/test_v3_execution_core.py`:

```python
# Before:
async def stub_coherence_review(
    blueprint,
    draft_pack,
    manifest,
    emit_event,
    **_kwargs: object,
) -> CoherenceReport:
    _ = blueprint
    _ = manifest
    _ = emit_event
    ...

# After:
async def stub_coherence_review(
    blueprint,
    draft_pack,
    emit_event,
    **_kwargs: object,
) -> CoherenceReport:
    _ = blueprint
    _ = emit_event
    ...
```

### Verification for Step 7

```bash
uv run pytest backend/tests/v3_review/ -v
uv run pytest backend/tests/v3_execution/test_v3_execution_core.py -v
```

Confirm:
- `manifest` parameter does not appear in `run_coherence_review()` signature
- `check_component_ids_in_manifest` does not appear anywhere in the codebase
- `_load_component_registry` is not imported in `runner.py`
- `Draft202012Validator` is not imported in `deterministic_checks.py` (unless used elsewhere)

---

## Step 8 — Update the sync test

**File:** `backend/tests/pipeline/test_lectio_contract_sync.py`

### Goal

Replace the stale assertions for `component-registry.json` and `component-field-map.json` with assertions for `lectio-content-contract.json` and add a structural validation test.

### Replace `test_synced_lectio_artifacts_exist`

```python
import json   # add at the top of the file if not already present

def test_synced_lectio_artifacts_exist() -> None:
    root = _repo_root()

    # Primary unified contract — replaces manifest.json, component-registry.json,
    # component-field-map.json, and per-template JSON files
    assert (root / "backend" / "contracts" / "lectio-content-contract.json").exists(), (
        "lectio-content-contract.json is missing. "
        "Run: uv run python tools/update_lectio_contracts.py"
    )

    # JSON Schema for SectionContent — drives Pydantic model generation
    assert (root / "backend" / "contracts" / "section-content-schema.json").exists(), (
        "section-content-schema.json is missing. "
        "Run: uv run python tools/update_lectio_contracts.py"
    )

    # Generated Pydantic adapter — must have AUTO-GENERATED header
    adapter_path = root / "backend" / "src" / "pipeline" / "types" / "section_content.py"
    assert adapter_path.exists(), "section_content.py Pydantic adapter is missing."
    adapter_text = adapter_path.read_text(encoding="utf-8")
    assert "AUTO-GENERATED" in "\n".join(adapter_text.splitlines()[:8]), (
        "section_content.py does not have an AUTO-GENERATED header. "
        "This file must be generated from section-content-schema.json, not hand-edited."
    )
```

### Add `test_lectio_content_contract_has_required_structure`

Add immediately after the replaced test:

```python
def test_lectio_content_contract_has_required_structure() -> None:
    root = _repo_root()
    contract_path = root / "backend" / "contracts" / "lectio-content-contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    # Top-level structure
    assert "component_cards" in contract, "missing component_cards"
    assert "planner_index" in contract, "missing planner_index"
    assert "templates" in contract, "missing templates"
    assert "formatting_policy" in contract, "missing formatting_policy"

    # Spot-check a known stable component card
    cards = contract["component_cards"]
    assert "explanation-block" in cards, "explanation-block missing from component_cards"
    card = cards["explanation-block"]
    assert card.get("section_field") == "explanation", (
        f"explanation-block section_field wrong: {card.get('section_field')}"
    )
    assert "field_contracts" in card, "explanation-block missing field_contracts"
    assert "body" in card["field_contracts"], "explanation-block field_contracts missing 'body'"

    # Phase map must have named phases (from Lectio 0.4.2 Proposal 1)
    phase_map = contract["planner_index"].get("phase_map", {})
    assert "1" in phase_map, "phase_map missing phase 1"
    assert "name" in phase_map["1"], "phase_map phase 1 missing 'name'"
    assert phase_map["1"]["name"] == "Orient", (
        f"Expected phase 1 name 'Orient', got '{phase_map['1'].get('name')}'"
    )
    assert "components" in phase_map["1"], "phase_map phase 1 missing 'components'"

    # guided-concept-path template must be present
    templates = contract.get("templates", {})
    assert "guided-concept-path" in templates, "guided-concept-path missing from templates"
    template = templates["guided-concept-path"]
    assert "available_components" in template, "guided-concept-path missing available_components"
```

Do not modify `test_sync_rejects_non_generated_adapter` — it is correct and must remain.

### Verification for Step 8

```bash
uv run pytest backend/tests/pipeline/test_lectio_contract_sync.py -v
```

All three tests must pass. Manually confirm: temporarily replace `lectio-content-contract.json` with `{}`, run the tests, confirm `test_lectio_content_contract_has_required_structure` fails. Restore the file.

---

## Full verification run

After all 8 steps are complete, run the full backend test suite:

```bash
uv run pytest backend/tests/ -v --tb=short 2>&1 | head -100
```

Then run the specific suites that cover the changed code:

```bash
uv run pytest backend/tests/pipeline/ -v
uv run pytest backend/tests/generation/ -v
uv run pytest backend/tests/v3_execution/ -v
uv run pytest backend/tests/v3_review/ -v
```

### Final codebase checks — grep for removed patterns

Run these to confirm no stale references remain in V3 code:

```bash
# Must return no results in V3 files
grep -r "manifest_components" backend/src/v3_execution/ backend/src/v3_review/ backend/src/generation/v3_studio/
grep -r "get_manifest()" backend/src/generation/v3_studio/
grep -r "_manifest_block" backend/src/generation/v3_studio/
grep -r "_load_guided_concept_contract" backend/src/generation/
grep -r "check_component_ids_in_manifest" backend/src/
grep -r "manifest_components=order.manifest_components" backend/src/
grep -r "_manifest_for_components" backend/src/

# Must return results (confirm new code is in place)
grep -r "get_component_card" backend/src/pipeline/contracts.py
grep -r "get_planner_index" backend/src/generation/v3_studio/prompts.py
grep -r "component_cards" backend/src/v3_execution/models.py
grep -r "LECTIO COMPONENT CONTRACTS" backend/src/v3_execution/prompts/section_writer.py
grep -r "validate_lectio_field_payload" backend/src/v3_execution/executors/section_writer.py
grep -r "check_component_ids_in_lectio_contract" backend/src/v3_review/
```

---

## What does NOT change

The following must remain completely unchanged. Do not touch them.

- `pipeline/contracts.py` functions `get_manifest()`, `get_component_registry_entry()`, `get_section_field_for_component()`, `get_component_generation_hint()`, `get_component_capacity()`, `build_section_generation_manifest()` — the pipeline (v1/v2) path uses these
- `_EXTERNAL_FIELDS` set in `contracts.py` — stays as consumer-side media exclusion decision
- `ProductionBlueprint` model — not in scope
- Writer output shape `{"fields": {...}}` — must not change
- `pipeline/prompts/content.py` and `pipeline/prompts/block_gen.py` — v2 path, untouched
- `SectionGenerationManifest` and `GenerationFieldContract` in `pipeline/types/` — v2 types, untouched
- Any file outside `backend/` — frontend is not in scope for this migration

---

## Execution order summary

| Step | File(s) | Depends on |
|---|---|---|
| 0 | `frontend/package.json`, lockfiles, `tools/update_lectio_contracts.py`, `backend/contracts/`, `section_content.py` | Nothing — do first |
| 1 | `backend/src/pipeline/contracts.py` | Step 0 |
| 2 | `backend/src/generation/v3_studio/prompts.py` + tests | Step 1 |
| 3 | `models.py`, `compile_orders.py`, `section_writer.py` (executor), `validation.py` | Step 1 |
| 4 | `backend/src/v3_execution/prompts/section_writer.py` | Step 3 |
| 5 | new `lectio_validation.py`, `section_writer.py` (executor) | Step 0 (needs section_content.py) |
| 6 | `backend/src/v3_execution/assembly/section_builder.py` | Step 5 |
| 7 | `reviewer.py`, `deterministic_checks.py`, `repair_router.py`, `runner.py`, test stub | Steps 5, 6 |
| 8 | `backend/tests/pipeline/test_lectio_contract_sync.py` | Steps 0–7 complete |

Steps 2 and 3 can run in parallel after Step 1. Steps 4 and 5 can run in parallel after Step 3. Step 6 requires Step 5. Step 7 requires Steps 5 and 6. Step 8 is last.
