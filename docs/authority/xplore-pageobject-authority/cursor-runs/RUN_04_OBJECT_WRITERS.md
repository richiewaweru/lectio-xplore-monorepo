# Cursor Run 04 — Object-Specific Writers

## Goal

Generate canonical content for every first-slice object without allowing writers to re-plan.

## Work

1. Create `generation/page_objects` module and immutable writer context.
2. Install common and per-object prompts from this pack.
3. Implement typed writer agents for prose, list, table, worked-example, and figure brief.
4. Implement questions as a deterministic assembler from existing item records.
5. Add dispatcher keyed only by the fixed planned object.
6. Add validation feedback retries using existing retry policy; maximum one application-level correction unless current standards dictate otherwise.
7. Add tests for valid output, extra fields, capacity, scope, terminology, wrong object, duplicate work, and question wall.
8. Preserve complete educational content; no truncation repair.

## Gate

Every object fixture produces content accepted by canonical backend contract models. Writer cannot change plan. Questions assembler has no prose/brief input. Figure output is a valid pending block with stable request ID.

## Commit

`feat(generation): write native page-object content`
