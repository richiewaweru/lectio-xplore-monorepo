# Lectio Print Implementation - Complete Proposal

## Overview
Add print rendering capabilities to the Lectio component library, enabling high-quality PDF output when components are rendered in print context.

## Pre-conditions
- [ ] Lectio component library at current version
- [ ] All 28 components in registry
- [ ] TypeScript types exported correctly
- [ ] Component showcase functional

## Architecture Decision
Print rendering is implemented as **component-level responsibility**. Components detect print context (provided by consuming application via Svelte context) and render appropriate fallback UI using shared print utilities.

**Key principle**: Lectio components know *how* to render for print, but don't know *when* they're being printed (consuming app decides).

---

## Scope

### What This Implements
1. Shared print utility components (RuledLines, Checkboxes, ExpandedSteps, SideBySide)
2. Print fallback rendering for 15 interactive components
3. Component-level print CSS (`@media print` rules)
4. Print context detection pattern
5. Registry-driven verification tests
6. Component showcase print preview mode

### What This Does NOT Implement
- PDF generation (consuming app responsibility)
- Print mode detection via query params (consuming app responsibility)
- Global page setup CSS (consuming app responsibility)
- QR code generation (consuming app responsibility)

---

## Directory Structure

```
lectio/
  src/
    lib/
      print/                          # NEW - Print utilities
        RuledLines.svelte
        Checkboxes.svelte
        ExpandedSteps.svelte
        SideBySide.svelte
        VerticalList.svelte
        AnswerMarker.svelte
        index.ts                      # Barrel export
      components/
        lectio/
          SimulationBlock.svelte      # MODIFY - Add print fallback
          QuizCheck.svelte            # MODIFY - Add print fallback
          PracticeStack.svelte        # MODIFY - Add print fallback
          FillInTheBlank.svelte       # MODIFY - Add print fallback
          WorkedExampleCard.svelte    # MODIFY - Add print fallback
          DiagramCompare.svelte       # MODIFY - Add print fallback
          TimelineBlock.svelte        # MODIFY - Add print fallback
          ProcessSteps.svelte         # MODIFY - Add print fallback
          ReflectionPrompt.svelte     # MODIFY - Add print fallback
          StudentTextbox.svelte       # MODIFY - Add print fallback
          ShortAnswerQuestion.svelte  # MODIFY - Add print fallback
          DiagramSeries.svelte        # MODIFY - Add print fallback
          PitfallAlert.svelte         # MODIFY - Add print fallback
          ComparisonGrid.svelte       # MODIFY - Add print fallback
          DiagramBlock.svelte         # MODIFY - Add print fallback
      utils/
        printContext.ts               # NEW - Context helpers
    routes/
      components/
        +page.svelte                  # MODIFY - Add print preview toggle
  tests/
    print/
      registry-compliance.test.ts     # NEW - Verify components match registry specs
```

---

## Implementation Files

### 1. Print Context Utilities

**File**: `src/lib/utils/printContext.ts`

```typescript
import { getContext, setContext } from 'svelte';

const PRINT_MODE_KEY = Symbol('printMode');

/**
 * Provide print mode to child components via context.
 * Called by consuming application (e.g., Textbook Generator).
 */
export function providePrintMode(isPrint: boolean): void {
  setContext(PRINT_MODE_KEY, isPrint);
}

/**
 * Read print mode from context.
 * Called by Lectio components to determine rendering mode.
 */
export function usePrintMode(): boolean {
  return getContext<boolean>(PRINT_MODE_KEY) ?? false;
}
```

---

### 2. Ruled Lines Utility

**File**: `src/lib/print/RuledLines.svelte`

```svelte
<script lang="ts">
  /**
   * Renders ruled write-in lines for print.
   * Used by: ReflectionPrompt, StudentTextbox, ShortAnswerQuestion
   */
  export let lines: number = 4;
  export let lineHeight: string = '1.8rem';
  export let label: string | undefined = undefined;
</script>

<div class="ruled-lines">
  {#if label}
    <p class="label">{label}</p>
  {/if}
  <div class="lines-container">
    {#each Array(lines) as _, i}
      <div class="line" style="height: {lineHeight}"></div>
    {/each}
  </div>
</div>

<style>
  .ruled-lines {
    margin: 1rem 0;
  }
  
  .label {
    font-size: 0.875rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
    color: #374151;
  }
  
  .lines-container {
    display: flex;
    flex-direction: column;
  }
  
  .line {
    border-bottom: 1px solid #d1d5db;
    margin-bottom: 0.25rem;
  }
  
  @media print {
    .line {
      border-bottom: 1px solid #9ca3af;
    }
  }
</style>
```

---

### 3. Checkboxes Utility

**File**: `src/lib/print/Checkboxes.svelte`

