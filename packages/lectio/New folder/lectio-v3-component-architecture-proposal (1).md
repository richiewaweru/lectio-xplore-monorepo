# Lectio v3 Component Architecture Migration Proposal

## Purpose

Lectio is already a strong working component library. The current problem is not that the library is broken. The problem is that too much component truth currently lives in one central registry file.

Right now, `src/lib/schema/registry.ts` acts as the single source of truth for component metadata, showcase, template generation, validation, and contract export. It stores each component’s `id`, `purpose`, `cognitiveJob`, `subjects`, `behaviourModes`, `capacity`, `printFallback`, `generationHint`, `status`, `group`, and `sectionField`. It also derives the component-to-field map from `sectionField`.

That works today, but v3 needs a cleaner foundation:

```txt
Each component should own its own local truth.
The registry should collect component modules.
The exporter should generate contracts and an agent-readable manifest.
Textbook Generator v3 should consume exported JSON only.
```

This proposal keeps Lectio’s current strengths but reorganizes the code so components are easier to expand, inspect, test, and use by the v3 Lesson Architect.

---

## Current Codebase Reality

Lectio currently has three important foundations already in place:

### 1. Central component registry

`src/lib/schema/registry.ts` currently defines `ComponentMeta` and the full `componentRegistry`. This is the current source of truth for component metadata.

### 2. SectionContent type system

`src/lib/schema/types.ts` defines the content shapes that the LLM fills, components render, and templates assemble. It includes all major component content types such as `ExplanationContent`, `WorkedExampleContent`, `PracticeContent`, `DiagramContent`, `QuizContent`, `ReflectionContent`, `SimulationContent`, and the full `SectionContent` object.

### 3. Export pipeline

`scripts/export-contracts.ts` already exports:

```txt
section-content-schema.json
component-field-map.json
component-registry.json
preset-registry.json
template contracts
```

It reads `componentRegistry` and writes component metadata for downstream pipeline use.

So this migration should not reinvent Lectio. It should move the current truth into better locations.

---

## Target Architecture

Move from this:

```txt
src/lib/schema/registry.ts
  owns all component metadata
  owns field mapping
  feeds export-contracts
```

To this:

```txt
src/lib/lectio/components/{component-id}/
  Component.svelte
  schema.ts
  metadata.ts
  print.ts
  examples.ts
  index.ts

src/lib/lectio/registry/
  components.ts
  field-map.ts
  manifest.ts

scripts/export-contracts.ts
  exports contracts from collected component modules
```

The central rule:

```txt
Component folders own component truth.
Registry collects.
Exporter emits.
Textbook Generator consumes JSON.
```

---

## Proposed Folder Structure

```txt
src/lib/lectio/
  core/
    types.ts
    phases.ts
    validate-component.ts

  components/
    section-header/
      Component.svelte
      schema.ts
      metadata.ts
      print.ts
      examples.ts
      index.ts

    hook/
      Component.svelte
      schema.ts
      metadata.ts
      print.ts
      examples.ts
      index.ts

    explanation/
      Component.svelte
      schema.ts
      metadata.ts
      print.ts
      examples.ts
      index.ts

    worked-example/
      Component.svelte
      schema.ts
      metadata.ts
      print.ts
      examples.ts
      index.ts

    practice/
      Component.svelte
      schema.ts
      metadata.ts
      print.ts
      examples.ts
      index.ts

    diagram/
      Component.svelte
      schema.ts
      metadata.ts
      print.ts
      examples.ts
      index.ts

  registry/
    components.ts
    field-map.ts
    manifest.ts

scripts/
  export-contracts.ts
```

The folder names should use educator-readable names where possible.

For example:

```txt
worked-example-card → worked-example
practice-stack → practice
diagram-block → diagram
quiz-check → quick-check
reflection-prompt → reflection
pitfall-alert → common-mistake
```

Internally, keep stable legacy IDs where needed for compatibility, but expose teacher-facing names in the manifest.

---

## Component Naming Policy

Use two names per component:

```ts
id: "worked-example-card"          // stable technical/component ID
teacherLabel: "Worked Example"     // educator-facing UI label
name: "WorkedExampleCard"          // code/component name
```

Do not show IDs like `worked-example-card` or `diagram-block` directly in teacher UI unless needed for debugging.

Use clear teacher-facing labels:

