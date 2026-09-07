# Lectio Pre-Migration Proposals

5 changes required before backend V3 manifest migration — target version **Lectio 0.4.1**

> **Gate:** Do not start backend migration until all 5 proposals are merged and `npm run export-contracts` passes cleanly.

---

## Proposal 1 — Add named phase registry and enrich `planner_index`

**Files:** `src/lib/lectio/registry/phases.ts` (new file) · `scripts/export-contracts.ts` · `src/lib/lectio/registry/manifest.ts`

### Goal

`planner_index.phase_map` currently exports `{ "1": ["section-header", ...] }` — numeric keys only. The architect LLM needs phase names to reason about pedagogical function. "Phase 1 — Orient" tells the architect what that phase is *for*. A bare `"1"` does not. Phase names must live in Lectio and flow into the contract automatically.

### Pre-conditions

- `src/lib/lectio/core/types.ts` declares `LectioPhase = 1 | 2 | 3 | 4 | 5 | 6 | 7`
- Every component `metadata.ts` already declares `phase: LectioPhase`
- `scripts/export-contracts.ts` already builds `planner_index`

### Step 1 — Create `src/lib/lectio/registry/phases.ts` (new file)

```typescript
/**
 * Canonical phase definitions for the Lectio component registry.
 * Phase numbers must match the LectioPhase type in core/types.ts.
 * These names flow into lectio-content-contract.json → planner_index.phase_map.
 */

export interface LectioPhaseDefinition {
  id: number;
  name: string;
  description: string;
}

export const LECTIO_PHASES: Record<number, LectioPhaseDefinition> = {
  1: { id: 1, name: 'Orient',     description: 'Set direction, context, purpose, or closure for the section' },
  2: { id: 2, name: 'Understand', description: 'Build conceptual understanding through language and definition' },
  3: { id: 3, name: 'Model',      description: 'Show reasoning or procedure in action with worked examples' },
  4: { id: 4, name: 'Practice',   description: 'Apply, retrieve, and check understanding through active tasks' },
  5: { id: 5, name: 'Alert',      description: 'Flag misconceptions, pitfalls, or cautions before they form' },
  6: { id: 6, name: 'Visual',     description: 'Carry meaning through image, diagram sequence, or comparison' },
  7: { id: 7, name: 'Simulate',   description: 'Interactive or exploratory mode for dynamic concept engagement' },
};
```

### Step 2 — Update `scripts/export-contracts.ts`

Add import at the top:

```typescript
import { LECTIO_PHASES } from '../src/lib/lectio/registry/phases';
```

Find the section that builds `planner_index`. Replace the current flat `phase_map` build with:

```typescript
const phaseMap: Record<string, { name: string; description: string; components: string[] }> = {};

for (const [phaseNumStr, phaseDef] of Object.entries(LECTIO_PHASES)) {
  const phaseNum = Number(phaseNumStr);
  const componentIds = lectioModulesList
    .filter(
      (m) =>
        m.metadata.phase === phaseNum &&
        m.metadata.sectionField !== null &&
        m.metadata.status !== 'planned'
    )
    .map((m) => m.metadata.id);

  if (componentIds.length === 0) continue;

  phaseMap[phaseNumStr] = {
    name: phaseDef.name,
    description: phaseDef.description,
    components: componentIds,
  };
}

const plannerIndex = {
  component_ids: lectioModulesList
    .filter((m) => m.metadata.sectionField !== null && m.metadata.status !== 'planned')
    .map((m) => m.metadata.id),
  phase_map: phaseMap,
};
```

### Step 3 — Update `src/lib/lectio/registry/manifest.ts`

Add import:

```typescript
import { LECTIO_PHASES } from './phases';
```

Replace any hardcoded phase name strings (`"Orient"`, `"Understand"`, etc.) inside `buildLectioManifest()` with `LECTIO_PHASES[phaseNumber].name`. Both files now share the same single source of truth.

