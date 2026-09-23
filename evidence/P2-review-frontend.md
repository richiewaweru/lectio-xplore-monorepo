# P2b — Teaching Plan review UI and displayed-hash approval

Date: 2026-09-23 (Africa/Nairobi)
Branch: `codex/generation-stability`
Starting HEAD: `57177e66ce6b1d1e89c0e912b77212c7e138365b`
P2a and P2b gates: PASS, accepted by Sol. Final follow-up validation passed on 2026-09-23. P2 overall is PASS; P3 is active at the read-only design checkpoint, with no product code started.

## Contract implemented

- Units and Studio display the validated `teaching_plan` content (arc, sections and blocks, transitions, learner actions, evidence and references, source questions/sourcebook scope, anchor usage, and misconception focus).
- Review status and revision appear in a separate review panel, together with the verified pending/approved content hash. The UI does not treat review metadata as plan content.
- Approval is enabled only when visible plan content exists, current review status is `pending`, `pending_hash_verified` is true, the pending hash is nonblank, and plan, review, and identity revisions match.
- Both callers submit the exact loaded `expected_revision` and `expected_content_hash`. They re-fetch after approval and continue only when the plan content and verified approved revision/hash match what the teacher submitted.
- The active approval endpoint returns typed HTTP 409 `TEACHING_CONTENT_HASH_REQUIRED` when the submitted hash is missing or blank. Existing stale revision and same-revision mutation conflicts remain typed and fail closed.
- Print has an independently found approval invariant: if revision 1 is approved but revision 2 is pending, Create Print now returns typed HTTP 409 `TEACHING_REVISION_PENDING_REVIEW`. It does not call the Print queue/save path and does not approve or change the pending record. The teacher must review the current draft first.

## Validation

Commands run from `apps/textbook-agent/backend`:

```text
uv run pytest tests/curriculum/test_p2_approval_content_identity.py tests/curriculum/test_p02_shared_plan_gates.py tests/curriculum/test_smart_lesson_contracts.py tests/curriculum/test_workspace_projection.py tests/planning/test_path_routes.py tests/application/test_p03_realization_gates.py -q
```

Result: **69 passed, 1 warning, 84.28 s.** The warning is the existing Pydantic `schema` field shadow warning in `src/contracts/generation_manifest.py`. Coverage includes typed hashless API rejection, hash/revision conflicts, route contract/projection regressions, and the approved-revision-1 plus pending-revision-2 Print rejection test. That regression checks that the review remains `pending`, its current revision stays 2, its approved pointer remains 1, and revision 2 remains pending after the rejected request.

```text
uv run ruff check src/application/unit_lesson/realize_print_handoff.py src/print/http/v3_studio/router.py tests/application/test_p03_realization_gates.py tests/curriculum/test_p2_approval_content_identity.py
```

Result: **All checks passed.**

Commands run from `apps/textbook-agent/frontend`:

```text
npm test -- src/lib/curriculum/lessons/teaching-plan-review.test.ts src/lib/curriculum/lessons/TeachingPlanReview.test.ts src/lib/api/v3.test.ts src/routes/studio/page.test.ts 'src/routes/units/[id]/lessons/[lessonId]/plan/page.test.ts'
```

Result: **55 passed across 5 files** on the final rerun after adding the stale-ready/current-pending regression. UI tests cover disabled approval for blank/unverified/mismatched review state, separate pedagogical and review content, visible verified hashes, exact hash/revision POST payloads from Units and Studio, verified approval content after refresh, and preserving actionable pending review despite a stale worker `ready` stage.

```text
npm run check
```

Result: **0 errors, 5 warnings.** Warnings are in pre-existing `InteractionEditor.svelte`, `DocumentCanvas.svelte`, `DocumentEditor.svelte`, and `PrintDocumentEditor.svelte` code.

```text
npm run build
```

Result: **exit 0.** Build prints existing Svelte warnings and optional-dependency notices for `canvas`, `utf-8-validate`, `bufferutil`, and `supports-color`.

## Scope and remaining gate

P2b edits are limited to the two approval surfaces and their API/view/tests, the active approval request handler, and a small Print handoff guard with focused regression coverage. Print worker/output identity, realization lifecycle, and authoring remain unchanged. No architectural blocker surfaced. Sol accepted P2b and P2. P3 is active for read-only design review; product edits remain gated on Sol's review.
