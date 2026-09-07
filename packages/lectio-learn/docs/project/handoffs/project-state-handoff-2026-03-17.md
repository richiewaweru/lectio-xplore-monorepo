# Project State Handoff

## Current Product State

- The Svelte repo now ships the registry-driven template system as the public template experience.
- The public routes are `/components`, `/templates`, and `/templates/[templateId]`.
- The public app shell includes a shared desktop-only sticky sidebar for components and templates, driven directly from the live registries.
- The template detail page uses a left-side persistent contract drawer on `md+` and a temporary left-side sheet on mobile, with desktop preference remembered in `localStorage`.

## Library Surface

- Public component exports: 22 teaching components
- New published components in this phase:
  - `ComparisonGrid`
  - `TimelineBlock`
- Extended components in this phase:
  - `PracticeStack`
  - `GlossaryRail`
  - `ProcessSteps`
  - `DiagramBlock`
  - `DiagramCompare`
  - `GlossaryInline`

## Template System

- Starter templates shipped through `src/lib/template-registry.ts`: 10
- Shared infrastructure:
  - `src/lib/template-types.ts`
  - `src/lib/template-validation.ts`
  - `src/lib/template-registry.ts`
  - `src/lib/presets/base-presets.ts`
- Shared template chrome:
  - `src/lib/templates/TemplatesGallery.svelte`
  - `src/lib/templates/TemplateDetailView.svelte`
  - `src/lib/templates/TemplateContractDrawer.svelte`
  - `src/lib/templates/TemplateContractPanel.svelte`

## Documentation Updated

- `README.md`
- `docs/reference/component-guide.md`
- `docs/project/runs/phase7-contract-drawer-update.md`
- `docs/project/runs/phase8-source-of-truth-sync.md`
- `docs/project/runs/phase9-sidebar-navigation-alignment.md`

Historical planning docs were retained, but they now carry a status note directing readers back to the live implementation.

## Validation Status

- Validated on March 17, 2026 with:
  - `npm run check`
  - `npm run test`
  - `npm run build`
- Final commit and push details should be read from `docs/project/runs/phase8-source-of-truth-sync.md`.

## Known Notes

- `GuidedConceptPath.svelte` and `EnrichedLearningPath.svelte` still exist as internal reference surfaces.
- The Svelte build still emits the known large-chunk warning.