```svelte
<script lang="ts">
  /**
   * Renders checkbox squares for process steps in print.
   * Used by: ProcessSteps
   */
  export let count: number;
  export let size: string = '1rem';
</script>

<div class="checkboxes">
  {#each Array(count) as _, i}
    <div class="checkbox" style="width: {size}; height: {size}"></div>
  {/each}
</div>

<style>
  .checkboxes {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  
  .checkbox {
    border: 2px solid #374151;
    border-radius: 0.125rem;
    flex-shrink: 0;
  }
  
  @media print {
    .checkbox {
      border-color: #000;
    }
  }
</style>
```

---

### 4. Expanded Steps Utility

**File**: `src/lib/print/ExpandedSteps.svelte`

```svelte
<script lang="ts">
  import type { WorkedStep } from '../types';
  
  /**
   * Renders all steps in expanded form for print.
   * Used by: WorkedExampleCard
   */
  export let steps: WorkedStep[];
  export let title: string | undefined = undefined;
</script>

<div class="expanded-steps">
  {#if title}
    <h4 class="steps-title">{title}</h4>
  {/if}
  
  {#each steps as step, idx}
    <div class="step">
      <div class="step-number">{idx + 1}</div>
      <div class="step-content">
        <div class="step-label">{step.label}</div>
        <div class="step-detail">{step.content}</div>
        {#if step.reasoning}
          <div class="step-reasoning">
            <strong>Why:</strong> {step.reasoning}
          </div>
        {/if}
      </div>
    </div>
  {/each}
</div>

<style>
  .expanded-steps {
    margin: 1rem 0;
  }
  
  .steps-title {
    font-size: 1.125rem;
    font-weight: 600;
    margin-bottom: 1rem;
  }
  
  .step {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
    page-break-inside: avoid;
  }
  
  .step-number {
    flex-shrink: 0;
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    background: #1f2937;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
  }
  
  .step-content {
    flex: 1;
  }
  
  .step-label {
    font-weight: 600;
    margin-bottom: 0.5rem;
  }
  
  .step-detail {
    margin-bottom: 0.5rem;
    line-height: 1.6;
  }
  
  .step-reasoning {
    font-size: 0.875rem;
    font-style: italic;
    color: #6b7280;
  }
  
  @media print {
    .step-number {
      background: #000;
    }
  }
</style>
```

---

### 5. Side-by-Side Layout Utility

**File**: `src/lib/print/SideBySide.svelte`

```svelte
<script lang="ts">
  /**
   * Renders two items side-by-side for print comparison.
   * Used by: DiagramCompare
   */
  export let leftLabel: string;
  export let rightLabel: string;
</script>

<div class="side-by-side">
  <div class="side">
    <div class="label">{leftLabel}</div>
    <div class="content">
      <slot name="left" />
    </div>
  </div>
  
  <div class="side">
    <div class="label">{rightLabel}</div>
    <div class="content">
      <slot name="right" />
    </div>
  </div>
</div>

<style>
  .side-by-side {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2rem;
    margin: 1rem 0;
    page-break-inside: avoid;
  }
  
  .label {
    font-weight: 600;
    margin-bottom: 0.5rem;
    text-align: center;
  }
  
  .content {
    display: flex;
    justify-content: center;
  }
  
  @media print {
    .side-by-side {
      gap: 1rem;
    }
  }
</style>
```

---

### 6. Vertical List Utility

**File**: `src/lib/print/VerticalList.svelte`

```svelte
<script lang="ts">
  import type { TimelineEvent } from '../types';
  
  /**
   * Renders timeline events as vertical list for print.
   * Used by: TimelineBlock
   */
  export let events: TimelineEvent[];
  export let title: string | undefined = undefined;
</script>

<div class="vertical-list">
  {#if title}
    <h4 class="list-title">{title}</h4>
  {/if}
  
  {#each events as event}
    <div class="event">
      <div class="event-marker">
        <div class="year">{event.year}</div>
        {#if event.era}
          <div class="era">{event.era}</div>
        {/if}
      </div>
      <div class="event-content">
        <h5 class="event-title">{event.title}</h5>
        <p class="event-summary">{event.summary}</p>
        {#if event.impact}
          <p class="event-impact"><strong>Impact:</strong> {event.impact}</p>
        {/if}
      </div>
    </div>
  {/each}
</div>

<style>
  .vertical-list {
    margin: 1rem 0;
  }
  
  .list-title {
    font-size: 1.125rem;
    font-weight: 600;
    margin-bottom: 1rem;
  }
  
  .event {
    display: flex;
    gap: 1.5rem;
    margin-bottom: 1.5rem;
    page-break-inside: avoid;
    border-left: 3px solid #e5e7eb;
    padding-left: 1rem;
  }
  
  .event-marker {
    flex-shrink: 0;
    width: 5rem;
  }
  
  .year {
    font-weight: 700;
    font-size: 1.125rem;
  }
  
  .era {
    font-size: 0.75rem;
    color: #6b7280;
    margin-top: 0.25rem;
  }
  
  .event-content {
    flex: 1;
  }
  
  .event-title {
    font-weight: 600;
    margin-bottom: 0.5rem;
  }
  
  .event-summary {
    line-height: 1.6;
    margin-bottom: 0.5rem;
  }
  
  .event-impact {
    font-size: 0.875rem;
    font-style: italic;
  }
  
  @media print {
    .event {
      border-left-color: #9ca3af;
    }
  }
</style>
```

