# Lectio Library Guide

This guide documents the current public library surface after the packaging, runtime-surface, and template-expansion work shipped on March 19, 2026.

## What Ships Now

- Framework: SvelteKit + Svelte 5 runes + TypeScript + Tailwind CSS v4
- Public package entrypoint: `src/lib/index.ts`
- Public stylesheet entrypoint: `src/lib/theme.css` via `import 'lectio/theme.css'`
- Public teaching component count: 30
- Public template count: 13 registry-backed templates in `src/lib/templates/registry.ts`
- Public runtime surfaces:
  - `TemplatePreviewSurface`
  - `TemplateRuntimeSurface`
  - `LectioThemeSurface`
  - `ResolvedTemplatePreviewSurface`
- Showcase routes:
  - `/components`
  - `/templates`
  - `/templates/[templateId]`

## Public Components

### Foundation

- `SectionHeader`
- `HookHero`
- `ExplanationBlock`
- `PrerequisiteStrip`
- `WhatNextBridge`
- `InterviewAnchor`
- `CalloutBlock`
- `SummaryBlock`
- `SectionDivider`

### Definition and Knowledge

- `DefinitionCard`
- `DefinitionFamily`
- `GlossaryRail`
- `GlossaryInline`
- `InsightStrip`
- `KeyFact`
- `ComparisonGrid`

### Examples and Process

- `WorkedExampleCard`
- `ProcessSteps`

### Assessment and Practice

- `PracticeStack`
- `QuizCheck`
- `ReflectionPrompt`
- `StudentTextbox`
- `ShortAnswerQuestion`
- `FillInTheBlank`

### Alerts

- `PitfallAlert`

### Visual and Sequence

- `DiagramBlock`
- `DiagramCompare`
- `DiagramSeries`
- `TimelineBlock`

### Interactive

- `SimulationBlock`

## Public Template System

The public template system is registry-driven.

- Registry: `src/lib/templates/registry.ts`
- Shared contracts and selectors: `src/lib/templates/types.ts`
- Validation: `src/lib/templates/validation.ts`
- Runtime helpers: `src/lib/templates/resolver.ts`
- Consumer surfaces: `src/lib/templates/TemplatePreviewSurface.svelte` and `src/lib/templates/TemplateRuntimeSurface.svelte`
- Gallery shell: `src/lib/templates/TemplatesGallery.svelte`
- Detail shell: `src/lib/templates/TemplateDetailView.svelte`

The 13 shipped templates are:

- Guided Concept Path
- Visual Led
- Compare and Apply
- Low Load
- Concept Compact
- Formal Track
- Diagram Led
- Classification
- Timeline
- Procedure
- Interactive Lab
- Guided Discovery
- Open Canvas

## Rendering From A Consumer App

Build the library and import the shared theme once:

```bash
npm run package
```

```css
@import 'tailwindcss';
@import 'lectio/theme.css';
```

Render a seeded preview or a real section through the public runtime wrappers:

```svelte
<script lang="ts">
  import { TemplatePreviewSurface, TemplateRuntimeSurface } from 'lectio';
  import type { SectionContent } from 'lectio';

  let { section }: { section: SectionContent } = $props();
</script>

<TemplatePreviewSurface templateId="interactive-lab" presetId="blue-classroom" />
<TemplateRuntimeSurface
  templateId="interactive-lab"
  presetId="blue-classroom"
  {section}
/>
```

Use the higher-level surfaces unless you are composing your own preview chrome. `LectioThemeSurface` and `ResolvedTemplatePreviewSurface` are exported for advanced consumers only.

## Lesson document interchange

For cross-app lesson files (generator export → builder import), Lectio exposes `LessonDocument`, `fromSectionContents`, `toSectionContents`, `validateDocument`, `getEmptyContent`, `getEditSchema`, and `getFieldComponentMap()`. Registry entries include `teacherLabel` and `teacherDescription` for palette UI.

Full reference: [lesson-document.md](lesson-document.md).

## Contract Snapshots

