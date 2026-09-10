# Verification Matrix

## Baseline before edits

From repo root:

```bash
pnpm contracts:test
pnpm contracts:check
pnpm page:test
pnpm page:check
pnpm app:test
pnpm app:check
pnpm program:domain-guards
```

From `apps/textbook-agent/backend`:

```bash
uv run python tools/agent/validate_repo.py --scope backend
uv run python ../tools/agent/check_architecture.py --format text
```

If a command is stale/broken on the inspected baseline, record it honestly before changing anything.

## New architecture test cases

| Case | Required proof |
|---|---|
| Passive prose lesson | Heading + Paragraph sequence |
| Visual explanation | Figure mixed with prose |
| Comparison | Table selected for genuine relation |
| Key warning | Callout used intentionally |
| List-worthy content | List rather than paragraph stuffing |
| Mixed content | all primitive order preserved |
| Learn Choice | generate → render → answer → evaluate → reload |
| Learn FillBlank | same |
| Learn Classify/Sort | same |
| Learn Match | same |
| Learn Sequence | same |
| Other retained interaction | same |
| Learn local edit | change one node only |
| Learn local regenerate | replace one node/section only |
| Learn persistence | save → process restart/reload → identical content |
| Print written task | response space/ruled lines downstream |
| Print comparison | paper-appropriate table/layout |
| Print PDF | persisted doc → reload → PDF |
| Learn then Print | sibling generated from Teaching Plan, not Learn artifact |
| Print then Learn | sibling generated from Teaching Plan, not Print artifact |
| recoverable composer error | retry only correct stage |
| recoverable interaction schema error | feedback only selected interaction writer |
| deleted legacy route | cannot be reached |

## Quality assertions

- The composer must not decorate every section with tables/callouts.
- Learn must not insert an interaction merely because the path is Learn.
- The Teaching Plan must retain learner-task fidelity.
- Figure selection must reflect actual visual/spatial/process need.
- Stable node IDs survive normal edits.
- Interaction state must not be embedded into normal prose node content.
- Print page concerns do not leak into shared/learn code.
