# P6 — Canonical frontend state implementation

Status: Implementation complete; awaiting Sol gate review. P6 is not marked accepted yet.

## Changes

- Added typed preparation states, review kind, verified approval identity, typed artifact errors/recovery actions, and compatibility/debug annotations to the Unit status DTO.
- Replaced worker-stage/output-pointer inference in `lesson-context.ts` with canonical workspace mapping. Any status object missing workspace data is explicitly ambiguous; it cannot borrow Learn/Print identities from raw fields or another path.
- Unit lesson header and overview use canonical preparation badges and state. Unit dashboard prepare/reprepare and realization actions require fresh status; realization Create additionally requires verified approval. Refresh failures surface while the cached payload is retained but considered stale.
- Plan phase follows canonical preparation and review kind before loading structural worker details. It uses only canonical generation identity, error retryability, and artifact retryability. A downstream ready/failure stage cannot override canonical review or failure state.
- Learn and Print Create controls require fresh verified approval. Artifact identity, status polling, and retry eligibility use only the corresponding path projection. Print polling no longer treats preparation worker activity as Print activity, and queued guidance only asks teachers to refresh; Retry appears only for canonical recoverable failures.
- Preview fetch failure is separate from realization failure: a ready Print path remains ready and offers no realization retry. `LessonIssuesPanel` only renders an execution retry when the caller passes canonical retryability.
- Studio generation editor/output routes remain unchanged and keep their output-level status behavior.

## Validation

From `apps/textbook-agent/frontend`:

```powershell
npm test -- src/lib/curriculum/lessons/lesson-context.test.ts src/routes/units/[id]/page.test.ts 'src/routes/units/[id]/lessons/[lessonId]/plan/page.test.ts' 'src/routes/units/[id]/lessons/[lessonId]/learn/page.test.ts' 'src/routes/units/[id]/lessons/[lessonId]/print/page.test.ts' src/routes/studio/page.test.ts
```

Result: 6 files passed, 73 tests passed. Coverage includes every canonical preparation state; contradictory worker stages and output pointers; verified approval surviving downstream failure; Learn/Print independence; missing-workspace ambiguity; explicit retryability; Unit overview status-refresh errors; Plan review-kind/failure precedence; fresh approval Create gates; Print ready-document preview failure and queued-state no-retry guidance; and Studio regression behavior.

```powershell
npm run check
```

Result: exit 0, 0 errors, 5 existing Svelte warnings in `InteractionEditor.svelte`, `DocumentCanvas.svelte`, `DocumentEditor.svelte`, and `PrintDocumentEditor.svelte` (all outside P6 edits).

```powershell
npm run build
```

Result: exit 0. Existing warnings remain for those editor components. Vite reports optional dependencies not found for `canvas`, `bufferutil`, `utf-8-validate`, and `supports-color`; adapter reports completion.

From repository root:

```powershell
git -c core.whitespace=cr-at-eol diff --check
```

Result: passed for the tracked diff. P6 added no backend product changes. Existing unrelated `.gitignore` and diagnosis-note edits remain untouched.

## Sol review

Pending. Sol approved the read-only inventory/design and authorized this bounded implementation. P6 remains unchecked until the final frontend diff and evidence are accepted.