```txt
section-header       → Lesson Section
hook-hero            → Opening Hook
explanation-block    → Explanation
prerequisite-strip   → Before You Start
what-next-bridge     → What Comes Next
interview-anchor     → Explain It Aloud
callout-block        → Key Note
summary-block        → Summary
section-divider      → Section Break

definition-card      → Definition
definition-family    → Related Definitions
glossary-rail        → Vocabulary List
glossary-inline      → Inline Vocabulary
insight-strip        → Key Insights
key-fact             → Key Fact
comparison-grid      → Compare Ideas

worked-example-card  → Worked Example
process-steps        → Step-by-Step Method

practice-stack       → Practice Questions
quiz-check           → Quick Check
reflection-prompt    → Reflection
student-textbox      → Student Response Box
short-answer         → Short Answer
fill-in-blank        → Fill in the Blank

pitfall-alert        → Common Mistake

diagram-block        → Diagram
diagram-compare      → Compare Diagrams
diagram-series       → Diagram Sequence
image-block          → Image
video-embed          → Video
timeline-block       → Timeline

simulation-block     → Interactive Simulation
```

The Lesson Architect can read the role and metadata. The teacher should see plain names.

---

## Core Types

Create:

```txt
src/lib/lectio/core/types.ts
```

```ts
import type { ZodTypeAny } from "zod";

export type LectioPhase = 1 | 2 | 3 | 4 | 5 | 6 | 7;

export type ComponentStatus = "stable" | "beta" | "planned";

export type BreakBehavior = "allow" | "avoid" | "force-new-page";
export type PreferredWidth = "full" | "half" | "inline";

export interface LectioCapabilities {
  acceptsMedia: boolean;
  acceptsQuestions: boolean;
  producesAnswerKey: boolean;
  interactive: boolean;
  isMedia: boolean;
}

export interface LectioPrintSpec {
  breakBehavior: BreakBehavior;
  preferredWidth: PreferredWidth;
  fallback: string;
  notes?: string;
}

export interface LectioComponentMetadata {
  id: string;
  name: string;
  teacherLabel: string;
  teacherDescription: string;

  phase: LectioPhase;

  /**
   * Agent-facing explanation of what this component is structurally for.
   * This is not a useWhen rule.
   */
  role: string;

  cognitiveJob: string;

  subjects: string[];
  behaviourModes: string[];

  capabilities: LectioCapabilities;
  capacity: Record<string, number | string>;

  /**
   * Field on SectionContent that this component renders.
   * null means inline-only or no dedicated SectionContent field.
   */
  sectionField: string | null;

  status: ComponentStatus;
  generationHint?: string;
}

export interface LectioComponentModule<TData = unknown> {
  component: unknown;
  schema: ZodTypeAny;
  metadata: LectioComponentMetadata;
  print: LectioPrintSpec;
  examples: TData[];
}
```

Important: do not put lesson-planning rules in this type.

Do not add:

```txt
useWhen
avoidWhen
bestForLearnerType
maxPerLesson
recommendedBefore
recommendedAfter
```

Those belong to Textbook Generator v3’s lens library and Lesson Architect.

---

## Phase Names

Create:

```txt
src/lib/lectio/core/phases.ts
```

```ts
export const LECTIO_PHASES = {
  1: {
    id: 1,
    name: "Orient",
    description: "Set direction, context, purpose, or closure."
  },
  2: {
    id: 2,
    name: "Build Knowledge",
    description: "Define, compare, organize, or anchor key knowledge."
  },
  3: {
    id: 3,
    name: "Model",
    description: "Show a method, example, or process before independent work."
  },
  4: {
    id: 4,
    name: "Practice and Check",
    description: "Let students answer, practise, retrieve, reflect, or show thinking."
  },
  5: {
    id: 5,
    name: "Address Mistakes",
    description: "Warn against misconceptions or correct common errors."
  },
  6: {
    id: 6,
    name: "Visualize",
    description: "Make spatial, relational, chronological, or visual structure visible."
  },
  7: {
    id: 7,
    name: "Interact",
    description: "Let learners manipulate, observe, or explore a concept interactively."
  }
} as const;
```

This preserves the current `group` structure but gives it clearer v3 meaning.

---

## Component Folder Contract

Every component folder must have:

```txt
Component.svelte
schema.ts
metadata.ts
print.ts
examples.ts
index.ts
```

### Example: Worked Example

```txt
src/lib/lectio/components/worked-example/
  Component.svelte
  schema.ts
  metadata.ts
  print.ts
  examples.ts
  index.ts
```

`schema.ts`

```ts
import { z } from "zod";

export const WorkedStepSchema = z.object({
  label: z.string(),
  content: z.string(),
  note: z.string().optional(),
  formula: z.string().optional(),
  diagram_ref: z.string().optional()
});

export const WorkedExampleSchema = z.object({
  title: z.string(),
  setup: z.string(),
  steps: z.array(WorkedStepSchema).min(1).max(6),
  conclusion: z.string(),
  method_label: z.string().optional(),
  answer: z.string().optional()
});

export type WorkedExampleData = z.infer<typeof WorkedExampleSchema>;
```

