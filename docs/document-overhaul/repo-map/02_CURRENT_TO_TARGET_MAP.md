# Current → Target Architecture Map

## Current

```text
Unit
 ↓
Concepts / PathLesson
 ↓
Teaching Plan
 ↓
path admission
 ├──────────────────────────────┐
 ↓                              ↓
PRINT                           LEARN
closed Print forms              content + interaction capabilities
 ↓                              ↓
whole_lesson                    native_selection
 ↓                              ↓
page objects                    component_lectio
 ↓                              ↓
@lectio/page                    LessonDocument / Builder
 ↓                              ↓
PDF                             Preview / Release / Runtime
```

## Target

```text
Unit
 ↓
Concepts / PathLesson
 ↓
Teaching Plan
(including learner task meaning)
 ↓
path admission
 ├──────────────────────────────┐
 ↓                              ↓
PRINT REALIZER                  LEARN REALIZER
 ↓                              ↓
document primitives             document primitives
+ Print task treatments         + retained interactions
 ↓                              ↓
PrintDocument                   LearnDocument
 ↓                              ↓
page engine / pagination        editable web document
 ↓                              ↓
PDF                             release / runtime / analytics
```

## What is reused rather than rebuilt

```text
KEEP/ADAPT
─────────────────────────────────────────────
Unit + curriculum path
Teaching Plan revisions/approval
independent realization identity
generation status/retry infrastructure where sound
Print page/PDF engine
Print figure/table/prose knowledge
Learn Builder persistence patterns
Learn release/runtime/attempt/analytics infrastructure
retained interaction evaluators/renderers
auth/dashboard/workspace/application shell
```

## What fundamentally changes

```text
CURRENT                              TARGET
────────────────────────────────────────────────────────
Learn content capability registry → six document primitives
content component selection       → document composition
component-specific content schema → simple node schemas
component-specific writers        → generic document writers
SectionContent field map          → ordered document nodes
template-owned block constraints  → path realizer + renderer rules
Learn print-mode components       → Print-only implementation
dual-output convenience           → explicit single-path request by default
Print-owned canonical intents     → genuinely shared intent owner
```

## What disappears

```text
ExplanationBlock
DefinitionCard
SummaryBlock
InsightStrip
KeyFact
PitfallAlert
PracticeStack-as-general-content
registry/template machinery needed only by those content blocks
component_lectio ordinary-content lane
video/simulation/unsupported media pathways
old lesson compatibility
legacy content adapters/fallbacks
```

Retained interactions are decided separately by behavior, not by old package membership.
