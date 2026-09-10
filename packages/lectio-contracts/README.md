# @lectio/contracts

The neutral instructional vocabulary shared by the Lectio **Print** (`@lectio/page`)
and **Learn** native paths.

This package deliberately owns *no* renderers, payload schemas or native
inventory, and has no Svelte, Python or renderer dependency. A planner, a backend
service and a test fixture can all depend on it.

## What lives here

| Surface | File | Ownership |
|---|---|---|
| Instructional intents (32 canonical ids) | `data/instructional-intents.v1.json` | **Authored** here (canonical) |
| Learner actions | `data/learner-actions.v1.json` | **Authored** here |
| Teaching view | `generated/teaching-view.v1.json` | **Generated** |
| Vocabulary manifest (versions + hashes) | `generated/manifest.json` | **Generated** |

Intent identifiers are canonical and are never renamed by native packages. To add
or change an intent, edit `data/instructional-intents.v1.json` and re-run the
exporter. Print adapts the same ids with `valid_objects` / generation guidance.

## Teaching view

`buildTeachingView()` returns the only vocabulary a shared teaching plan may use:
intent definitions, neighbouring-intent boundaries and learner actions.

Absent by design: page object ids, Learn component or interaction kind ids,
payload schemas, capacity or layout limits and payload examples. A teaching plan
that cannot name native inventory cannot pre-commit either native path.

`src/native-inventory.ts` holds the machine-checkable half of that boundary and
is asserted against by `tests/teaching-view.test.ts`.

## Commands

```bash
pnpm --filter @lectio/contracts export-contracts   # regenerate teaching view + hash
pnpm --filter @lectio/contracts test               # vocabulary, teaching view, regeneration gates
pnpm --filter @lectio/contracts check              # tsc --noEmit
pnpm --filter @lectio/contracts build              # dist/ for publication
```

Workspace consumers resolve the TypeScript sources directly; `publishConfig`
switches the exports to `dist/` for publication.
