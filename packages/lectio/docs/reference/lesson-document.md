# Lesson document interchange

Lectio defines a portable JSON format (`LessonDocument`) and helpers so **generators** (e.g. Textbook Generator) and **editors** (e.g. Lesson Builder) share one contract without depending on each other. Both consume only this package.

## Types and functions

Exported from `lectio` (see `src/lib/index.ts`):

| Export | Purpose |
| --- | --- |
| `LessonDocument`, `BlockInstance`, `DocumentSection`, `MediaReference` | Portable document shape (`version: 1`). |
| `DocumentValidationResult`, `FromSectionContentsMetadata` | Validation and conversion metadata. |
| `fromSectionContents(sections, metadata)` | Build a `LessonDocument` from pipeline `SectionContent[]`. |
| `toSectionContents(document)` | Rebuild `SectionContent[]` for rendering or `validateSection`. |
| `validateDocument(document)` | Structural checks + per-section capacity warnings via `validateSection`. |
| `getFieldComponentMap()` | Reverse of `getComponentFieldMap()`: `SectionContent` field name → component id. |
| `getEmptyContent(componentId)` | Placeholder content for a new block in an editor. |
| `getPreviewContent(componentId)` | Optional richer preview payload (may match empty today). |
| `getEditSchema(componentId)` | Form descriptor for builder UIs; `null` for components without a block field (e.g. `glossary-inline`). |
| `assertFactoriesCoverRegistry()` | Dev/test guard: every `getComponentFieldMap()` id has a factory. |

## Registry: teacher-facing metadata

`ComponentMeta` includes:

- `teacherLabel` — short palette label.
- `teacherDescription` — one-sentence teacher copy.

Source strings live in `src/lib/teacher/teacher-facing.ts` and are merged into each registry entry via `teacherFor(id)` in `src/lib/schema/registry.ts`.

## Contract export

`npm run export-contracts` emits `contracts/lectio-content-contract.json`, which includes planner and component-card metadata for external pipelines without importing TypeScript.

## Design notes

- Blocks are stored flat in `document.blocks` keyed by id; `DocumentSection.block_ids` defines order within a section.
- `DocumentSection.id` is stable and matches `SectionContent.section_id` when converting from pipeline sections (round-trip preservation).
- Block `content` is `Record<string, unknown>` at the interchange boundary; the component registry and types define the real shapes.
- `worked_example` / `worked_examples` and `pitfall` / `pitfalls` are folded into multiple `worked-example-card` / `pitfall-alert` blocks in document order; `toSectionContents` merges them back.

## Tests

- `src/lib/document.test.ts` — round-trip and `validateDocument`.
- `src/lib/content-factories.test.ts` — registry coverage and `getEmptyContent`.
- `src/lib/edit-schemas.test.ts` — every mapped component has a non-null edit schema.

## Related

- [registry-field-map.md](registry-field-map.md) — `sectionField` and exported JSON.
- [component-guide.md](component-guide.md) — public library surface.