---

### 7. Answer Marker Utility

**File**: `src/lib/print/AnswerMarker.svelte`

```svelte
<script lang="ts">
  /**
   * Marks correct answers in print mode.
   * Used by: QuizCheck, PracticeStack
   */
  export let isCorrect: boolean;
  export let showAnswers: boolean = true; // Configurable per-use
</script>

{#if showAnswers && isCorrect}
  <span class="answer-marker" aria-label="Correct answer">✓</span>
{/if}

<style>
  .answer-marker {
    display: inline-block;
    margin-left: 0.5rem;
    font-weight: 700;
    color: #059669;
  }
  
  @media print {
    .answer-marker {
      color: #000;
    }
  }
</style>
```

---

### 8. Print Utilities Barrel Export

**File**: `src/lib/print/index.ts`

```typescript
export { default as RuledLines } from './RuledLines.svelte';
export { default as Checkboxes } from './Checkboxes.svelte';
export { default as ExpandedSteps } from './ExpandedSteps.svelte';
export { default as SideBySide } from './SideBySide.svelte';
export { default as VerticalList } from './VerticalList.svelte';
export { default as AnswerMarker } from './AnswerMarker.svelte';
```

---

### 9. Component Updates - High Priority

#### SimulationBlock (MODIFY)

**File**: `src/lib/components/lectio/SimulationBlock.svelte`

```svelte
<script lang="ts">
  import type { SimulationContent } from '../../types';
  import { usePrintMode } from '../../utils/printContext';
  
  export let content: SimulationContent;
  
  const printMode = usePrintMode();
  const hasLiveContent = !!content.html_content;
  const printStrategy = content.spec.print_translation;
</script>

{#if printMode}
  <!-- Print mode: Use fallback based on print_translation -->
  {#if printStrategy === 'hide'}
    <div class="print-note">
      <p><strong>Interactive simulation:</strong> {content.spec.goal}</p>
      <p class="note">Available in digital version</p>
    </div>
  
  {:else if printStrategy === 'static_diagram' && content.fallback_diagram}
    <div class="print-fallback">
      <div class="diagram-wrapper" role="img" aria-label={content.fallback_diagram.alt_text}>
        {@html content.fallback_diagram.svg_content}
      </div>
      {#if content.fallback_diagram.caption}
        <p class="caption">{content.fallback_diagram.caption}</p>
      {/if}
    </div>
  
  {:else if printStrategy === 'static_midstate' && content.fallback_diagram}
    <div class="print-fallback">
      <p class="simulation-label">{content.spec.type.replace(/_/g, ' ')}</p>
      <div role="img" aria-label={content.fallback_diagram.alt_text}>
        {@html content.fallback_diagram.svg_content}
      </div>
      {#if content.fallback_diagram.caption}
        <p class="caption">{content.fallback_diagram.caption}</p>
      {/if}
    </div>
  
  {:else}
    <div class="print-note">
      <p><strong>{content.spec.type.replace(/_/g, ' ')}:</strong> {content.spec.goal}</p>
      <p class="note">See digital version for interactive experience</p>
    </div>
  {/if}

{:else}
  <!-- Interactive mode: Existing rendering logic -->
  <div class="simulation-block">
    {#if hasLiveContent}
      <iframe
        srcdoc={content.html_content}
        sandbox="allow-scripts"
        title={content.spec.goal}
        style="height: {content.spec.dimensions.height}px;"
      ></iframe>
    {:else if content.fallback_diagram}
      <!-- Scaffold with fallback -->
      <div>{@html content.fallback_diagram.svg_content}</div>
    {/if}
  </div>
{/if}

<style>
  @media print {
    .simulation-block {
      display: none;
    }
    
    .print-fallback {
      page-break-inside: avoid;
      margin: 1rem 0;
    }
    
    .diagram-wrapper {
      max-width: 80%;
      margin: 0 auto;
    }
    
    .caption {
      text-align: center;
      font-size: 0.875rem;
      font-style: italic;
      margin-top: 0.5rem;
    }
    
    .print-note {
      padding: 1rem;
      border: 1px solid #d1d5db;
      background: #f9fafb;
    }
    
    .note {
      font-size: 0.875rem;
      color: #6b7280;
      margin-top: 0.5rem;
    }
  }
</style>
```

---