This should mirror the existing `WorkedExampleContent` shape from `src/lib/schema/types.ts`, not invent a new content shape. The existing type already includes title, setup, steps, conclusion, method label, alternatives, answer, and optional diagram.

`metadata.ts`

```ts
export const metadata = {
  id: "worked-example-card",
  name: "WorkedExampleCard",
  teacherLabel: "Worked Example",
  teacherDescription: "Shows a method step by step before students try it.",
  phase: 3,

  role: "Shows a complete method step by step so the learner can follow the reasoning before attempting a similar task.",

  cognitiveJob: "Watch reasoning in action",

  subjects: ["universal"],

  behaviourModes: ["static", "step-reveal", "accordion", "compare"],

  capabilities: {
    acceptsMedia: true,
    acceptsQuestions: false,
    producesAnswerKey: false,
    interactive: false,
    isMedia: false
  },

  capacity: {
    stepsMax: 6,
    stepsWarning: 4,
    stepLabelMaxWords: 12,
    stepContentMaxWords: 80
  },

  sectionField: "worked_example",
  status: "stable",

  generationHint:
    "Generate a short worked example with justified steps. Each step should show what was done and why it matters."
} as const;
```

`print.ts`

```ts
export const print = {
  breakBehavior: "avoid",
  preferredWidth: "full",
  fallback: "All steps expanded",
  notes: "Avoid splitting a worked example across pages when possible."
} as const;
```

`examples.ts`

```ts
import type { WorkedExampleData } from "./schema";

export const examples: WorkedExampleData[] = [
  {
    title: "Finding the area of an L-shape",
    setup: "An L-shaped floor can be split into two rectangles.",
    steps: [
      {
        label: "Split the shape",
        content: "Draw one straight line to make two rectangles.",
        note: "Splitting lets us use length × width."
      }
    ],
    conclusion: "Add the two rectangle areas to get the total area.",
    answer: "48 sq cm"
  }
];
```

`index.ts`

```ts
import Component from "./Component.svelte";
import { WorkedExampleSchema } from "./schema";
import { metadata } from "./metadata";
import { print } from "./print";
import { examples } from "./examples";

export default {
  component: Component,
  schema: WorkedExampleSchema,
  metadata,
  print,
  examples
};
```

---

## Registry Collector

Create:

```txt
src/lib/lectio/registry/components.ts
```

This registry should only collect modules.

```ts
import SectionHeader from "../components/section-header";
import Hook from "../components/hook";
import Explanation from "../components/explanation";
import Prerequisites from "../components/before-you-start";
import WorkedExample from "../components/worked-example";
import Practice from "../components/practice";
import Diagram from "../components/diagram";

export const lectioComponents = [
  SectionHeader,
  Hook,
  Explanation,
  Prerequisites,
  WorkedExample,
  Practice,
  Diagram
] as const;

export const componentRegistry = Object.fromEntries(
  lectioComponents.map((entry) => [entry.metadata.id, entry])
);
```

The old `src/lib/schema/registry.ts` should eventually become a compatibility wrapper, not the source of truth.

Possible wrapper:

```ts
export {
  componentRegistry,
  getComponentById,
  getStableComponents,
  getComponentsByPhase as getComponentsByGroup,
  getComponentsForSubject,
  getComponentFieldMap
} from "../lectio/registry";
```

This keeps old imports working while moving truth to the new structure.

---

## Field Map

Create:

```txt
src/lib/lectio/registry/field-map.ts
```

```ts
import { lectioComponents } from "./components";

export function getComponentFieldMap(): Record<string, string> {
  const map: Record<string, string> = {};

  for (const component of lectioComponents) {
    const field = component.metadata.sectionField;
    if (field !== null) {
      map[component.metadata.id] = field;
    }
  }

  return map;
}
```

This preserves the existing behavior where `sectionField` is the authoritative component-to-SectionContent mapping. The current registry already uses this pattern.

---

## Manifest Builder

Create:

```txt
src/lib/lectio/registry/manifest.ts
```

