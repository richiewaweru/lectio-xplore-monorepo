## Phase 04 report — durable native streaming

### Files changed
- `src/planning/whole_lesson/repository.py` — `persist_streaming_snapshot` (revision bump only on material change; no final fence)
- `src/planning/whole_lesson/executor.py` — `publish_streaming_snapshot`; called after each section; stable `document_id`

### Behavior
- After a section's blocks reach ready/visual_pending, DB is re-read and a valid partial LectioDocumentV2 is persisted
- Section order is canonical plan order among ready sections
- Partial snapshots never set final SHA/reload proof
- Final `assemble_from_db` still performs exact key-set validation + fresh-session reload fence
- Document id stable across streaming revisions (`doc-{generation_id}` or prior id)

### Tests
- New streaming event tests + existing assemble/fence/resume suites: passed