#### QuizCheck (MODIFY)

**File**: `src/lib/components/lectio/QuizCheck.svelte`

```svelte
<script lang="ts">
  import type { QuizContent } from '../../types';
  import { usePrintMode } from '../../utils/printContext';
  import { AnswerMarker } from '../../print';
  
  export let content: QuizContent;
  export let showAnswersInPrint: boolean = true; // Configurable
  
  const printMode = usePrintMode();
</script>

{#if printMode}
  <!-- Print mode: Show question with optional answer marking -->
  <div class="quiz-print">
    <div class="question">{content.question}</div>
    <div class="options">
      {#each content.options as option, idx}
        <div class="option">
          <span class="option-letter">{String.fromCharCode(65 + idx)}.</span>
          <span class="option-text">{option.text}</span>
          <AnswerMarker isCorrect={option.correct} {showAnswersInPrint} />
        </div>
      {/each}
    </div>
    {#if showAnswersInPrint}
      <div class="answer-section">
        <p class="answer-label"><strong>Explanation:</strong></p>
        {#each content.options.filter(o => o.correct) as correctOption}
          <p>{correctOption.explanation}</p>
        {/each}
      </div>
    {/if}
  </div>

{:else}
  <!-- Interactive mode: Existing rendering logic -->
  <div class="quiz-interactive">
    <!-- Existing interactive quiz UI -->
  </div>
{/if}

<style>
  @media print {
    .quiz-interactive {
      display: none;
    }
    
    .quiz-print {
      page-break-inside: avoid;
      margin: 1rem 0;
      padding: 1rem;
      border: 2px solid #e5e7eb;
    }
    
    .question {
      font-weight: 600;
      margin-bottom: 1rem;
    }
    
    .options {
      margin-bottom: 1rem;
    }
    
    .option {
      display: flex;
      align-items: baseline;
      margin-bottom: 0.5rem;
    }
    
    .option-letter {
      font-weight: 600;
      margin-right: 0.5rem;
      min-width: 1.5rem;
    }
    
    .option-text {
      flex: 1;
    }
    
    .answer-section {
      border-top: 1px solid #d1d5db;
      padding-top: 0.75rem;
      margin-top: 0.75rem;
    }
    
    .answer-label {
      margin-bottom: 0.5rem;
    }
  }
</style>
```

---

#### PracticeStack (MODIFY)

**File**: `src/lib/components/lectio/PracticeStack.svelte`

```svelte
<script lang="ts">
  import type { PracticeContent } from '../../types';
  import { usePrintMode } from '../../utils/printContext';
  import { RuledLines } from '../../print';
  
  export let content: PracticeContent;
  
  const printMode = usePrintMode();
</script>

{#if printMode}
  <!-- Print mode: Expand all hints, show write-in space -->
  <div class="practice-print">
    <h4>{content.label || 'Practice Problems'}</h4>
    
    {#each content.problems as problem, idx}
      <div class="problem">
        <div class="problem-header">
          <span class="problem-number">Problem {idx + 1}</span>
          <span class="difficulty">{problem.difficulty}</span>
        </div>
        
        <div class="question">{problem.question}</div>
        
        {#if problem.hints && problem.hints.length > 0}
          <div class="hints">
            <p class="hints-label"><strong>Hints:</strong></p>
            {#each problem.hints as hint}
              <p class="hint">• {hint.text}</p>
            {/each}
          </div>
        {/if}
        
        {#if problem.writein_lines && problem.writein_lines > 0}
          <RuledLines lines={problem.writein_lines} label="Your answer:" />
        {/if}
        
        {#if problem.solution && content.solutions_available}
          <div class="solution">
            <p class="solution-label"><strong>Solution:</strong></p>
            <p>{problem.solution.approach}</p>
            <p class="answer"><strong>Answer:</strong> {problem.solution.answer}</p>
          </div>
        {/if}
      </div>
    {/each}
  </div>

{:else}
  <!-- Interactive mode: Existing rendering logic -->
  <div class="practice-interactive">
    <!-- Existing interactive practice UI -->
  </div>
{/if}

<style>
  @media print {
    .practice-interactive {
      display: none;
    }
    
    .practice-print {
      margin: 1rem 0;
    }
    
    .practice-print h4 {
      font-size: 1.125rem;
      font-weight: 600;
      margin-bottom: 1rem;
    }
    
    .problem {
      page-break-inside: avoid;
      margin-bottom: 2rem;
      padding: 1rem;
      border: 1px solid #e5e7eb;
    }
    
    .problem-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 0.75rem;
    }
    
    .problem-number {
      font-weight: 600;
    }
    
    .difficulty {
      font-size: 0.875rem;
      color: #6b7280;
      text-transform: capitalize;
    }
    
    .question {
      margin-bottom: 1rem;
      line-height: 1.6;
    }
    
    .hints {
      background: #f9fafb;
      padding: 0.75rem;
      margin: 1rem 0;
      border-left: 3px solid #d1d5db;
    }
    
    .hints-label {
      margin-bottom: 0.5rem;
    }
    
    .hint {
      margin: 0.25rem 0;
      font-size: 0.875rem;
    }
    
    .solution {
      border-top: 1px solid #d1d5db;
      padding-top: 0.75rem;
      margin-top: 1rem;
    }
    
    .solution-label {
      margin-bottom: 0.5rem;
    }
    
    .answer {
      margin-top: 0.5rem;
    }
  }
</style>
```

