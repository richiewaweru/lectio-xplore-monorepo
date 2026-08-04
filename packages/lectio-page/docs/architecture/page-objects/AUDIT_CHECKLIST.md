# Claude Audit Checklist

Audit the pack against these non-negotiable questions.

## Fork integrity

- Is the new package genuinely fresh?
- Does any v2 code import legacy Lectio?
- Is coexistence implemented by document version rather than conversion?
- Is there any hidden migration proposal?

## Intent quality

- Are there approximately 30 useful intents?
- Does each intent carry pedagogical role and cognitive job?
- Are intents meaningfully distinct?
- Is object-intent compatibility explicit?
- Has the catalogue retained the pedagogical richness previously carried by component names?
- Does any intent recreate a renderer or component?

## Object discipline

- Are there exactly ten initial objects?
- Is every page behavior keyed to object rather than intent?
- Is `aside` the only boxed object?
- Are table, worked-example, questions and choices explicitly unboxed?
- Is heading bound to the first following block?

## Print geometry

- Is float-based scholar's margin used?
- Is CSS grid rejected for fragmented page flow?
- Does root language propagate?
- Are table headers repeated?
- Are figures and captions atomic?
- Are questions protected from internal splitting?
- Is the stylesheet positive-rule-only?
- Is meaning photocopy-safe?

## Backend fork

- Does planner output object + intent + position?
- Has `section_field` disappeared from v2?
- Has `component_id` disappeared from the v2 resource path?
- Is `block_ready` idempotently merged into ordered arrays?
- Are writers retained rather than rebuilt?
- Are streaming, retries, tracing, resume, image pipeline and PDF machinery untouched?

## Hedging detection

Reject the pack if it proposes:

- an adapter shim;
- dual internal representations for v2;
- saved-document migration;
- a renderer fallback to legacy components;
- a generic `legacy_payload` escape hatch;
- boxes for visual appeal;
- changing the PDF engine before testing the new document model.

## Final verdict format

```text
PASS
or
REVISE: <specific blocking changes>
or
REJECT: <architectural contradiction>
```
