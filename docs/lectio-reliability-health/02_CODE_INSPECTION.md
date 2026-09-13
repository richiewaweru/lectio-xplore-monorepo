# Code inspection and limitations
Inspection: read-only GitHub source at a6b75e33; no local repository build, dependency installation, test execution or live app proof in proposal preparation. These findings supersede the old c3563ab assessment.
Paths below are repository-relative. Prefix B = apps/textbook-agent/backend/src; F = apps/textbook-agent/frontend/src.

| Observed file | Actual observation | Required action |
|---|---|---|
| B/document/composer.py | compose_document_plan uses AuthoringEngine with max_repair_attempts=2 | Preserve composer; attach durable run context and count actual calls |
| B/document/writer.py | write_document_primitive uses max_repair_attempts=2 and can invoke execute again after quality failure; random work_order_id created inside call | Unify total call budget; persist item identity before execution; retain quality repair feedback |
| B/learn/generation/native_execution.py | produce_learn_from_approved_teaching creates random output ID, awaits full production, then adds completed GenerationModel and EditableLessonModel; admit_realization comes afterward | Trace callers/transactions; admit durable operation before calls, checkpoint intermediate outputs, prevent duplicates |
| same Learn file | preparation reads GenerationModel.chunked_state_json directly, without Print repository | Earlier claim that Learn imports Print repository here is obsolete; do not manufacture that cleanup |
| same Learn file | allow_heuristic_composition_fallback=True | Expose policy/mode and test fallback truthfully |
| B/application/unit_lesson/realize_print_handoff.py | Uses PageDocumentRepository.save_teaching_review(status=approved, queue=True), then admits realization using preparation ID as output | Audit repeated admissions, approval immutability and preparation/output state ownership; preserve compatibility while making operations independent |
| B/print/generation/whole_lesson/states.py | Already has legal transitions, resume decisions, leases; failed_recoverable explicitly not worker-claimable | Reuse protections; never let polling reset exhausted retries |
| F/routes/units/[id]/+page.svelte | Previously inspected 872-line page combines load/plan/prepare/Print/Learn/history; scoped panels already exist, common busy state | Extract controllers/stores and independent operations; preserve existing panels |
| F/lib/api/units.ts | Shared request functions and generation/status API surface | Version/extend responses deliberately; maintain callers while transitioning |
| apps/textbook-agent/tools/agent/validate_repo.py | Validation is driven by context-summary.yaml; failures aggregate | Inspect context definitions before execution; do not remove failing scope steps |
| package.json | contracts/page/app scripts and domain guards present | Use actual scripts in commands file; do not invent a gate script and claim it ran |

Follow-through inspection required before edits: infra/authoring/engine.py and provider SDK configuration; document composition IDs; Learn native_production and interaction writers; Print executor/repository/worker/native_retry; generation DB models/migrations; realization admission and both HTTP callers; publishing/runtime authorization; prompt manifests; media jobs; frontend Builder/Print stores and HTTP error handling. Locate actual files via rg. This is a targeted inspected baseline, not a claim that every module was audited.

Evidence already reviewed: docs/treasure-joe-final-cleanup/evidence/phase-f-PASS-FAIL.json records ~1314 Ruff findings and planning/v3_blueprint failures, while focused gates pass. Independent verifier report refers to an earlier tip and notes missing retained PDF and incomplete continuous live provenance. Current tracking STATE.json no longer contains the earlier placeholder. Rerun to classify current failures; do not repeat superseded defects.

Sources: https://github.com/richiewaweru/lectio-xplore-monorepo/tree/a6b75e33
https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/
https://opentelemetry.io/docs/concepts/signals/traces/
https://platform.claude.com/docs/en/api/errors
External sources are rationale; repository/provider configuration must be checked at implementation time.
