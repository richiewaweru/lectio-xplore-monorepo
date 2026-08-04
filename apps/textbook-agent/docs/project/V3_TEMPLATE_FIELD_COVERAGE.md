# V3 template field coverage (guided-concept-path)

Audit of common V3 `SectionContent` fields vs Lectio components used in the active template. When a field is valid in the contract but omitted here, treat it as a template gap to fix in the **Lectio** package and re-publish.

| Field | Rendered | Component | Notes |
| --- | --- | --- | --- |
| header | yes | SectionHeader | Required metadata |
| hook | yes | HookHero | |
| prerequisites | yes | PrerequisiteStrip | |
| explanation | yes | ExplanationBlock | Markdown emphasis supported |
| definition | yes | DefinitionCard | |
| definition_family | yes | DefinitionFamily | Print: expanded list (accordion bypassed) |
| key_fact | yes | KeyFact | Inline markdown via RichText |
| callout | yes | CalloutBlock | Inline markdown heading/body |
| pitfall / pitfalls | yes | PitfallAlert | Print: examples always visible |
| quiz | yes | QuizCheck | Print layout with AnswerMarker |
| worked_example / worked_examples | yes | WorkedExampleCard | Print: eager diagram images |
| practice | yes | PracticeStack | Print branch; eager inline diagrams |
| summary | yes | SummaryBlock | |
| reflection | yes | ReflectionPrompt | |
| what_next | yes | WhatNextBridge | |
| diagram | yes | DiagramBlock | Print: eager `loading`, callout text list, caption markdown |
| diagram_series | yes | DiagramSeries | Verify per-template |
| diagram_compare | yes | DiagramCompare | |
| simulation | yes | SimulationBlock | Print uses `print_translation` |
| student_textbox | yes | StudentTextbox | |
| short_answer | yes | ShortAnswerQuestion | |
| fill_in_blank | yes | FillInTheBlank | |

**Upstream note:** Component fixes ship from the `lectio` npm package. This repo applies a `patch-package` patch when local changes are needed before the next Lectio release.