### Expected output shape in `lectio-content-contract.json`

```json
"planner_index": {
  "component_ids": ["section-header", "hook-hero", "explanation-block", "..."],
  "phase_map": {
    "1": {
      "name": "Orient",
      "description": "Set direction, context, purpose, or closure for the section",
      "components": ["section-header", "hook-hero", "explanation-block", "prerequisite-strip", "what-next-bridge", "interview-anchor", "callout-block", "summary-block", "section-divider"]
    },
    "3": {
      "name": "Model",
      "description": "Show reasoning or procedure in action with worked examples",
      "components": ["worked-example-card", "process-steps"]
    }
  }
}
```

### Verification checklist

- [ ] `npm run export-contracts` completes without errors
- [ ] `planner_index.phase_map["1"]` has `name`, `description`, and `components` keys
- [ ] `phase_map["1"].name` equals `"Orient"`
- [ ] `phase_map["3"].components` contains `"worked-example-card"`
- [ ] `phase_map["6"].components` contains `"diagram-block"`
- [ ] `buildLectioManifest()` existing tests still pass
- [ ] No hardcoded phase name strings remain in `manifest.ts` or `export-contracts.ts`

### Do NOT

- Change any component `metadata.ts` files — phase numbers are already correctly set on all components
- Rename the `planner_index` key in the contract output — the backend reads this exact key name
- Put phase information in any file other than `phases.ts`

---

## Proposal 2 — Wire `content-contract.ts` through `module.ts` into the export

**Files:** Each component's `module.ts` · `scripts/export-contracts.ts`

### Goal

Each component has a `content-contract.ts` with `fieldContracts` (field-level format, description, constraints) and `componentConstraints`. These files exist but do not flow into the exported contract — `field_contracts` in the published cards was assembled from a separate location. After this change, every component card's `field_contracts` comes directly from that component's own source file.

**Do Proposal 5 first** so the TypeScript compiler validates format values the moment content contracts are wired through.

### Pre-conditions

- `src/lib/lectio/core/types.ts` has `LectioContentModule.contentContract?: LectioContentContract` (already present — do not change it)
- `src/lib/lectio/core/content-contract.ts` defines `LectioContentContract` interface (already present)
- `practice-stack/content-contract.ts` exists — use it as the reference implementation

### Step 1 — Wire each component's `module.ts`

For every component folder that contains a `content-contract.ts`, update `module.ts` with this exact pattern:

```typescript
// Add this import alongside the existing imports:
import { contentContract } from './content-contract';

// Add contentContract to the exported module object:
export const lectioModule = {
  schema: componentSchema,
  metadata,
  print,
  examples,
  contentContract,   // add this line
} satisfies LectioContentModule;
```

Apply to every component that has a `content-contract.ts`. Do not add this to components that do not have one — the field is optional on `LectioContentModule`.

### Step 2 — Read `module.contentContract` in `scripts/export-contracts.ts`

In the loop building each component card, replace whatever currently populates `field_contracts` with:

```typescript
const contentContract = mod.contentContract ?? null;

const card = {
  component_id: mod.metadata.id,
  section_field: mod.metadata.sectionField,
  role: mod.metadata.role,
  cognitive_job: mod.metadata.cognitiveJob,
  subjects: [...mod.metadata.subjects],
  capacity: { ...mod.metadata.capacity },
  capabilities: { ...mod.metadata.capabilities },
  status: mod.metadata.status,
  writer_excluded: mod.metadata.capabilities.isMedia,   // from Proposal 3
  field_contracts: contentContract?.fieldContracts ?? {},
  component_constraints: contentContract?.componentConstraints ?? [],
  examples: mod.examples.slice(0, 1),
  print_behavior: {
    breakBehavior: mod.print.breakBehavior,
    preferredWidth: mod.print.preferredWidth,
    fallback: mod.print.fallback,
  },
};
```

