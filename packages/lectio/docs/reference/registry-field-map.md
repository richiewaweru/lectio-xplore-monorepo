# Registry-Driven Field Map

The component registry is the single source of truth for the mapping between Lectio components and their `SectionContent` fields. This document explains how the system works, how to extend it, and how pipeline consumers should interact with it after the March 19, 2026 packaging and contract-export updates.

## The Problem This Solves

Previously, the mapping from component IDs (for example `"practice-stack"`) to `SectionContent` fields (for example `"practice"`) was hardcoded in `template-validation.ts` as a lookup table. That created three problems:

1. Duplication: the registry already knew which components existed, but a separate map had to be maintained in sync.
2. Fragility: adding a new component required updating both the registry and the map.
3. Pipeline leakage: downstream tools would need their own copy of the same map, creating another source of truth.

## How It Works Now

### `sectionField` on `ComponentMeta`

Every component in the registry declares a `sectionField` property:

```typescript
// src/lib/schema/registry.ts

export interface ComponentMeta {
  sectionField: keyof SectionContent | null;
  teacherLabel: string;
  teacherDescription: string;
}
```

- Most components set this to the `SectionContent` key they read from.
- Components used inline without a dedicated block field set this to `null`. Right now that is `GlossaryInline`.

### `getComponentFieldMap()`

A helper derives the component-to-field map from the registry at runtime:

```typescript
import { getComponentFieldMap } from '$lib/registry';

const map = getComponentFieldMap();
// => { "section-header": "header", "hook-hero": "hook", ... }
```

- Components with `sectionField: null` are excluded.
- This helper is used by both `template-validation.ts` and `scripts/export-contracts.ts`.

### `getFieldComponentMap()` (lesson documents)

The inverse mapping (field name → component id) is exported from the package for lesson interchange and builder code:

```typescript
import { getFieldComponentMap } from 'lectio';

const reverse = getFieldComponentMap();
// => { header: "section-header", hook: "hook-hero", ... }
```

See [lesson-document.md](lesson-document.md) for `fromSectionContents` / `toSectionContents`.

## How To Add A New Component

### First-class module (current default)

Each generation-facing block is authored as a small module folder under `src/lib/lectio/components/<component-id>/` and collected in `src/lib/lectio/registry/components.ts`:

| File | Role |
| --- | --- |
| `schema.ts` | Zod schema for this block’s SectionContent slice |
| `metadata.ts` | Public metadata (`id`, `sectionField`, planner fields) |
| `print.ts` | Print/layout hints for this block |
| `examples.ts` | Validated example payloads |
| `content-contract.ts` | Field-level render/format behavior for consumers |
| `module.ts` | Bundles the above into `lectioModule` |
| `Component.svelte` | Optional; re-exports the runtime `.svelte` from `src/lib/components/lectio/` |

Then:

1. Add or extend the `SectionContent` field in `src/lib/schema/types.ts` and wire Zod in `src/lib/lectio/schemas/content-zod.ts` if needed.
2. Register the module in `src/lib/lectio/registry/components.ts`.
3. Ensure the runtime component exists under `src/lib/components/lectio/` and is wired from `Component.svelte` if used.
4. Run `pnpm run export-contracts` to refresh `contracts/lectio-content-contract.json` and related outputs.

### Legacy note

Older docs described registering directly in `src/lib/schema/registry.ts`. New components should use the module pipeline above; `componentRegistry` is built from those modules for backwards compatibility.

## For Pipeline Consumers

The pipeline should never import from `src/`. Instead, it should read exported contracts from `contracts/`.

### Generating Contracts

```bash
npm run export-contracts
npm run export-contracts -- --out ../some-other-project/contracts
LECTIO_CONTRACTS_DIR=../some-other-project/contracts npm run export-contracts
```

This produces the canonical contract artifacts:

| File | Contents |
|---|---|
| `section-content-schema.json` | Canonical JSON schema for `SectionContent` |
| `lectio-content-contract.json` | Unified consumer contract: templates, planner index, component cards, field contracts, examples, and print behavior |
| `generated/python/section_content.py` | Official generated Pydantic v2 adapter |

### Using The Unified Contract

`lectio-content-contract.json` centralizes all generation-facing metadata:

```json
{
  "component_cards": {
    "practice-stack": {
      "section_field": "practice",
      "field_contracts": {},
      "schema_summary": {}
    }
  },
  "templates": {
    "guided-concept-path": {
      "available_components": ["practice-stack", "quiz-check"]
    }
  }
}
```

Use `component_cards[component_id]` for per-component details (`section_field`, schema fragment, examples, print behavior), and `templates[template_id]` for template constraints.

## Architecture Diagram

```text
src/lib/lectio/components/*         (component-owned schema/metadata/print/examples/contentContract)
        |
        '--> scripts/export-contracts.ts       (exports to JSON, supports --out)
                  |
                  '--> contracts/              (pipeline reads these)
                         |-- section-content-schema.json
                         '-- lectio-content-contract.json
```

## Key Files

| File | Role |
|---|---|
| `src/lib/schema/registry.ts` | Component registry with `sectionField`, teacher-facing fields, and `getComponentFieldMap()` |
| `src/lib/teacher/teacher-facing.ts` | Strings merged into each registry entry |
| `src/lib/teacher/document.ts` | `LessonDocument` conversion and validation |
| `src/lib/templates/validation.ts` | Template validation that derives the field map from the registry |
| `scripts/export-contracts.ts` | Exports contracts to `contracts/` |
| `src/lib/presets/base-presets.ts` | Source of truth for preset metadata exported to JSON |
| `src/lib/schema/types.ts` | `SectionContent` interface |
| `src/test/lectio.test.ts` | Tests for field map correctness |
| `src/test/runtime-surface.test.ts` | Tests for public preview and runtime surfaces |