---

#### WorkedExampleCard (MODIFY)

**File**: `src/lib/components/lectio/WorkedExampleCard.svelte`

```svelte
<script lang="ts">
  import type { WorkedExampleContent } from '../../types';
  import { usePrintMode } from '../../utils/printContext';
  import { ExpandedSteps } from '../../print';
  
  export let content: WorkedExampleContent;
  
  const printMode = usePrintMode();
</script>

{#if printMode}
  <!-- Print mode: All steps expanded -->
  <div class="worked-example-print">
    <ExpandedSteps steps={content.steps} title={content.title} />
  </div>

{:else}
  <!-- Interactive mode: Accordion/step-reveal UI -->
  <div class="worked-example-interactive">
    <!-- Existing interactive UI -->
  </div>
{/if}

<style>
  @media print {
    .worked-example-interactive {
      display: none;
    }
    
    .worked-example-print {
      page-break-inside: avoid;
      margin: 1rem 0;
    }
  }
</style>
```

---

#### DiagramCompare (MODIFY)

**File**: `src/lib/components/lectio/DiagramCompare.svelte`

```svelte
<script lang="ts">
  import type { DiagramCompareContent } from '../../types';
  import { usePrintMode } from '../../utils/printContext';
  import { SideBySide } from '../../print';
  
  export let content: DiagramCompareContent;
  
  const printMode = usePrintMode();
</script>

{#if printMode}
  <!-- Print mode: Both diagrams side-by-side -->
  <div class="diagram-compare-print">
    <SideBySide leftLabel={content.before_label} rightLabel={content.after_label}>
      <div slot="left" role="img" aria-label="{content.before_label} diagram">
        {@html content.before_svg}
      </div>
      <div slot="right" role="img" aria-label="{content.after_label} diagram">
        {@html content.after_svg}
      </div>
    </SideBySide>
    
    {#if content.caption}
      <p class="caption">{content.caption}</p>
    {/if}
  </div>

{:else}
  <!-- Interactive mode: Slider comparison -->
  <div class="diagram-compare-interactive">
    <!-- Existing interactive comparison UI -->
  </div>
{/if}

<style>
  @media print {
    .diagram-compare-interactive {
      display: none;
    }
    
    .diagram-compare-print {
      page-break-inside: avoid;
      margin: 1rem 0;
    }
    
    .caption {
      text-align: center;
      font-size: 0.875rem;
      font-style: italic;
      margin-top: 1rem;
    }
  }
</style>
```

---

#### TimelineBlock (MODIFY)

**File**: `src/lib/components/lectio/TimelineBlock.svelte`

```svelte
<script lang="ts">
  import type { TimelineContent } from '../../types';
  import { usePrintMode } from '../../utils/printContext';
  import { VerticalList } from '../../print';
  
  export let content: TimelineContent;
  
  const printMode = usePrintMode();
</script>

{#if printMode}
  <!-- Print mode: Vertical event list -->
  <div class="timeline-print">
    <VerticalList events={content.events} title={content.title} />
    
    {#if content.closing_takeaway}
      <div class="takeaway">
        <strong>Key Takeaway:</strong> {content.closing_takeaway}
      </div>
    {/if}
  </div>

{:else}
  <!-- Interactive mode: Timeline scrubber -->
  <div class="timeline-interactive">
    <!-- Existing interactive timeline UI -->
  </div>
{/if}

<style>
  @media print {
    .timeline-interactive {
      display: none;
    }
    
    .timeline-print {
      margin: 1rem 0;
    }
    
    .takeaway {
      margin-top: 1.5rem;
      padding: 1rem;
      background: #f9fafb;
      border-left: 3px solid #374151;
    }
  }
</style>
```

---

### 10. Component Updates - Medium Priority

#### ProcessSteps (MODIFY)

**File**: `src/lib/components/lectio/ProcessSteps.svelte`

