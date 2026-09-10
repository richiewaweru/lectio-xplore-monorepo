# Phase J — Redesign Writers and Prompts

## Goal
Simplify LLM responsibilities so normal writing is flexible and only interaction payloads face strict behavior contracts.

## Open these active files first
- `apps/textbook-agent/backend/src/curriculum/prompts.py`
- `apps/textbook-agent/backend/src/print/generation/prompts.py`
- `apps/textbook-agent/backend/src/print/generation/whole_lesson/prompt_render.py`
- `apps/textbook-agent/backend/src/learn/generation/interaction_writer.py`
- `apps/textbook-agent/backend/src/learn/generation/activity_authoring.py`
- `apps/textbook-agent/backend/src/learn/generation/component_lectio/`
- `apps/textbook-agent/backend/src/core/prompts.py`

## Implementation tasks
- Teaching planner writes pedagogical meaning and learner tasks only.
- Path realizer chooses compact form sequence.
- Generic document writers author Paragraph/Heading/List/Table/Callout content; Figure uses the existing safe figure pipeline where appropriate.
- Interaction writer receives only the selected interaction's strict contract.
- Retry feedback is stage-local: composition errors go back to composer, interaction schema errors go back to that interaction writer.
- Delete old component-specific ordinary writer prompts/instructions after cutover.

## Expected outputs
- `document composition prompt`
- `generic document writing prompts`
- `retained interaction prompts only`
- `stage-local retry/error contracts`

## Acceptance gate
Normal prose/table/callout generation no longer fails because the model attempted to fill unrelated component-specific fields.
