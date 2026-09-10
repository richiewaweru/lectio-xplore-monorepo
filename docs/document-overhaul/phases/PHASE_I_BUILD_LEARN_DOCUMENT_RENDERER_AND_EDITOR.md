# Phase I — Build Learn Document Renderer and Editor

## Goal
Give the new LearnDocument the Kira-like smooth editing surface: click ordinary content, edit it directly, reorder it, insert nodes, and locally regenerate.

## Open these active files first
- `apps/textbook-agent/frontend/src/lib/learn/student/StudentLessonShell.svelte`
- `apps/textbook-agent/frontend/src/lib/learn/student/OrderedBlockList.svelte`
- `apps/textbook-agent/frontend/src/lib/learn/student/student-shell.ts`
- `apps/textbook-agent/frontend/src/lib/learn/authoring/`
- `apps/textbook-agent/frontend/src/lib/learn/authoring/builder/api/lesson-crud.ts`
- `apps/textbook-agent/frontend/src/lib/learn/authoring/workspace/lesson-state.ts`
- `apps/textbook-agent/frontend/src/routes/learn/lessons/[id]/+page.svelte`
- `apps/textbook-agent/frontend/src/routes/learn/instances/[instanceId]/+page.svelte`

## Implementation tasks
- Render Paragraph, Heading, List, Figure, Table and Callout directly from the canonical LearnDocument.
- Add inline editing for text content and structured cell/item editing for tables/lists.
- Support add/delete/reorder using stable node IDs.
- Add local node or section regeneration without rebuilding unrelated content.
- Render retained Interaction nodes through the dedicated interaction renderer.
- Keep runtime attempt state separate from ordinary document content.
- Do not create a second editor-only document representation.

## Expected outputs
- `frontend/src/lib/learn/document/...`
- `updated builder/editor state`
- `updated student shell/ordered renderer`
- `frontend unit/component tests`

## Acceptance gate
A teacher can generate, edit, add, delete, reorder, save, reload and preview a mixed Learn lesson without any legacy content-component edit form.