### Step 3 — Add warning for mapped components without a content contract

Immediately after building each card:

```typescript
if (mod.metadata.sectionField !== null && !mod.contentContract) {
  console.warn(
    `[Lectio] No content-contract.ts for mapped component "${mod.metadata.id}". ` +
    `field_contracts will be empty in the exported card. ` +
    `Add a content-contract.ts to this component folder.`
  );
}
```

This must be a warning only — not a hard error. Some components legitimately do not have a content contract yet.

### Verification checklist

- [ ] `npm run export-contracts` completes without errors
- [ ] `component_cards["explanation-block"].field_contracts` has `body`, `emphasis`, and `callouts` keys
- [ ] `component_cards["practice-stack"].field_contracts` has a key for `problems[].question`
- [ ] `component_cards["explanation-block"].component_constraints` is a non-empty array
- [ ] A component without a `content-contract.ts` produces `field_contracts: {}` and a console warning — not a build failure
- [ ] `npm run check` passes with no new TypeScript errors

### Do NOT

- Create new `content-contract.ts` files for components that do not have one — that is separate work, not in scope here
- Change the shape of `LectioContentContract` — use the existing interface as-is
- Modify the content of any existing `content-contract.ts` files — only wire them through `module.ts`
- Remove the `?` optional marker from `contentContract` on `LectioContentModule`

---

## Proposal 3 — Add `writer_excluded` flag derived from `capabilities.isMedia`

**Files:** `scripts/export-contracts.ts`

### Goal

The backend hardcodes a Python set `_EXTERNAL_FIELDS` listing which fields are generated by the media pipeline rather than the section writer LLM. Lectio already declares `capabilities.isMedia: true` on every media component. After this change, each exported card carries `writer_excluded: true/false` derived from `isMedia`. The backend reads this flag instead of maintaining its own list. When a new media component is added to Lectio, the backend gets the exclusion automatically without a manual update.

### Pre-conditions

- `LectioCapabilities.isMedia: boolean` is already declared and correctly set on all components — `diagram-block`, `diagram-series`, `diagram-compare`, `image-block`, `simulation-block`, `video-embed` all have `isMedia: true`
- `capabilities` is already included in exported component cards

### The complete change — one line in `scripts/export-contracts.ts`

In the card assembly loop, add `writer_excluded` derived from `isMedia`:

```typescript
const card = {
  // ... existing fields ...
  capabilities: { ...mod.metadata.capabilities },
  writer_excluded: mod.metadata.capabilities.isMedia,
  // ... rest of fields ...
};
```

### Expected values in the exported contract

```json
"component_cards": {
  "explanation-block":  { "writer_excluded": false },
  "practice-stack":     { "writer_excluded": false },
  "worked-example-card":{ "writer_excluded": false },
  "diagram-block":      { "writer_excluded": true  },
  "diagram-series":     { "writer_excluded": true  },
  "diagram-compare":    { "writer_excluded": true  },
  "simulation-block":   { "writer_excluded": true  },
  "image-block":        { "writer_excluded": true  },
  "video-embed":        { "writer_excluded": true  }
}
```

### Verification checklist

- [ ] `npm run export-contracts` completes without errors
- [ ] `component_cards["diagram-block"].writer_excluded` is `true`
- [ ] `component_cards["diagram-series"].writer_excluded` is `true`
- [ ] `component_cards["diagram-compare"].writer_excluded` is `true`
- [ ] `component_cards["simulation-block"].writer_excluded` is `true`
- [ ] `component_cards["image-block"].writer_excluded` is `true`
- [ ] `component_cards["video-embed"].writer_excluded` is `true`
- [ ] `component_cards["explanation-block"].writer_excluded` is `false`
- [ ] `component_cards["practice-stack"].writer_excluded` is `false`

### Do NOT

