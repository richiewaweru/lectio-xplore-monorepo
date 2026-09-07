# PHASE 05 REPORT — Student Preview + Explicit Immutable Publishing (coverage closeout)

Status: **PASS**

## What was implemented
1. Immutable `LearnRelease` publish with SHA-256 `document_hash` (existing).
2. Additive provenance: `path_lesson_revision`, `objective_hash` (+ migration `20260906_0038`).
3. Publish resolves PathLesson when `path_lesson_id` is supplied (or via generation→pack→LessonProvenance); **requires** revision + objective_hash for unit-path; manual drafts remain null.
4. Student preview `/learn/lessons/[id]` uses the same `StudentLessonShell` with `preview` flag (`data-persist-attempts=false`); attempts only exist on `/instances/{id}/attempts`.

## Tests
| Command | Result |
|---|---|
| `uv run pytest tests/routes/test_learn_releases.py` | PASS (immutable v1/v2, manual null provenance, unit-path required fields, preview surface) |

## Acceptance gates
- [x] Edit → student preview + publish
- [x] Post-publish edit does not mutate prior release
- [x] Unit-path provenance required / manual null
- [x] Preview does not expose attempt write surface
- [x] LessonShare unused as release

## Deviations
None material.

## Safe to proceed: YES
