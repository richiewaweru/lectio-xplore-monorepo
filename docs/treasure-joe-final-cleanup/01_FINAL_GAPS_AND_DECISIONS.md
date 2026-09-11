# Final Gaps and Locked Decisions

## 1. Learner-action vocabulary closes at planning time

`learner-actions.yaml` remains authoritative.

```text
planner emits action
   ↓
resolve canonical action / alias from YAML
   ↓
known → continue
unknown → structured planner repair/retry
```

Do not create a duplicated Python enum.

Resolve `describe-in-own-words` deliberately:
- alias it to `enter-text`, or
- require planner to emit `enter-text` while "describe in own words" lives in target/purpose.

Every non-passive canonical action must have an intentional downstream realization.

## 2. Interaction selection is truthful

```text
one legal interaction
→ deterministic; no LLM call

2+ legal interactions
→ bounded LLM selector using interaction-selection.md
→ validate result is in supplied candidates
```

If there is no meaningful multi-candidate case yet, remain deterministic and stop claiming an active LLM selection stage.

## 3. Exact Unit Learn proof

Required:

```text
fresh Unit
→ Teaching Plan
→ approval
→ Generate Learn from Unit UI
→ realize-learn
→ LearnDocument v2
→ Builder
→ naturally generated interaction
→ submit/evaluate
→ persisted/reloaded attempt
```

No manual learner-action injection, seed-to-Builder substitute, or DB patch.

## 4. Exact Print PDF proof

Required:

```text
native Print artifact
→ edit unique marker
→ save revision
→ reload marker
→ export/download actual PDF
→ inspect PDF
→ marker present
```

"PDF export started" is not proof.

## 5. Repository health

Must run:

```bash
pnpm contracts:test
pnpm contracts:check
pnpm page:test
pnpm page:check
pnpm app:test
pnpm app:check
pnpm program:domain-guards
```

plus relevant backend/architecture gates.

## 6. Legacy v1 salvage path

Remove the remaining executable v1 Learn ordinary-content salvage/test path where it remaps primitives to old component IDs.

Historical migrations may remain when genuinely historical.

## 7. Tracking finality

Final tracking must contain real SHA values, not `pending-commit`.

Run independent verification after the implementation commit. Do not merge before that.
