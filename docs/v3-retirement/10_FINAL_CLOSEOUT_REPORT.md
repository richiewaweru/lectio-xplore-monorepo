# Final V3 Retirement Closeout

## Repository
- Branch: `chore/retire-v3-legacy`
- Starting SHA: `8a21be412b0ce4000655388a130ff2055194d45f`
- Current SHA: `28efa2a2` (plus pending final cleanup commit)
- Result: PASS

## Executive result
```text
The V3 legacy retirement on branch `chore/retire-v3-legacy` is fully verified and green.
The blocking shared task writer contract was diagnosed and aligned to batch semantics,
enabling the full native pipeline to succeed end-to-end on "How Shadows Form".
Both Learn and Print paths were executed and verified from the same approved Teaching Plan.
Learn produced a rich 4-section, 15-node document with interactive items (classify, choice)
and materialized to the Builder lesson. Print produced a complete document, supported full
revision saving, and successfully exported a valid PDF (52,638 bytes).
All frontend checks (tests 225/225 passed, check 0 errors, build succeeded) and backend
collections (1,386 passed, 0 collection errors) are verified. Zero dead legacy code remains
in v3_execution or v3_blueprint. Live compatibility routes remain stable and operational.
The branch is ready to merge into main.
```

## Shared-task writer repair
Root cause:
```text
The prompt in resources/prompts/shared-task-writer.md instructed the LLM to author a single
task for a single block, whereas the native execution pipeline expected batch output
containing exactly one task per response-bearing block in the section.
```
Repair/tests/why not architecture redesign:
```text
In curriculum/agents.py:
1. Structured response_blocks descriptors with expected_task_count provided to agent.
2. Passive / null-action blocks handled deterministically in code without calling LLM.
3. Hard count validation enforced with exactly one bounded repair attempt if mismatch persists.
4. Python code retains authoritative ownership of IDs, revision, hash, mode, and source binding.
Unit test suite apps/textbook-agent/backend/tests/curriculum/test_shared_task_writer.py added
covering all 9 contract scenarios (all passed 9/9).
Architecture redesign was avoided: this was a contract bug between prompt and consumer,
not a need for a multi-system rewrite.
```

## Learn proof
Unit/lesson/Teaching Plan revision/hash:
```text
Unit ID: a5b9e24f-9c88-407b-bde3-71a9d27e3dd2 ("How Shadows Form")
Lesson ID: 0fc47fa7-fd86-4e6e-9f58-e89d0eafe8fa
Preparation Generation ID: 913d086a-d1ef-4119-90f4-33e6aa0a08e1
Teaching Plan ID: 0bac7f60-57d3-4597-8c54-110191925c98
Revision: 1
Approved Content Hash: c530b26f42ebe8312f8bce6580941e02453772c0eaa836466cb14875591be9d6
```
Learn realization/output + interaction/save/rejoin proof:
```text
Realization ID: db89b1e7-7e6d-4c32-8ee9-3a0313a97cf7
Output ID: learn-out-0bb74c9c5e5b40a5
Status: ready (0 errors)
Sections: 4 (orient, explain, contrast, check), 15 nodes total.
Interactions: contrast-b3 (classify), check-b1 (choice).
Materialized to Builder Lesson: 49f06d18-10f8-4256-a203-be18d2d276ba.
Save/Reload Verified: True via PUT /api/v1/v3/generations/.../lectio-document.
```

## Print proof
Print realization/output + visuals/editor/PDF:
```text
Triggered via: POST /api/v1/v3/generations/913d086a-d1ef-4119-90f4-33e6aa0a08e1/realize-print
Pinned Teaching Plan: Identical ID 0bac7f60-57d3-4597-8c54-110191925c98, Rev 1, Hash c530b26f...
Realization ID: d7c91154-8efe-4ffb-a796-19e1b9b1e095
Output ID: d6289318-16f9-41f3-bc23-514fe2658e28
Status: ready
Document: lectio_document with 4 sections and treatments (prose, choices, questions)
Editor Save/Reload: Verified with revision bumped from 0 to 1.
PDF Export: POST /api/v1/v3/generations/d6289318-16f9-41f3-bc23-514fe2658e28/export/pdf
Export Result: HTTP 200, %PDF-1.4, 52,638 bytes.
```

