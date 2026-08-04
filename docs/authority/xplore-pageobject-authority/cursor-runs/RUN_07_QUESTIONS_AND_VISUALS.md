# Cursor Run 07 — Question Wall and Stable Visual Completion

## Goal

Integrate asynchronous questions/media without breaking page order or product invariants.

## Work

1. Trace item-generation inputs and add a test that generated lesson prose cannot enter them.
2. Map planned question source IDs to canonical item records.
3. Preserve answer references and teacher/student policy.
4. Trace visual request lifecycle.
5. Store a pending figure block before generation completes.
6. Update only the figure asset payload on success/failure.
7. Ensure block ID, intent, object, position, caption, and alt text remain stable.
8. Add resume and concurrent-completion tests.
9. Verify async completion never changes section array order.

## Gate

Question wall test green. Pending→ready and pending→failed figures preserve stable block identity/order. Reload reflects final state.

## Commit

`feat(generation): preserve question wall and visual positions`
