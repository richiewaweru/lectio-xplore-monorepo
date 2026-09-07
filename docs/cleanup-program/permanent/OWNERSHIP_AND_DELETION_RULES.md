# Ownership + Deletion Rules

Classify every meaningful path as one of:
- ACTIVE_PRODUCT
- ACTIVE_INFRA
- ACTIVE_BUILD
- ACTIVE_TEST
- MIGRATION_HISTORY
- AUTHORITATIVE_DOC
- SPLIT_REQUIRED
- LEGACY_REFERENCED
- DEAD

## DEAD criteria
Delete only when:
1. no mounted production route reaches it,
2. no Unit-path call graph reaches it,
3. no current package export requires it,
4. no build/deploy script requires it,
5. no migration-history role requires it,
6. no authoritative current test/fixture requires it,
7. no authoritative documentation requires it.

Legacy-only tests are not a reason to preserve an unsupported product path. If implementation and tests are both detached from the supported product, remove both.

## Split rule
Mixed modules should be split by durable ownership.

Example:
```text
planning/prompts.py
→ curriculum/teaching_plan/prompts.py
→ print/generation/prompts/form_plan.py
→ learn/generation/prompts/experience_plan.py
```

## Duplication rule
Intentional thin duplication is acceptable when it removes Print/Learn coupling. Prefer two surface-owned writers over one mode-switching writer.

## Database exception
Old migrations are not dead code. Do not delete migration history during this cleanup.
