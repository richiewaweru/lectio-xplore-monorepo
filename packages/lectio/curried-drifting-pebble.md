# Plan: Lectio Print Fallback Implementation

## Context
The proposal `Lectio_Print_Implementation_Proposal.md` defines print rendering for all 15 interactive components in the Lectio library. Currently, `printFallback` exists only as registry metadata — no `@media print` CSS or context-driven rendering is implemented. This plan activates those fallbacks following the proposal's architecture while adapting it for **Svelte 5 runes** (the proposal was written in Svelte 4 syntax) and the actual type shapes in `src/lib/types.ts`.

---

## Key Adaptations from Proposal

| Proposal (Svelte 4) | Actual (Svelte 5) |
|---|---|
| `export let content` | `let { content } = $props()` |
| Named slots `<slot name="left" />` | Snippets `{@render left()}` |
| `const printMode = usePrintMode()` | `const getPrintMode = usePrintMode(); const printMode = $derived(getPrintMode())` |
| `$effect(() => { providePrintMode(x) })` | `providePrintMode(() => printPreviewMode)` at init time |
| `segment.type === 'text'` / `segment.content` | `segment.is_blank` / `segment.text` (actual type) |
| `step.reasoning` | `step.note` (actual WorkedStep type) |

---

## Files to Create

### `src/lib/utils/printContext.ts`
Reactive context using getter functions (Svelte 5 safe):
```typescript
import { getContext, setContext } from 'svelte';
const KEY = Symbol('printMode');
export function providePrintMode(getter: () => boolean): void { setContext(KEY, getter); }
export function usePrintMode(): () => boolean { return getContext<() => boolean>(KEY) ?? (() => false); }
```

### `src/lib/print/` — 6 utility components
- `RuledLines.svelte` — lines prop, draws bordered divs
- `Checkboxes.svelte` — count prop, draws bordered squares
- `ExpandedSteps.svelte` — `steps: WorkedStep[]`, uses `step.note` (not `step.reasoning`)
- `SideBySide.svelte` — Svelte 5 **snippets** (`left` + `right`), not slots
- `VerticalList.svelte` — `events: TimelineEvent[]`
- `AnswerMarker.svelte` — `isCorrect`, `showAnswers`
- `index.ts` — barrel export

All utility components use Svelte 5 `$props()` syntax and scoped CSS with `@media print` rules.

---

## Files to Modify

### High Priority (interactive → static swap needed)

| File | Change |
|---|---|
| `SimulationBlock.svelte` | Wrap existing markup in `{#if !printMode}`. Add `{:else}` branch: hide/static-diagram/static-midstate based on `content.spec.print_translation` |
| `QuizCheck.svelte` | Wrap existing in `{#if !printMode}`. Add print branch: question + lettered options + AnswerMarker |
| `PracticeStack.svelte` | Wrap existing in `{#if !printMode}`. Add print branch: expanded problems + RuledLines per `writein_lines` |
| `FillInTheBlank.svelte` | Wrap existing in `{#if !printMode}`. Add print branch: `segment.is_blank ? '___' : segment.text` + word bank |
| `WorkedExampleCard.svelte` | Wrap existing in `{#if !printMode}`. Add print branch: ExpandedSteps (uses `step.note` not `step.reasoning`) |
| `DiagramCompare.svelte` | Wrap existing in `{#if !printMode}`. Add print branch: SideBySide snippet with SVGs |
| `TimelineBlock.svelte` | Wrap existing in `{#if !printMode}`. Add print branch: VerticalList + closing_takeaway |

### Medium Priority

| File | Change |
|---|---|
| `ProcessSteps.svelte` | Wrap existing in `{#if !printMode}`. Print: all steps + Checkboxes |
| `ReflectionPrompt.svelte` | Already has `.print-only` lines. Add `usePrintMode` context: show `<div class="print-only">` always when printMode is true (currently CSS-only, not context-driven) |
| `StudentTextbox.svelte` | Wrap existing in `{#if !printMode}`. Print: RuledLines with label |
| `ShortAnswerQuestion.svelte` | Wrap existing in `{#if !printMode}`. Print: question + marks + RuledLines |

### Low Priority (CSS-only, no interactive swap needed)

| File | Change |
|---|---|
| `DiagramSeries.svelte` | Add `@media print` block: show all diagrams in sequence, hide nav controls |
| `DiagramBlock.svelte` | Add `@media print`: hide callout popovers/zoom button, centre SVG at 80% width |
| `PitfallAlert.svelte` | Add `@media print`: `page-break-inside: avoid`, amber left border |
| `ComparisonGrid.svelte` | Add `@media print`: remove horizontal scroll, render full table |

### Infrastructure

| File | Change |
|---|---|
| `src/lib/index.ts` | Add `export * from './print'; export { providePrintMode, usePrintMode } from './utils/printContext';` |
| `package.json` | Add `"./print"` export pointing to `dist/print/index.js` |
| `src/routes/components/+page.svelte` | Add `let printPreviewMode = $state(false); providePrintMode(() => printPreviewMode);` + toggle checkbox in controls area |

---

## Critical Files
- `src/lib/types.ts` — verify `WorkedStep` fields (`note`, not `reasoning`), `FillInBlankSegment` (`is_blank`/`text`), `ProcessStepItem` (`action`/`detail`/`warning`)
- `src/lib/components/lectio/*.svelte` — all 15 listed above
- `src/lib/index.ts`
- `package.json`

---

## Pattern for Each High/Medium Priority Component

```svelte
<script lang="ts">
  import { usePrintMode } from '$lib/utils/printContext';
  // ... existing imports + print utility imports

  let { content } = $props();  // existing
  const getPrintMode = usePrintMode();
  const printMode = $derived(getPrintMode());
  // ... existing state/derived
</script>

{#if printMode}
  <!-- Print fallback markup -->
{:else}
  <!-- Existing interactive markup (unchanged) -->
{/if}

<style>
  /* existing styles unchanged */
  @media print {
    /* new print rules */
    .component-print { page-break-inside: avoid; }
  }
</style>
```

---

## Testing & Verification

1. **Type-check**: `npm run check` — must pass with zero errors
2. **Build**: `npm run build` — dist must include `print/` subdirectory
3. **Showcase preview**: Run `npm run dev`, toggle "Print Preview Mode" checkbox in component showcase — each of the 15 components should render its static print version
4. **Browser print dialog**: With print preview mode ON, use Ctrl+P to verify `@media print` rules apply correctly
5. **Registry test**: `tests/print/registry-compliance.test.ts` — verify all 15 `printFallback` registry values align with implementations

## Commit Strategy
One commit per logical group:
1. `feat(print): add printContext utility and print utility components`
2. `feat(print): add print fallbacks to high-priority interactive components`
3. `feat(print): add print fallbacks to medium-priority components`
4. `feat(print): add print CSS to low-priority components`
5. `feat(print): wire print preview toggle in component showcase`
6. `feat(print): update package exports and add registry compliance tests`