- Add a new field to `LectioCapabilities` or `LectioComponentPublicMetadata` — derive directly from the existing `isMedia` value at export time
- Create a top-level `excluded_components` list in the contract — the per-card flag is cleaner and self-documenting
- Change any component `metadata.ts` files — `isMedia` is already correctly set

---

## Proposal 4 — Fix the contract sync test to check the correct files

**Files:** `backend/tests/pipeline/test_lectio_contract_sync.py`

### Goal

The CI sync test currently asserts that `component-registry.json` and `component-field-map.json` exist in `backend/contracts/`. Per the Lectio docs, those files were replaced by `lectio-content-contract.json`. The test is asserting stale files, providing false confidence. It must be updated to assert the files the backend migration actually depends on.

### Pre-conditions

- `backend/contracts/lectio-content-contract.json` exists
- `backend/contracts/section-content-schema.json` exists
- `backend/src/pipeline/types/section_content.py` exists with `AUTO-GENERATED` header

### Replace `test_synced_lectio_artifacts_exist`

Add `import json` at the top of the file if not already present. Then replace the body of `test_synced_lectio_artifacts_exist`:

```python
def test_synced_lectio_artifacts_exist() -> None:
    root = _repo_root()

    # Primary unified contract — replaces manifest.json, component-registry.json,
    # component-field-map.json, and per-template JSON files
    assert (root / "backend" / "contracts" / "lectio-content-contract.json").exists(), (
        "lectio-content-contract.json is missing. "
        "Run: npm run export-contracts in the Lectio repo, "
        "then copy the output to backend/contracts/."
    )

    # JSON Schema for SectionContent — drives Pydantic model generation
    assert (root / "backend" / "contracts" / "section-content-schema.json").exists(), (
        "section-content-schema.json is missing. "
        "Run: npm run export-contracts in the Lectio repo."
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

### Add new structural validation test

Add this function immediately after `test_synced_lectio_artifacts_exist`:

```python
def test_lectio_content_contract_has_required_structure() -> None:
    root = _repo_root()
    contract_path = root / "backend" / "contracts" / "lectio-content-contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    assert "component_cards" in contract, "lectio-content-contract.json missing component_cards"
    assert "planner_index" in contract, "lectio-content-contract.json missing planner_index"
    assert "templates" in contract, "lectio-content-contract.json missing templates"
    assert "formatting_policy" in contract, "lectio-content-contract.json missing formatting_policy"

    # Spot-check explanation-block card
    cards = contract["component_cards"]
    assert "explanation-block" in cards, "explanation-block missing from component_cards"
    card = cards["explanation-block"]
    assert card.get("section_field") == "explanation", "explanation-block has wrong section_field"
    assert "field_contracts" in card, "explanation-block card missing field_contracts"
    assert "writer_excluded" in card, "explanation-block card missing writer_excluded"

    # Spot-check planner_index phase_map has named phases (requires Proposal 1)
    phase_map = contract["planner_index"].get("phase_map", {})
    assert "1" in phase_map, "phase_map missing phase 1"
    assert "name" in phase_map["1"], "phase_map phase 1 missing name field"
    assert phase_map["1"]["name"] == "Orient", (
        f"Expected phase 1 name 'Orient', got '{phase_map['1'].get('name')}'"
    )
    assert "components" in phase_map["1"], "phase_map phase 1 missing components list"
