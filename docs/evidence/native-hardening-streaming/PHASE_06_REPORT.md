## Phase 06 report — viewer SSE/PDF gates

### Files changed
- `src/planning/whole_lesson/native_status.py` — document_revision
- `src/generation/v3_studio/router.py` — doc_version = `rev:{document_revision}` for native
- `frontend/src/routes/studio/+page.svelte` — failed_recoverable/terminal hydrates last-good document + shows error

### Behavior
- Studio already polls through writing_* / awaiting_visuals and refreshes when doc_version changes
- SSE remains a poke for legacy streams; native path relies on polling (survives SSE loss by design)
- PDF FIGURES_NOT_READY gate unchanged and covered by existing tests
- Pending figure placeholder remains in page_objects/views.py

### Tests
Phase 06 doc_version unit + visual PDF routes: passed
