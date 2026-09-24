# Database and Persistence Plan

## Migration strategy

Build additively, prove, cut over, then promptly remove obsolete schema. This provides operational rollback without committing to backwards compatibility.

## Add

Likely:

- generation_builds
- generation_runs
- generation_work_items
- generation_events
- shared_lesson_documents
- model-call trace extensions if needed

## SharedLessonDocument storage

Prefer explicit identity/revision/hash columns plus typed JSON aggregate:

```text
id
path_lesson_id
revision
teaching_plan_id
teaching_plan_revision
teaching_plan_hash
content_hash
document_json
created_at
```

Avoid SQL-normalizing every paragraph/callout before an editing/query requirement exists.

## Cleanup

After all current callers migrate and backups exist, remove obsolete path-specific state, old blobs/columns/tables and compatibility identifiers.

Do not combine “first production cutover” and irreversible legacy-column drops in one migration.