```ts
import { LECTIO_PHASES } from "../core/phases";
import { lectioComponents } from "./components";

export function buildLectioManifest() {
  return {
    version: "3.0.0",
    phases: Object.fromEntries(
      Object.entries(LECTIO_PHASES).map(([phaseId, phase]) => [
        phaseId,
        {
          ...phase,
          components: lectioComponents
            .filter((component) => component.metadata.phase === Number(phaseId))
            .map((component) => ({
              id: component.metadata.id,
              name: component.metadata.name,
              teacherLabel: component.metadata.teacherLabel,
              teacherDescription: component.metadata.teacherDescription,
              role: component.metadata.role,
              cognitiveJob: component.metadata.cognitiveJob,
              subjects: component.metadata.subjects,
              behaviourModes: component.metadata.behaviourModes,
              capabilities: component.metadata.capabilities,
              capacity: component.metadata.capacity,
              sectionField: component.metadata.sectionField,
              status: component.metadata.status,
              print: component.print
            }))
        }
      ])
    )
  };
}
```

This is the file Textbook Generator v3 should consume.

---

## Export Script Changes

Update `scripts/export-contracts.ts`.

The current script exports SectionContent schema, component field map, component registry, preset registry, and template contracts.

Keep those exports where useful, but change their source from old `componentRegistry` to the new module collector.

Add new exports:

```txt
manifest.json
component-schemas.json
print-rules.json
component-examples.json
```

Target output:

```txt
contracts/
  section-content-schema.json
  component-field-map.json
  component-registry.json
  component-schemas.json
  component-examples.json
  print-rules.json
  manifest.json
  preset-registry.json
```

### Export responsibilities

`manifest.json`

For Lesson Architect planning.

```txt
phase
role
teacher label
capabilities
capacity
print behavior
section field
```

`component-schemas.json`

For validating generated component data.

`component-field-map.json`

For mapping component IDs to `SectionContent` fields.

`print-rules.json`

For print/PDF layout decisions.

`component-examples.json`

For examples, tests, and future agent guidance.

`component-registry.json`

For backward compatibility and debugging.

---

## SectionContent Strategy

Do not delete `src/lib/schema/types.ts` yet.

It is currently the full canonical content model for what the LLM fills, what components render, and what templates assemble.

For this migration:

```txt
Keep SectionContent.
Move individual component content schemas beside components.
Eventually make SectionContent composed from component schemas.
```

Initial compatibility approach:

```txt
schema/types.ts remains.
component schema.ts files mirror existing content interfaces.
export-contracts still emits section-content-schema.json.
```

Later improvement:

```txt
Component schemas become canonical.
SectionContent is generated/composed from component schemas.
```

Do not try to solve that in the first pass unless necessary.

---

## Migration Plan for All Components

Migrate by phase, matching the existing registry groups.

### Phase 1 — Orient / Foundation

```txt
section-header       → Lesson Section
hook-hero            → Opening Hook
explanation-block    → Explanation
prerequisite-strip   → Before You Start
what-next-bridge     → What Comes Next
interview-anchor     → Explain It Aloud
callout-block        → Key Note
summary-block        → Summary
section-divider      → Section Break
video-embed          → Video
```

Note: `video-embed` currently sits in group 1 even though it is media. Keep the ID stable, but decide whether its v3 `phase` should remain 1 or move to 6. If unsure, keep phase 1 for compatibility and mark capability as media.

### Phase 2 — Build Knowledge

```txt
definition-card      → Definition
definition-family    → Related Definitions
glossary-rail        → Vocabulary List
glossary-inline      → Inline Vocabulary
insight-strip        → Key Insights
key-fact             → Key Fact
comparison-grid      → Compare Ideas
```

### Phase 3 — Model

```txt
worked-example-card  → Worked Example
process-steps        → Step-by-Step Method
```

### Phase 4 — Practice and Check

```txt
practice-stack       → Practice Questions
quiz-check           → Quick Check
reflection-prompt    → Reflection
student-textbox      → Student Response Box
short-answer         → Short Answer
fill-in-blank        → Fill in the Blank
```

### Phase 5 — Address Mistakes

```txt
pitfall-alert        → Common Mistake
```

### Phase 6 — Visualize

```txt
diagram-block        → Diagram
diagram-compare      → Compare Diagrams
diagram-series       → Diagram Sequence
image-block          → Image
timeline-block       → Timeline
```

### Phase 7 — Interact

```txt
simulation-block     → Interactive Simulation
```

The current registry has one inline-only component, `glossary-inline`, with `sectionField: null`. It should still have metadata and manifest visibility, but it should be excluded from `component-field-map.json`, matching current behavior.

---

## Capability Defaults

Use these defaults during migration.

### Text/explanation components

```ts
capabilities: {
  acceptsMedia: false,
  acceptsQuestions: false,
  producesAnswerKey: false,
  interactive: false,
  isMedia: false
}
```

