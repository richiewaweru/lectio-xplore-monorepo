## Phase 03 report — failure state and resume

### Files changed
- `src/planning/whole_lesson/repository.py` — claim guard refuses pending/rejected teaching review
- `src/planning/whole_lesson/worker.py` — failure stage uses lease.stage (not hard-coded writing_sections)
- `src/planning/whole_lesson/native_status.py` — exposes document_revision

### Behavior
- Worker claim cannot steal awaiting_teaching_approval / pending review checkpoints
- Failure transitions still synchronize generation.status + execution.last_error + events via repository.transition
- Resume still skips ready / visual_pending blocks via decide_resume

### Tests
Existing phase02 resume / worker failure / fencing suites: passed