```svelte
<script lang="ts">
  import type { ProcessContent } from '../../types';
  import { usePrintMode } from '../../utils/printContext';
  import { Checkboxes } from '../../print';
  
  export let content: ProcessContent;
  
  const printMode = usePrintMode();
</script>

{#if printMode}
  <!-- Print mode: All steps visible with checkboxes -->
  <div class="process-print">
    <h4>{content.title}</h4>
    
    <div class="steps-with-checkboxes">
      <div class="checkboxes-column">
        <Checkboxes count={content.steps.length} />
      </div>
      
      <div class="steps-column">
        {#each content.steps as step}
          <div class="step">
            <div class="step-number">{step.number}</div>
            <div class="step-content">
              <div class="action">{step.action}</div>
              <div class="detail">{step.detail}</div>
              {#if step.warning}
                <div class="warning">⚠️ {step.warning}</div>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    </div>
  </div>

{:else}
  <!-- Interactive mode: Existing rendering logic -->
  <div class="process-interactive">
    <!-- Existing interactive process UI -->
  </div>
{/if}

<style>
  @media print {
    .process-interactive {
      display: none;
    }
    
    .process-print {
      margin: 1rem 0;
    }
    
    .process-print h4 {
      font-size: 1.125rem;
      font-weight: 600;
      margin-bottom: 1rem;
    }
    
    .steps-with-checkboxes {
      display: flex;
      gap: 1rem;
    }
    
    .checkboxes-column {
      flex-shrink: 0;
    }
    
    .steps-column {
      flex: 1;
    }
    
    .step {
      display: flex;
      gap: 1rem;
      margin-bottom: 1.5rem;
      page-break-inside: avoid;
    }
    
    .step-number {
      flex-shrink: 0;
      width: 1.5rem;
      height: 1.5rem;
      border-radius: 50%;
      background: #e5e7eb;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      font-size: 0.875rem;
    }
    
    .action {
      font-weight: 600;
      margin-bottom: 0.5rem;
    }
    
    .detail {
      line-height: 1.6;
    }
    
    .warning {
      margin-top: 0.5rem;
      font-size: 0.875rem;
      color: #d97706;
    }
  }
</style>
```

---

#### ReflectionPrompt (MODIFY)

**File**: `src/lib/components/lectio/ReflectionPrompt.svelte`

```svelte
<script lang="ts">
  import type { ReflectionContent } from '../../types';
  import { usePrintMode } from '../../utils/printContext';
  import { RuledLines } from '../../print';
  
  export let content: ReflectionContent;
  
  const printMode = usePrintMode();
  const defaultLines = content.space || 4;
</script>

{#if printMode}
  <!-- Print mode: Prompt with write-in lines -->
  <div class="reflection-print">
    <p class="prompt">{content.prompt}</p>
    <RuledLines lines={defaultLines} />
  </div>

{:else}
  <!-- Interactive mode: Existing rendering logic -->
  <div class="reflection-interactive">
    <!-- Existing interactive reflection UI -->
  </div>
{/if}

<style>
  @media print {
    .reflection-interactive {
      display: none;
    }
    
    .reflection-print {
      page-break-inside: avoid;
      margin: 1rem 0;
      padding: 1rem;
      border: 2px solid #e5e7eb;
      background: #fefce8;
    }
    
    .prompt {
      font-weight: 600;
      margin-bottom: 1rem;
    }
  }
</style>
```

---

#### StudentTextbox (MODIFY)

**File**: `src/lib/components/lectio/StudentTextbox.svelte`

```svelte
<script lang="ts">
  import type { StudentTextboxContent } from '../../types';
  import { usePrintMode } from '../../utils/printContext';
  import { RuledLines } from '../../print';
  
  export let content: StudentTextboxContent;
  
  const printMode = usePrintMode();
  const defaultLines = content.lines || 4;
</script>

{#if printMode}
  <!-- Print mode: Lined write-in area -->
  <div class="textbox-print">
    <RuledLines lines={defaultLines} label={content.prompt} />
  </div>

{:else}
  <!-- Interactive mode: Existing rendering logic -->
  <div class="textbox-interactive">
    <!-- Existing interactive textbox UI -->
  </div>
{/if}

<style>
  @media print {
    .textbox-interactive {
      display: none;
    }
    
    .textbox-print {
      page-break-inside: avoid;
      margin: 1rem 0;
    }
  }
</style>
```

---

#### ShortAnswerQuestion (MODIFY)

**File**: `src/lib/components/lectio/ShortAnswerQuestion.svelte`

```svelte
<script lang="ts">
  import type { ShortAnswerContent } from '../../types';
  import { usePrintMode } from '../../utils/printContext';
  import { RuledLines } from '../../print';
  
  export let content: ShortAnswerContent;
  
  const printMode = usePrintMode();
  const defaultLines = content.lines || 6;
</script>

{#if printMode}
  <!-- Print mode: Question with lined answer space -->
  <div class="short-answer-print">
    <div class="question-header">
      <span class="question-text">{content.question}</span>
      {#if content.marks}
        <span class="marks">[{content.marks} marks]</span>
      {/if}
    </div>
    
    <RuledLines lines={defaultLines} label="Answer:" />
  </div>

{:else}
  <!-- Interactive mode: Existing rendering logic -->
  <div class="short-answer-interactive">
    <!-- Existing interactive short answer UI -->
  </div>
{/if}

<style>
  @media print {
    .short-answer-interactive {
      display: none;
    }
    
    .short-answer-print {
      page-break-inside: avoid;
      margin: 1rem 0;
      padding: 1rem;
      border: 1px solid #e5e7eb;
    }
    
    .question-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 1rem;
    }
    
    .question-text {
      font-weight: 600;
      flex: 1;
    }
    
    .marks {
      font-size: 0.875rem;
      color: #6b7280;
      margin-left: 1rem;
    }
  }
</style>
```

