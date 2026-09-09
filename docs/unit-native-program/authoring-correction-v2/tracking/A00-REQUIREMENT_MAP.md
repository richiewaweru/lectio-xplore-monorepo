# A00 Requirement Map

## Sources Reviewed

- `docs/unit-native-program/COMMAND_MAP.md`
- `docs/unit-native-program/authoring-correction-v2/ARCHITECTURE.md`
- `docs/unit-native-program/authoring-correction-v2/SOURCE_MAP.md`
- `docs/unit-native-program/authoring-correction-v2/acceptance/POLICY.md`
- `docs/unit-native-program/authoring-correction-v2/acceptance/KNOWN_ANSWER_CASES.json`
- `docs/unit-native-program/authoring-correction-v2/phases/A00.md`

## Requirements To Files

| Requirement | Production files | A00 regression tests |
| --- | --- | --- |
| Preserve independent answers for numeric, fill-blank, and choice items; never derive correctness from first number, last word, or first option. | `apps/textbook-agent/backend/src/learn/generation/interaction_writer.py`, `apps/textbook-agent/backend/src/learn/generation/work_orders.py` | `apps/textbook-agent/backend/tests/authoring_correction/test_a00_arbitrary_answers.py` |
| Keep coverage for all core 8 Learn interactions: choice, multi-select, fill-blank, numeric, short-response, match-pairs, classify, sequence. | `apps/textbook-agent/backend/contracts/learn-capabilities.v1.json`, `apps/textbook-agent/backend/contracts/learn-writer-view.v1.json`, `apps/textbook-agent/backend/src/learn/generation/interaction_writer.py`, `packages/lectio-learn/src/lib/learn/capabilities/interactions.ts` | `test_a00_arbitrary_answers.py` directly exposes choice, fill-blank, numeric; existing P06/P07 gates cover runtime shape and parity for the other core interactions. Later A01+ fixes must extend authoring semantics across all eight. |
| Content authoring must generate final content, not copy the planning brief as lesson body. | `apps/textbook-agent/backend/src/learn/generation/ordered_assemble.py`, `apps/textbook-agent/backend/src/learn/generation/native_production.py`, `packages/lectio-learn/src/lib/learn/capabilities/views.ts` | `apps/textbook-agent/backend/tests/authoring_correction/test_a00_brief_as_content.py` |
| Print table provider failure must surface a typed failure after bounded repair; it must not fall back to a fixed Lit leaf/Covered leaf table. | `apps/textbook-agent/backend/src/print/rendering/page_objects/registry.py`, `apps/textbook-agent/backend/src/print/rendering/page_objects/validation.py`, `apps/textbook-agent/backend/src/print/generation/whole_lesson/executor.py` | `apps/textbook-agent/backend/tests/authoring_correction/test_a00_print_table_fallback.py` |
| Learn content selection must be semantic and closed-set validated, not hard-coded to `content_candidates[0]`. | `apps/textbook-agent/backend/src/learn/generation/native_selection.py`, `apps/textbook-agent/backend/src/learn/resources/selection.py`, `apps/textbook-agent/backend/contracts/learn-selection-view.v1.json` | `apps/textbook-agent/backend/tests/authoring_correction/test_a00_first_content_selection.py` |
| Fallback candidates must still honor budgets; exhausted candidates remain excluded when fallback logic runs. | `apps/textbook-agent/backend/src/learn/resources/selection.py`, `apps/textbook-agent/backend/src/print/resources/selection.py` | `apps/textbook-agent/backend/tests/authoring_correction/test_a00_fallback_budget.py` |

## Generation-Enabled Learn Content

Generation-enabled Learn content must eventually route through scoped authoring definitions and provider-backed writing, analogous to Print writers. Current baseline assembly creates body-like content directly in `ordered_assemble.py`, including `explanation-block`, `callout`, `key-concept`/`key-fact`, `summary-block`, `section-header`, and `hook-hero` shapes. A00 only records and tests the defect; A01+ should connect selected Learn content work orders to real content authoring.

## Core 8 Interaction Expectations

- `choice`: correct option must name a declared option; invalid source keys fail rather than selecting the first option.
- `multi-select`: correct ids must come from independently supplied answer relationships, not the first N options.
- `fill-blank`: accepted answers must come from supplied answer data or provider-authored final config, not the last token of the brief.
- `numeric`: expected value must come from supplied answer data or provider-authored final config, not the first number in the prompt.
- `short-response`: teacher-review prompts must remain review-only when answers cannot be enumerated.
- `match-pairs`: pair relationships must preserve supplied relationships while presentation may shuffle.
- `classify`: categories and mappings must be supplied/authored meaningfully, not invented as Category A/B alternation.
- `sequence`: accepted order must preserve supplied order while presentation may shuffle.
