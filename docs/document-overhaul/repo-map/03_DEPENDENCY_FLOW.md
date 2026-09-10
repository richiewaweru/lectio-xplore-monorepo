# Dependency Flow to Protect

## Allowed target dependencies

```text
curriculum / teaching
        │
        ▼
application.unit_lesson
        │
        ├───────────────┐
        ▼               ▼
      print            learn
        │               │
        ▼               ▼
 @lectio/page       app-owned interaction UI/contracts
```

A small neutral document-vocabulary module may be consumed by both Print and Learn.

## Forbidden target dependencies

```text
print  ─X─→ learn
learn  ─X─→ print

teaching plan ─X─→ native form ids
teaching plan ─X─→ interaction component ids
teaching plan ─X─→ page layout ids

document primitive ─X─→ pagination rule
document primitive ─X─→ browser breakpoint
document primitive ─X─→ interaction scoring implementation
```

## Desired semantic boundary

```text
Teaching Plan says:
"learner classifies inputs and outputs"

Print says:
"realize that as a paper classification task"

Learn says:
"realize that as Classify/Sort"

Teaching Plan never says:
"SortCards"
```

## Current high-risk couplings to remove

- `learn/generation/native_selection.py` currently selects both content capability IDs and interaction IDs.
- `learn/generation/component_lectio/*` depends on component cards, payload strategies, SectionContent payload validation, and lane dispatch.
- `learn/contracts/lesson_document.py` requires `component_id` and `template_id`.
- `packages/lectio-learn` combines teaching components, interaction components, editor utilities, templates, generated AI contracts, and Print mode.
- `packages/lectio-learn/src/lib/print/RuledLines.svelte` is Print behavior living inside Learn.
- `@lectio/contracts` currently projects canonical intents from `@lectio/page`; intent ownership should move to the shared layer.