External pipelines should read contract artifacts from `contracts/`, not import Typescript from `src/`.

```bash
npm run export-contracts
npm run export-contracts -- --out ../some-other-project/contracts
```

The export now writes:

- `section-content-schema.json`
- `lectio-content-contract.json`
- `generated/python/section_content.py`

Legacy fragmented JSON exports were retired. Read `lectio-content-contract.json` as the primary contract surface.
`diagram-block` contracts keep `callouts` as `positioned_callouts` and treat coordinates as `x/y` percentages (0-100) for image overlay rendering.

Whenever template contracts, presets, or registry metadata change, rerun both `npm run package` and `npm run export-contracts` before publishing.

## Print Mode

Lectio provides a context-driven print system. Consuming applications call `providePrintMode` once at the page root; all 15 interactive components automatically switch to their static print fallbacks.

```svelte
<script lang="ts">
  import { providePrintMode } from 'lectio';

  // Your app decides when print mode is active
  const isPrint = $derived($page.url.searchParams.get('print') === 'true');
  providePrintMode(() => isPrint);
</script>
```

Six shared print utility components are exported: `RuledLines`, `Checkboxes`, `ExpandedSteps`, `SideBySide`, `VerticalList`, `AnswerMarker`.

The `/components` showcase has a **Print preview mode** toggle in the page header — use this to inspect all 15 fallbacks without opening a browser print dialog.

Full reference (consumer quickstart, per-component tables, contributor guide): [`docs/reference/print-mode.md`](print-mode.md).

## Copy Or Fork Checklist

If you want to reuse a component or template outside this repo, copy these pieces together:

1. The **component module** from `src/lib/lectio/components/<id>/` (schema, metadata, print, examples, `content-contract.ts`, `module.ts`) and the `.svelte` renderer from `src/lib/components/lectio/` (or the full template from `src/lib/templates/`).
2. Supporting UI primitives from `src/lib/components/ui/`.
3. `src/lib/schema/types.ts` for the content contracts and `src/lib/lectio/schemas/content-zod.ts` for Zod mirrors.
4. `src/lib/lectio/registry/` and `src/lib/templates/registry.ts` if you want showcase and template metadata.
5. `src/lib/schema/validate.ts` and `src/lib/templates/validation.ts` if you want the same validation behavior.
6. `src/lib/theme.css` for shared tokens, utilities, animations, and preset styling.
7. `src/lib/utils.ts` for class merging helpers.

## Important Current Notes

- **Print mode** shipped in this release. 15 interactive components have static print fallbacks driven by `providePrintMode` (Svelte context). Six print utility components (`RuledLines`, `Checkboxes`, `ExpandedSteps`, `SideBySide`, `VerticalList`, `AnswerMarker`) are exported from the main entry.
- **7 new stable components** shipped in the 2026-03-27 harmonisation: `CalloutBlock`, `SummaryBlock`, `SectionDivider`, `KeyFact`, `StudentTextbox`, `ShortAnswerQuestion`, `FillInTheBlank`. Each has a corresponding `SectionContent` field and registry entry.
- **TemplateContract no longer uses** `lessonFlow`, `requiredComponents`, or `optionalComponents`. The current shape uses `always_present` (required), `available_components` (optional), `component_budget` (lesson-level caps), `max_per_section` (per-section caps), `signal_affinity`, and `section_role_defaults`.
- **7 templates were renamed** for clarity: figure-first→visual-led, focus-flow→low-load, guided-concept-compact→concept-compact, diagram-led-lesson→diagram-led, distinction-grid→classification, process-trainer→procedure, timeline-narrative→timeline.
- `SimulationBlock` is part of the public library and supports iframe-backed `html_content`, fallback diagrams, and an expanded modal view.
- `TemplateDetailView` renders previews through `TemplatePreviewSurface`, so the showcase uses the same public preview path as consumers.
- Legacy internal templates such as `GuidedConceptPath.svelte` and `EnrichedLearningPath.svelte` still exist for showcase and regression coverage, but the registry plus public surfaces are the source of truth for consumers.

