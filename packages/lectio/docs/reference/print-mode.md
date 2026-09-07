# Print Mode

Lectio components know **how** to render for print. The consuming application decides **when** print mode is active.

## How It Works

Components read print mode from [Svelte context](https://svelte.dev/docs/svelte/context). The consuming app calls `providePrintMode` once at the root of the component tree; every Lectio component automatically switches to its static print fallback.

```
App root
 └── providePrintMode(() => isPrint)   ← you set this once
      └── <SimulationBlock />           ← renders static fallback
      └── <QuizCheck />                 ← renders lettered options
      └── <PracticeStack />             ← renders write-in lines
      └── ...                           ← all 15 components respond
```

## Quick Start (Consumer)

### 1. Import the context helper

```ts
import { providePrintMode } from 'lectio';
```

### 2. Wire it up in your layout or page root

```svelte
<script lang="ts">
  import { providePrintMode } from 'lectio';
  import { page } from '$app/stores';

  // Read a query param your PDF pipeline sets
  const isPrint = $derived($page.url.searchParams.get('print') === 'true');

  // Pass a getter — the getter is called reactively
  providePrintMode(() => isPrint);
</script>

<!-- All Lectio components below now auto-switch when isPrint is true -->
```

That's it. No prop drilling. No wrapper components.

### Alternative: reactive state toggle (e.g. for a preview toggle)

```svelte
<script lang="ts">
  import { providePrintMode } from 'lectio';

  let printPreview = $state(false);
  providePrintMode(() => printPreview);
</script>

<label>
  <input type="checkbox" bind:checked={printPreview} />
  Print preview
</label>
```

## Which Components Respond

### High priority — interactive → static swap

| Component | Print fallback |
|---|---|
| `SimulationBlock` | Static diagram (or goal description if no fallback) |
| `QuizCheck` | Lettered options, correct answer marked with ✓ |
| `PracticeStack` | All problems expanded + ruled write-in lines |
| `FillInTheBlank` | Passage with `________________` blanks + word bank box |
| `WorkedExampleCard` | All steps expanded with labels and notes |
| `DiagramCompare` | Both diagrams side-by-side |
| `TimelineBlock` | Vertical event list with year + summary |

### Medium priority — write-in areas

| Component | Print fallback |
|---|---|
| `ProcessSteps` | All steps visible with checkbox squares |
| `ReflectionPrompt` | Prompt + ruled write-in lines |
| `StudentTextbox` | Ruled write-in lines |
| `ShortAnswerQuestion` | Question + mark allocation + ruled lines |

### Low priority — CSS-only layout adjustments

| Component | What changes in print |
|---|---|
| `DiagramSeries` | All diagrams shown sequentially (interactive: only current step) |
| `DiagramBlock` | Callout popover buttons hidden, SVG centred at 80% width |
| `PitfallAlert` | `page-break-inside: avoid` + amber left border |
| `ComparisonGrid` | Horizontal scroll removed, full table rendered |

Components not in the above lists (e.g. `ExplanationBlock`, `DefinitionCard`) render the same in print and screen — they are already static.

## Print Utility Components

Six reusable print building blocks are exported from `lectio`. They are designed to be composed inside your own custom print layouts:

```ts
import {
  RuledLines,    // Horizontal write-in lines
  Checkboxes,    // Bordered checkbox squares (for process steps)
  ExpandedSteps, // All WorkedStep items expanded
  SideBySide,    // Two-column grid with labels
  VerticalList,  // Timeline events as a vertical list
  AnswerMarker,  // ✓ marker for correct quiz answers
} from 'lectio';
```

### `RuledLines`

```svelte
<RuledLines lines={4} lineHeight="1.8rem" label="Your answer:" />
```

| Prop | Type | Default | Description |
|---|---|---|---|
| `lines` | `number` | `4` | Number of ruled lines |
| `lineHeight` | `string` | `'1.8rem'` | Height of each line |
| `label` | `string \| undefined` | — | Optional label above the lines |

### `Checkboxes`

```svelte
<Checkboxes count={5} size="1rem" />
```

| Prop | Type | Default | Description |
|---|---|---|---|
| `count` | `number` | — | Number of checkbox squares |
| `size` | `string` | `'1rem'` | Width and height of each square |

### `ExpandedSteps`

```svelte
<ExpandedSteps steps={content.steps} title="Worked solution" />
```

| Prop | Type | Default | Description |
|---|---|---|---|
| `steps` | `WorkedStep[]` | — | Steps from `WorkedExampleContent` |
| `title` | `string \| undefined` | — | Optional heading above the steps |

### `SideBySide`

Uses Svelte 5 snippets for the two panels:

```svelte
<SideBySide leftLabel="Before" rightLabel="After">
  {#snippet left()}
    <!-- left content -->
  {/snippet}
  {#snippet right()}
    <!-- right content -->
  {/snippet}
</SideBySide>
```

| Prop | Type | Description |
|---|---|---|
| `leftLabel` | `string` | Label above the left panel |
| `rightLabel` | `string` | Label above the right panel |

### `VerticalList`

```svelte
<VerticalList events={content.events} title="Key Events" />
```

| Prop | Type | Default | Description |
|---|---|---|---|
| `events` | `TimelineEvent[]` | — | Events from `TimelineContent` |
| `title` | `string \| undefined` | — | Optional heading |

### `AnswerMarker`

```svelte
<AnswerMarker isCorrect={option.correct} showAnswers={true} />
```

| Prop | Type | Default | Description |
|---|---|---|---|
| `isCorrect` | `boolean` | — | Whether this option is the correct answer |
| `showAnswers` | `boolean` | `true` | Set to `false` to hide answer keys (student copy) |

---

## Controlling Answer Keys

`QuizCheck` and `PracticeStack` accept a `showAnswersInPrint` prop (default: `true`). Set it to `false` for student copies where answers should not be visible:

```svelte
<!-- Teacher copy — shows correct answers -->
<QuizCheck {content} showAnswersInPrint={true} />

<!-- Student copy — hides answer markers and explanations -->
<QuizCheck {content} showAnswersInPrint={false} />
```

---

## Reading Print Mode in Your Own Components

If you build custom components that sit inside a Lectio-powered layout and you want them to respond to print mode:

```svelte
<script lang="ts">
  import { usePrintMode } from 'lectio';

  const getPrintMode = usePrintMode();
  const printMode = $derived(getPrintMode());
</script>

{#if printMode}
  <!-- static print content -->
{:else}
  <!-- interactive content -->
{/if}
```

`usePrintMode()` returns a getter function (not a boolean) — wrap it in `$derived()` so your component stays reactive when the app toggles print mode on or off.

---

## For Lectio Contributors

### Architecture

Print mode is implemented as **component-level responsibility**:

- `src/lib/utils/printContext.ts` — `providePrintMode` / `usePrintMode`
- `src/lib/print/` — six shared print utility components + `index.ts` barrel
- Each of the 15 interactive components — reads `usePrintMode()` and swaps its template

The consuming application owns *when* print mode is active. Components own *how* they render in print mode.

### Pattern for adding print to a new component

```svelte
<script lang="ts">
  import { usePrintMode } from '$lib/utils/printContext';

  let { content } = $props();

  const getPrintMode = usePrintMode();
  const printMode = $derived(getPrintMode());
</script>

{#if printMode}
  <!-- Print fallback: static, no JS interactions, page-break-inside: avoid -->
{:else}
  <!-- Existing interactive markup — unchanged -->
{/if}

<style>
  @media print {
    /* Additional layout rules for print (e.g. hide nav controls) */
  }
</style>
```

Key rules:
- Always use `$derived(getPrintMode())` — never call `usePrintMode()()` directly in the template
- The print branch must be fully static: no interactive buttons, no JS-dependent state
- Use `page-break-inside: avoid` on the print container
- Prefer the shared utilities (`RuledLines`, `Checkboxes`, etc.) over writing new print CSS from scratch

### Context implementation detail

`providePrintMode` stores a **getter function** (not a boolean) in Svelte context. This is necessary because context is set at component initialisation time, but `isPrint` may change reactively afterward. The getter pattern lets `$derived()` in child components pick up changes without re-running `setContext`.

```ts
// src/lib/utils/printContext.ts
const KEY = Symbol('printMode');
export function providePrintMode(getter: () => boolean): void { setContext(KEY, getter); }
export function usePrintMode(): () => boolean { return getContext<() => boolean>(KEY) ?? (() => false); }
```

### Registry compliance test

`src/lib/print-registry-compliance.test.ts` verifies that every component's `printFallback` string in the registry matches the actual implemented behaviour. Run it with:

```bash
npm run test
```

When you add or change a component's print fallback, update both the implementation and the `printFallback` field in `src/lib/schema/registry.ts`.

### Showcase preview

The `/components` showcase has a **Print preview mode** toggle in the page header. Toggle it to verify print fallbacks without opening a browser print dialog. The toggle calls `providePrintMode(() => printPreviewMode)` — the same API consumers use.

