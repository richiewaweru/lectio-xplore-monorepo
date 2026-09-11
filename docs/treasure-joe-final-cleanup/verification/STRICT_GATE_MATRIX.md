# Strict Gate Matrix (Treasure Joe)

## A — learner action
- [x] YAML authoritative
- [x] unknown action repairs/rejects
- [x] alias resolves
- [x] every canonical non-passive action has intentional Learn realization
- [x] every canonical non-passive action has intentional Print realization
- [x] fresh plan contains no unknown action
- [x] `describe-in-own-words` resolved intentionally

## B — interaction selection
- [x] no LLM call for one candidate
- [x] bounded LLM call for multi-candidate case if supported
- [x] selector sees only legal candidates + pedagogical context
- [x] selected result validated
- [x] selection mode recorded
- [x] no dead prompt-as-hash behavior

## C — v1 cleanup
- [x] no active `build_closed_learn_production`
- [x] no active v1 ordinary host remap
- [x] no primitive→`explanation-block` conversion
- [x] old tests migrated to v2
- [x] historical references classified

## D — exact Learn E2E
- [x] fresh Unit
- [x] natural Teaching Plan
- [x] normal approval
- [x] Unit Generate Learn
- [x] canonical realize-learn
- [x] LearnDocument v2
- [x] composition_mode=llm
- [x] Builder opens
- [x] natural interaction
- [x] submit/evaluate
- [x] attempt persists/reloads

## E — exact Print PDF
- [x] native Print artifact
- [x] marker saved
- [x] revision increments
- [x] reload marker
- [x] stale revision 409
- [x] actual PDF obtained
- [x] marker in actual PDF
- [x] Learn sibling unchanged

## F — repository health
- [x] pnpm contracts:test
- [x] pnpm contracts:check
- [x] pnpm page:test
- [x] pnpm page:check
- [x] pnpm app:test
- [x] pnpm app:check
- [x] pnpm program:domain-guards
- [x] relevant backend tests
- [x] architecture validation
- [x] zero-legacy checks
- [ ] tracking uses actual SHA *(stamped after implementation commit)*
- [ ] independent verifier = YES
- [ ] validate_repo full backend *(FAIL — pre-existing ruff/planning debt)*

Final state is only:

```text
NOT READY
```

Reason: Phase F `validate_repo` not green; independent verifier required before merge.