```

### Verification checklist

- [ ] `pytest backend/tests/pipeline/test_lectio_contract_sync.py -v` passes with all tests green
- [ ] `test_synced_lectio_artifacts_exist` no longer references `component-registry.json` or `component-field-map.json`
- [ ] `test_lectio_content_contract_has_required_structure` passes with the current contract
- [ ] Manual check: temporarily replace the contract file with `{}`, confirm new test fails, then restore
- [ ] `test_sync_rejects_non_generated_adapter` is unchanged and still passes

### Do NOT

- Delete `component-registry.json` or `component-field-map.json` from `backend/contracts/` — that is backend cleanup work, not in scope here
- Modify `test_sync_rejects_non_generated_adapter`

---

## Proposal 5 — Add `FieldFormat` union type to `LectioContentContract`

**Files:** `src/lib/lectio/core/content-contract.ts`

### Goal

The `format` field in `fieldContracts` is currently typed as `string`. The contract's `formatting_policy` defines a controlled vocabulary. If a component author writes an unrecognised value like `"rich_text"`, it exports silently and the backend section writer receives an unknown format string, breaking the LLM instruction for that field. After this change, the TypeScript compiler enforces the vocabulary at authoring time.

**Do this proposal first** — before Proposal 2 wires the content contracts through — so any invalid `format` values in existing files are caught immediately.

### Pre-conditions

- `src/lib/lectio/core/content-contract.ts` defines `LectioContentContract` and the per-field shape
- At least `practice-stack/content-contract.ts` exists as a reference

### Add `FieldFormat` and tighten the `format` field

```typescript
/**
 * Controlled vocabulary for field format types.
 * Values must match the formatting_policy keys in lectio-content-contract.json.
 * Adding a new format type requires updating formatting_policy in the contract first.
 */
export type FieldFormat =
  | 'plain_text'
  | 'plain_text_short'
  | 'inline_markdown'
  | 'block_markdown'
  | 'latex_raw'
  | 'plain_phrase_list'
  | 'enum'
  | 'structured_array'
  | 'structured_object'
  | 'positioned_callouts';
```

Find the interface or type in `content-contract.ts` that declares the per-field shape and update `format` from `string` to `FieldFormat`:

```typescript
// Before:
export interface LectioFieldContract {
  format: string;
  description: string;
  renderBehavior?: string;
  constraints?: string[];
}

// After:
export interface LectioFieldContract {
  format: FieldFormat;   // tightened from string
  description: string;
  renderBehavior?: string;
  constraints?: string[];
}
```

If the field contract shape is defined differently in the actual file (inline type alias, etc.), apply the same change to whatever currently holds `format: string`. The goal is `format: FieldFormat` — do not restructure anything else.

### Verification checklist

- [ ] `npm run check` passes with no new TypeScript errors
- [ ] Deliberate failure test: temporarily change `format: 'block_markdown'` to `format: 'bad_format'` in any existing `content-contract.ts` — TypeScript must produce a type error. Revert after confirming.
- [ ] All existing `content-contract.ts` files compile without errors after the type is tightened
- [ ] `npm run export-contracts` still runs successfully

### Do NOT

- Add `FieldFormat` to `LectioComponentPublicMetadata` or `LectioContentModule` — it belongs only on the field contract shape
- Change the string values — they must exactly match the current `formatting_policy` keys in the exported contract
- Make `renderBehavior` or `constraints` required — they are legitimately absent on some field entries

---

## Execution order

| Order | Proposal | Dependency |
|---|---|---|
| 1st | **Proposal 5** — FieldFormat type | None. Do first so format errors are caught the moment Proposal 2 wires contracts through. |
| 1st | **Proposal 1** — Phase registry | None. Can run in parallel with Proposal 5. |
| Any | **Proposal 3** — `writer_excluded` flag | None. No dependencies on 1 or 5. |
| After 5 | **Proposal 2** — Wire content-contract | After Proposal 5 so type enforcement is active. |
| Last | **Proposal 4** — Fix sync test | After Proposals 1–3 are merged and the contract has been regenerated with all new fields. |

### Final gate before starting backend migration

```bash
# In Lectio repo
npm run export-contracts

# Copy contracts to backend
cp contracts/lectio-content-contract.json ../backend/contracts/
cp contracts/section-content-schema.json  ../backend/contracts/

# In backend repo
pytest backend/tests/pipeline/test_lectio_contract_sync.py -v
```

All tests must pass before proceeding to backend V3 migration work.
