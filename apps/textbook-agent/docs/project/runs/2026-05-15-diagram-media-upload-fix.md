## Bugfix: Diagram media upload dead-end in FieldMedia

**Classification**: minor
**Root cause**: `FieldMedia.svelte` only rendered upload controls for `video-embed` and `image-block`, so diagram components showed a dead-end helper message and could not upload media directly.

### Progress
- [x] Reproduced the bug (or identified the failing code path)
- [x] Identified root cause
- [x] Implemented the fix
- [x] Added regression test
- [x] Ran validation
- [x] Self-reviewed the diff

### Validation Evidence
- `npx vitest run src/lib/builder/components/media/DiagramUploader.test.ts src/lib/builder/components/canvas/diagram-media-fields.test.ts src/lib/builder/utils/media-utils.test.ts`
  - Result: 3 files passed, 8 tests passed.
- `npm run check`
  - Result: `svelte-check found 0 errors and 0 warnings`.

### Risks
- Mapping from media fields to SVG sibling fields for diagram variants must remain aligned with Lectio schema (`before_media_id -> before_svg`, `after_media_id -> after_svg`, series `media_id -> svg_content` in item rows).
