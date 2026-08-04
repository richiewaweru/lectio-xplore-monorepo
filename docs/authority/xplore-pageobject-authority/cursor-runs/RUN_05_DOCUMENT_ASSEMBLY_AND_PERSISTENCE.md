# Cursor Run 05 — Document Assembly and Persistence

## Goal

Build, validate, persist, reload, and resume a canonical `LectioDocumentV2` without legacy section-content construction.

## Work

1. Implement stable block IDs and normalization.
2. Assemble sections directly from planned blocks and writer outputs.
3. Assemble document metadata and version fields.
4. Validate with synced JSON Schema and backend semantic mirror.
5. Use the canonical persistence owner found in Run 00. Add a migration only if a blocker report proves no additive existing store is safe.
6. Persist per-block status needed for independent retry/resume.
7. Return discriminated v2 document from read API/serializer.
8. Add lifecycle tests: plan→write→assemble→persist→reload equality.
9. Add explicit test/trace proving no v2 call constructs legacy `SectionContent` or invokes legacy section builder.
10. Preserve v1 behavior and read path.

## Gate

One fixture lesson is a persisted valid v2 document; reload is normalized-equal; a failed writer resumes without regenerating successful blocks; v1 tests remain green.

## Commit

`feat(generation): assemble and persist lectio v2 documents`
