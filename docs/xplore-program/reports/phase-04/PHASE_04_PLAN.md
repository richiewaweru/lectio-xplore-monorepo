# Phase 04 execution plan (fresh after Phase 03 PASS)

## Goal
Make `@lectio/learn` executable via deterministic interaction contracts; upgrade QuizCheck/FillInBlank; add a compact set of missing primitives with local evaluation; in-memory fixture completion.

## Approach
1. EXTEND existing `InteractionSpec` into a Learn interaction contract module (`interaction-contract.ts`) with evaluation result, attempt policy, hints, feedback, completion.
2. Add deterministic evaluators for choice / multi-select / fill-blank / numeric / match / sequence.
3. Upgrade QuizCheck + FillInBlank to emit/consume contracts (additive; keep existing content schemas).
4. Add only justified new primitives as pure evaluators + thin Svelte shells: MultiSelect, MatchPairs, Sequence, NumericInput (Choice reuses QuizCheck).
5. AI-config rule: authored config JSON only; no AI-generated executable UI.
6. Tests for serializable contracts + deterministic outcomes + in-memory lesson completion.

## Non-goals
No learner DB, no AI open-ended grading, no large simulation library.
