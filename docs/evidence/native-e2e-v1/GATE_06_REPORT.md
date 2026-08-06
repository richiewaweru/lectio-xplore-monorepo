# Gate 6 — Parallel section execution

## Pass

Execution is section-oriented with `MAX_SECTION_CONCURRENCY = 4`; resume skips ready/visual_pending work.

## Changes

- State `writing_sections` added to `LEGAL_TRANSITIONS` / `ACTIVE_STATUSES` / `NATIVE_STATUSES`.
- `writing_blocks` retained as compatibility alias.
- `planning_forms → writing_sections` preferred transition.
- `write_form_blocks` runs one job per section under a section semaphore; within-section block concurrency still bounded by `MAX_WRITER_CONCURRENCY`.
- `ContentValidationError` classified as VALIDATION without executor re-repair.
- Successful outcomes persist `answer_entries`.

## Tests

- `tests/planning/test_parallel_section_execution.py` — out-of-order finish, peak ≤ 4, canonical keys
- `tests/planning/test_section_resume.py` — completed sections skipped
- Existing phase02 resume/isolation tests remain green
