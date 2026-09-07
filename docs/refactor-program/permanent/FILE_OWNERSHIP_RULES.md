# File Ownership Decision Rules

For every file/module, ask in order:

## 1. Would it exist if only curriculum planning existed?
If yes → `curriculum/`.

## 2. Would it exist if only Print existed?
If yes → `print/`.

Examples:
- page form planner
- page writer
- page object
- PDF export
- page figure brief
- print resource candidate

## 3. Would it exist if only Learn existed?
If yes → `learn/`.

Examples:
- component selector
- interaction writer
- Builder
- LearnRelease
- learner runtime
- assignment
- class analytics
- Learn component resource candidate

## 4. Would both Print and Learn need essentially the same implementation?
If yes → `platform/`.

Examples:
- DB session
- provider client
- retry/backoff utility
- telemetry sink
- blob storage primitive

## 5. Is it ambiguous because it combines multiple responsibilities?
Do not guess.
- split only if behavior can remain unchanged,
- otherwise leave in place temporarily,
- document as `NEEDS_SEAM_EXTRACTION`.

## Prompts

Prompts follow the product path that consumes their output.
Never place final prompts in platform/shared.

## Models

Domain model placement follows ownership, but shared SQLAlchemy Base and migration infrastructure remain platform-level.
A phased model split may use import/re-export shims temporarily if moving all models at once would create migration risk.