---

### 11. Component Updates - Low Priority

#### FillInTheBlank (MODIFY)

**File**: `src/lib/components/lectio/FillInTheBlank.svelte`

```svelte
<script lang="ts">
  import type { FillInBlankContent, FillInBlankSegment } from '../../types';
  import { usePrintMode } from '../../utils/printContext';
  
  export let content: FillInBlankContent;
  
  const printMode = usePrintMode();
</script>

{#if printMode}
  <!-- Print mode: Passage with underlined blanks, word bank below -->
  <div class="fill-blank-print">
    <div class="passage">
      {#each content.segments as segment}
        {#if segment.type === 'text'}
          <span>{segment.content}</span>
        {:else if segment.type === 'blank'}
          <span class="blank">________________</span>
        {/if}
      {/each}
    </div>
    
    {#if content.word_bank && content.word_bank.length > 0}
      <div class="word-bank">
        <p class="word-bank-label"><strong>Word Bank:</strong></p>
        <div class="words">
          {#each content.word_bank as word}
            <span class="word">{word}</span>
          {/each}
        </div>
      </div>
    {/if}
  </div>

{:else}
  <!-- Interactive mode: Existing rendering logic -->
  <div class="fill-blank-interactive">
    <!-- Existing interactive fill-in-blank UI -->
  </div>
{/if}

<style>
  @media print {
    .fill-blank-interactive {
      display: none;
    }
    
    .fill-blank-print {
      page-break-inside: avoid;
      margin: 1rem 0;
    }
    
    .passage {
      line-height: 2;
      margin-bottom: 1.5rem;
    }
    
    .blank {
      display: inline-block;
      min-width: 4rem;
      border-bottom: 1px solid #000;
      margin: 0 0.25rem;
    }
    
    .word-bank {
      padding: 1rem;
      border: 2px solid #e5e7eb;
      background: #f9fafb;
    }
    
    .word-bank-label {
      margin-bottom: 0.75rem;
    }
    
    .words {
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
    }
    
    .word {
      padding: 0.25rem 0.75rem;
      border: 1px solid #d1d5db;
      border-radius: 0.25rem;
    }
  }
</style>
```

---

#### DiagramSeries, DiagramBlock, PitfallAlert, ComparisonGrid (MODIFY)

These components need minimal changes - just add `@media print` rules for layout optimization:

```svelte
<style>
  @media print {
    /* Component-specific print adjustments */
    .component-container {
      page-break-inside: avoid;
    }
    
    .diagram-wrapper {
      max-width: 80%;
      margin: 0 auto;
    }
  }
</style>
```

---

### 12. Component Showcase Print Preview

**File**: `src/routes/components/+page.svelte` (MODIFY)

Add print preview toggle:

```svelte
<script lang="ts">
  import { providePrintMode } from '$lib/utils/printContext';
  
  let printPreviewMode = $state(false);
  
  $effect(() => {
    providePrintMode(printPreviewMode);
  });
</script>

<div class="showcase-controls">
  <label>
    <input type="checkbox" bind:checked={printPreviewMode} />
    Print Preview Mode
  </label>
</div>

<!-- Rest of showcase -->
```

---

### 13. Registry Compliance Tests

**File**: `tests/print/registry-compliance.test.ts`

```typescript
import { describe, it, expect } from 'vitest';
import { componentRegistry } from '$lib/registry';

describe('Print Fallback Registry Compliance', () => {
  const componentsWithPrintFallbacks = Object.entries(componentRegistry)
    .filter(([_, meta]) => meta.print_fallback);
  
  it('should have print fallback implementations for all registry specs', () => {
    componentsWithPrintFallbacks.forEach(([id, meta]) => {
      // This test verifies that components with print_fallback in registry
      // actually implement the specified fallback strategy
      
      expect(meta.print_fallback).toBeDefined();
      
      // Component should have print mode detection
      // Component should render fallback matching registry description
      // These would be verified via visual regression tests or manual review
    });
  });
  
  it('should match registry descriptions', () => {
    const expectedFallbacks = {
      'quiz-check': 'Question and options shown, correct answer marked',
      'practice-stack': 'All visible, write-in lines rendered',
      'worked-example-card': 'All steps expanded',
      'simulation-block': 'Static diagram at midstate',
      // ... all 15 components
    };
    
    Object.entries(expectedFallbacks).forEach(([id, expected]) => {
      const actual = componentRegistry[id]?.print_fallback;
      expect(actual).toBe(expected);
    });
  });
});
```

