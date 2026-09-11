# Locked Decisions

## Learner actions are broader than assessment

`learner_action` means: **this point in the lesson benefits from the learner doing something observable**.

It can support retrieval, prediction, discrimination, classification, sequencing, application, misconception surfacing, guided practice, reflection, or formal/informal checking.

It is not limited to check sections and is not synonymous with mastery evidence.

Every Learn interaction must correspond to an intentional learner action. Do not add interactivity merely because the path is Learn.

## Teaching Plan ownership

The Teaching Plan remains path-agnostic:

```text
learner_action
├── action
├── target
├── purpose
├── expected_evidence
└── difficulty
```

It must never name Learn interaction kinds, Print treatments, page objects, layouts, components, or renderers.

## Evidence is broad

`expected_evidence` can describe a prediction, current belief, classification, recalled fact, application, explanation, calculation, sequence, or mastery evidence. The learner does not always need to be correct for the action to be useful.

## Mutable intelligence lives outside code

```text
MARKDOWN
  What should the model think about?
  What counts as good instruction?
  When should it choose one behavior over another?

YAML / JSON
  What options exist?
  What stable mappings/candidates are legal?

CODE
  What must always be structurally true?
  Validation, persistence, evaluation, transactions, rendering algorithms.
```

Do not hardcode pedagogical philosophy in Python/TypeScript unless it is a true invariant.

## Shared ordinary writing

Both Print and Learn should use the shared ordinary document authoring layer for Paragraph, Heading, List, Figure, Table, and Callout. They may call it independently; they do not need to share the same generated text instance.

Print-only page objects/treatments happen after ordinary content has been authored.

## Twin task realization

```text
Teaching Plan action = select-one
        │
        ├── Learn → choice
        └── Print → choices
```

The two paths may render differently but must not independently invent whether a learner task exists.

## Symmetric path realization

The Unit flow should expose the same conceptual shape for `realize-learn` and `realize-print`. Studio/Builder are artifact workspaces, not the mechanism that decides whether the path exists.

## Path-local editing

Editing the Teaching Plan affects future realizations. Editing a Learn artifact affects only that Learn realization. Editing a Print artifact affects only that Print realization.

## Section structure survives realization

Final Learn documents must preserve section identity/order/title/transition metadata for tabs, section-local editing/regeneration, analytics, and future adaptation.

## Silent degraded generation is forbidden

If composition falls back to heuristics, persist/emit `composition_mode = heuristic_fallback`. Normal live acceptance should prove the LLM composition path, not silently pass through fallback.
