# Phase G — Rationalize Learn Interactions

## Goal
Keep only actual learner behaviors that deserve strict contracts and delete unsupported interaction/media complexity.

## Open these active files first
- `apps/textbook-agent/backend/src/learn/generation/interaction_writer.py`
- `apps/textbook-agent/backend/src/learn/generation/activity_authoring.py`
- `apps/textbook-agent/backend/src/learn/runtime/`
- `packages/lectio-learn/src/lib/learn/`
- `packages/lectio-learn/src/lib/learn/capabilities/`
- `packages/lectio-learn/contracts/`

## Implementation tasks
- Inventory the currently supported interactions and classify KEEP / DELETE.
- Prefer a small first set: Choice, MultiSelect if genuinely distinct, FillBlank, Classify/Sort, MatchPairs, Sequence, Numeric, ShortResponse only if current runtime/evaluation is sound.
- Delete image-hotspot, drag-label, image-choice, simulations, video and other unsupported asset-heavy behavior for now unless a live requirement proves otherwise.
- For every retained interaction, keep one strict payload contract, one writer path, one validator, one frontend renderer, and one evaluator/attempt contract.
- Move retained interactions out of the old general teaching-component package boundary if that package is being retired.

## Expected outputs
- `retained interaction registry`
- `interaction-specific contracts/writers/validators`
- `interaction E2E fixtures`
- `explicit deleted-interaction list`

## Acceptance gate
Every retained interaction can be generated, validated, rendered, answered, evaluated and reloaded. No deleted interaction remains selectable or importable from active production code.