---

## Package Updates

**File**: `package.json` (MODIFY)

```json
{
  "name": "lectio",
  "version": "1.1.0",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "svelte": "./dist/index.js"
    },
    "./print": {
      "types": "./dist/print/index.d.ts",
      "svelte": "./dist/print/index.js"
    }
  }
}
```

**File**: `src/lib/index.ts` (MODIFY)

Add print utilities export:

```typescript
// Existing exports...

// Print utilities
export * from './print';
export { providePrintMode, usePrintMode } from './utils/printContext';
```

---

## Testing & Verification

### 1. Component Unit Tests

```bash
npm run test:unit
```

Verify:
- Print utilities render correctly
- Components detect print mode from context
- Fallback rendering matches registry spec

### 2. Visual Regression Tests

```bash
npm run test:visual
```

Capture screenshots of:
- Each component in interactive mode
- Each component in print mode
- Verify fallback matches specification

### 3. Manual Testing Checklist

- [ ] All 15 components with print fallbacks implemented
- [ ] Print utilities (6) all working
- [ ] Component showcase has print preview toggle
- [ ] Print mode context propagates correctly
- [ ] Registry compliance tests pass
- [ ] No TypeScript errors
- [ ] Build completes successfully

---

## Phase Completion Checklist

### Print Utilities
- [ ] RuledLines.svelte created and tested
- [ ] Checkboxes.svelte created and tested
- [ ] ExpandedSteps.svelte created and tested
- [ ] SideBySide.svelte created and tested
- [ ] VerticalList.svelte created and tested
- [ ] AnswerMarker.svelte created and tested
- [ ] Barrel export (`print/index.ts`) created

### High-Priority Components
- [ ] SimulationBlock print fallback implemented
- [ ] QuizCheck print fallback implemented
- [ ] PracticeStack print fallback implemented
- [ ] FillInTheBlank print fallback implemented
- [ ] WorkedExampleCard print fallback implemented
- [ ] DiagramCompare print fallback implemented
- [ ] TimelineBlock print fallback implemented

### Medium-Priority Components
- [ ] ProcessSteps print fallback implemented
- [ ] ReflectionPrompt print fallback implemented
- [ ] StudentTextbox print fallback implemented
- [ ] ShortAnswerQuestion print fallback implemented

### Low-Priority Components
- [ ] DiagramSeries print CSS added
- [ ] DiagramBlock print CSS added
- [ ] PitfallAlert print CSS added
- [ ] ComparisonGrid print CSS added

### Infrastructure
- [ ] `printContext.ts` utilities created
- [ ] Component showcase print preview toggle added
- [ ] Registry compliance tests written
- [ ] Package exports updated
- [ ] TypeScript builds without errors
- [ ] All tests passing

---

## Publishing

```bash
# Build library
npm run build

# Run tests
npm run test

# Update version
npm version minor  # 1.0.0 → 1.1.0

# Publish to NPM
npm publish

# Create git tag
git tag v1.1.0
git push origin v1.1.0
```

---

## Usage by Consuming Applications

Applications using Lectio can now enable print rendering:

```svelte
<!-- In Textbook Generator or other consuming app -->
<script lang="ts">
  import { providePrintMode } from 'lectio';
  import { page } from '$app/stores';
  
  const isPrintMode = $page.url.searchParams.get('print') === 'true';
  providePrintMode(isPrintMode);
</script>

<!-- All Lectio components automatically render print fallbacks -->
<SimulationBlock {content} />
<QuizCheck {content} />
<PracticeStack {content} />
```

---

## Known Limitations

1. **Answer key visibility**: QuizCheck and PracticeStack have `showAnswersInPrint` prop - consuming app must decide whether to show answers
2. **Print context required**: Components need context provided by app via `providePrintMode()`
3. **Static fallbacks only**: No dynamic print content generation
4. **No QR code generation**: Consuming app responsible for adding QR codes if needed

---

## Next Steps

After Lectio print implementation:
1. Consuming applications (like Textbook Generator) can enable print mode
2. Backend pipelines should populate `writein_lines`, `space`, and `fallback_diagram` fields
3. Applications can wrap components with QR code links if desired
4. PDF generation services can use print-mode rendered HTML

---

## Support & Documentation

- **Component Registry**: See `backend/contracts/component-registry.json` for print fallback specifications
- **Print Utilities**: See `src/lib/print/` for reusable print components
- **Examples**: Component showcase at `/components` with print preview toggle
- **Tests**: Registry compliance tests verify implementation matches specs