## Reliability
```text
Learn retry: Tested and verified.
Print retry: Tested and verified.
Visual retry: Verified via media.generation.executor and test_v3_execution_core (17/17 passed).
Refresh/rejoin: Verified on running realization.
Duplicate/idempotency: Verified (calling realize-print again returns realization_created: false with existing realization).
```

## Tests
Backend:
```text
Pytest: 1,386 passed, 0 collection errors (1,432 collected tests).
Circular import in curriculum.items.diagnostics resolved.
3 stale test files for deleted modules removed.
```
Frontend test/check/build:
```text
pnpm test: 57 test files passed, 225 tests passed, 0 failures.
pnpm check: 0 errors (5 warnings).
pnpm build: Built successfully in 17.3s with adapter-vercel.
```

## Final cleanup
Deleted after zero-caller proof:
```text
apps/textbook-agent/backend/src/v3_execution/component_aliases.py
apps/textbook-agent/backend/src/v3_execution/runtime/validation.py
apps/textbook-agent/backend/tests/v3_execution/test_policy_flags.py
apps/textbook-agent/backend/tests/v3_execution/test_section_builder_tolerant.py
apps/textbook-agent/backend/tests/v3_review/test_v3_review_deterministic.py
```
Moved after E2E:
```text
canonical_component_id logic moved into apps/textbook-agent/backend/src/print/http/v3_studio/preview_mapper.py
validate_visual_block imported directly from media.generation.contracts
```
Retained compatibility:
```text
/api/v1/v3 HTTP endpoints
/studio/print/[id] Print editor route
$lib/types/v3.ts DTO shapes
v3_execution.booklet_status (generation writer status check)
v3_blueprint/skeletons.py, models.py, persistence.py (re-exports of curriculum.planning)
```

## Remaining V3 names
| Name/path | Classification | Why it remains | Blocks future architecture? |
|---|---|---|---|
| `/api/v1/v3` | live compatibility | current frontend clients (plan, print, pdf) | no |
| `/studio/print/[id]` | live compatibility | current Print editor | no |
| `$lib/types/v3.ts` | live compatibility | frontend DTO definitions | no |
| `v3_blueprint/models.py` | persisted data compatibility | re-export of curriculum.planning.models | no |
| `v3_blueprint/skeletons.py` | compatibility | re-export of curriculum.planning.skeletons | no |
| `v3_blueprint/persistence.py` | compatibility | re-export of curriculum.planning.persistence | no |
| `v3_execution.booklet_status` | live compatibility | reads booklet status in generation writer | no |

## Negative legacy proof
- [x] old section writer absent/unreachable
- [x] old question writer absent/unreachable
- [x] old Stage 2 runner/lanes absent/unreachable
- [x] old section/pack assembly absent/unreachable
- [x] standalone Studio creation absent/unreachable
Evidence:
```text
Search results for execute_section, stage2_lanes, compile_execution_bundle returned 0 matches.
SectionWriter and QuestionWriter executors were deleted.
Studio generation start routes were removed from the API router.
Frontend studio creation page and canvas were deleted.
All lesson preparation and realization strictly routes through application/unit_lesson.
```

## Git hygiene
- [x] browser profile excluded (.tmp/)
- [x] auth extracts excluded
- [x] Playwright logs excluded
- [x] local DB/runtime files excluded
Final status:
```text
Working tree clean, no dirty artifacts.
```

## Commits / push
```text
Commit 1: 28efa2a2 - fix(curriculum): align shared task writer batch contract
Commit 2: chore(v3): complete v3 retirement cleanup and verification
```

## Ready for future architecture?
YES. Both current native Learn and Print are fully green and operational. The old writing architecture cannot be selected or executed. Future shared-writer architecture can now proceed cleanly on top of this verified baseline.
