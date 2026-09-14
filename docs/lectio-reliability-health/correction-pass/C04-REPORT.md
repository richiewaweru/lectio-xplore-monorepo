# C04 Report

## Changes

- Interaction writer accepts budget_ledger/checkpoint_store/durable_persist_hook/progress; checkpoint reuse with compat
- Figure pipeline reserves budget slots before `execute_visual`, marks dispatched/ambiguous, emits media_attempt events
- Per-item `on_item_committed` durable persist from Learn production loop

## Tests

Covered by correction_pass + existing reliability suite (32+ in reliability/admission batch).

## Gate

PASS — interaction/media/document share the execution contract; deterministic convert-approved still uses engine without inventing LLM slots for non-generate paths.