### Practice/question components

For `practice-stack`, `quiz-check`, `short-answer`, `fill-in-blank`:

```ts
capabilities: {
  acceptsMedia: true,
  acceptsQuestions: true,
  producesAnswerKey: true,
  interactive: false,
  isMedia: false
}
```

### Reflection/student response components

```ts
capabilities: {
  acceptsMedia: false,
  acceptsQuestions: true,
  producesAnswerKey: false,
  interactive: false,
  isMedia: false
}
```

### Media components

For `diagram-block`, `diagram-compare`, `diagram-series`, `image-block`, `video-embed`, `timeline-block`:

```ts
capabilities: {
  acceptsMedia: false,
  acceptsQuestions: false,
  producesAnswerKey: false,
  interactive: false,
  isMedia: true
}
```

### Simulation

```ts
capabilities: {
  acceptsMedia: false,
  acceptsQuestions: false,
  producesAnswerKey: false,
  interactive: true,
  isMedia: true
}
```

---

## What Must Not Change

Do not change component IDs casually.

Keep IDs like:

```txt
worked-example-card
practice-stack
diagram-block
```

because downstream systems may already depend on them.

Teacher-facing names can become simpler:

```txt
Worked Example
Practice Questions
Diagram
```

Do not change `sectionField` names unless also updating `SectionContent`, export scripts, and downstream Textbook Generator contracts.

Examples:

```txt
worked-example-card → worked_example
practice-stack → practice
diagram-block → diagram
```

These mappings already exist and should remain stable.

---

## Validation Requirements

Add a component module validator:

```txt
src/lib/lectio/core/validate-component.ts
```

It should check:

```txt
metadata.id exists
metadata.teacherLabel exists
metadata.phase is 1–7
metadata.role exists
metadata.sectionField is string or null
schema exists
print.breakBehavior exists
print.preferredWidth exists
examples validate against schema
```

Run this during export.

If any component fails validation, `npm run export-contracts` should fail.

This prevents broken components from entering Textbook Generator v3.

---

## UI Naming Requirements

For any educator-facing UI, use:

```txt
teacherLabel
teacherDescription
```

Do not use:

```txt
id
name
sectionField
```

unless the UI is developer/admin/debug-only.

This matters because teachers should see:

```txt
Worked Example
Practice Questions
Common Mistake
Diagram Sequence
```

not:

```txt
worked-example-card
practice-stack
pitfall-alert
diagram-series
```

The current registry already pulls teacher-facing labels through `teacherFor(...)`. Keep that idea, but move the output into each component’s `metadata.ts`.

---

## Compatibility Wrapper

After migration, keep `src/lib/schema/registry.ts` as a wrapper if possible.

Current code may import:

```ts
import { componentRegistry, getComponentFieldMap } from "./schema/registry";
```

Replace the contents with exports from the new registry.

Example:

```ts
export {
  componentRegistry,
  getStableComponents,
  getComponentsForSubject,
  getComponentById
} from "../lectio/registry/components";

export { getComponentFieldMap } from "../lectio/registry/field-map";
```

If type compatibility is difficult, create adapter functions that return the old `ComponentMeta` shape from new metadata.

---

## Definition of Done

This migration is complete when:

```txt
1. All existing Lectio components are moved into standalone component folders.
2. Each component has Component.svelte, schema.ts, metadata.ts, print.ts, examples.ts, index.ts.
3. The central registry no longer owns inline metadata.
4. export-contracts.ts emits all old required files plus manifest.json.
5. component-field-map.json still excludes inline-only components with sectionField: null.
6. manifest.json is grouped by phase and uses educator-readable labels.
7. Examples validate against component schemas.
8. Existing component rendering still works.
9. Textbook Generator v3 can consume manifest.json without importing Lectio source code.
```

---

## Implementation Directive for Coding Agent

Refactor Lectio into v3 standalone component modules while preserving the current working behavior.

Do not rewrite the component renderers unless necessary. Move each existing component into a folder where it owns its schema, metadata, print behavior, examples, and export entry. Keep stable component IDs and section fields. Replace the central registry with a thin collector. Update export-contracts so all current exports still exist, and add an agent-readable `manifest.json` for Textbook Generator v3.

Use educator-readable labels in metadata and manifest. Technical IDs may stay stable internally, but teacher-facing surfaces should use plain names like “Worked Example,” “Practice Questions,” “Diagram,” and “Common Mistake.”

Do not encode lesson-planning rules inside Lectio components. Components describe what they are, what data they need, how they render, and how they behave in print. Textbook Generator v3 decides when and why to use them.
