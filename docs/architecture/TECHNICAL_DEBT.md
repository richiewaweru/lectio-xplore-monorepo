# Technical Debt Register

Canonical register for Lectio Xplore Unit-path product and architecture debt after D0–D6.
Status values: `open` | `asserted-as-is` | `fixed-in-d6` | `deferred`.

---

## Learn runtime / auth / evaluation

### LRN-001
- **Problem:** Learner auth still mixes learner session and teacher JWT semantics.
- **Severity:** High
- **Canonical owner:** `learn/runtime`, `infra/auth`
- **Why deferred:** Product redesign of auth surfaces; out of D6 scope.
- **Dependencies:** LRN-003, DATA-003
- **Acceptance criteria:** Learner routes accept only learner-session credentials; teacher JWT cannot act as learner without explicit impersonation audit.
- **Status:** open

### LRN-002
- **Problem:** Client can influence score/outcome/evidence on attempt submit.
- **Severity:** Critical
- **Canonical owner:** `learn/runtime/evaluation`
- **Why deferred:** Requires server-side evaluation redesign; D6 asserts current chain only.
- **Dependencies:** LRN-004
- **Acceptance criteria:** Scores/outcomes derived exclusively server-side from release + response payload; client-supplied grade fields ignored or rejected.
- **Status:** open

### LRN-003
- **Problem:** Concept/misconception bindings should derive from LearnRelease, not ad-hoc client/runtime copies.
- **Severity:** High
- **Canonical owner:** `learn/evidence`, `learn/runtime`
- **Why deferred:** Evidence model redesign; not required for D6 chain proof.
- **Dependencies:** LearnRelease schema freeze
- **Acceptance criteria:** Attempt evidence references release-owned concept IDs only.
- **Status:** open

### LRN-004
- **Problem:** Interaction UI → attempt persistence bridge incomplete.
- **Severity:** High
- **Canonical owner:** frontend `learn/student`, backend `learn/runtime`
- **Why deferred:** Frontend student UX work; Codex live run will surface gaps.
- **Dependencies:** LRN-002, FE-001
- **Acceptance criteria:** Every supported interaction type persists a typed attempt with reloadable progress.
- **Status:** open

### LRN-005
- **Problem:** Passive section completion semantics incomplete.
- **Severity:** Medium
- **Canonical owner:** `learn/runtime`
- **Why deferred:** Product rule undecided; D6C uses current complete semantics.
- **Dependencies:** LRN-006
- **Acceptance criteria:** Documented rules for when a passive section counts complete; tests cover them.
- **Status:** open

### LRN-006
- **Problem:** Sequential navigation enforcement incomplete.
- **Severity:** Medium
- **Canonical owner:** `learn/runtime`, frontend `learn/student`
- **Why deferred:** Product gating rules; out of D6.
- **Dependencies:** LRN-005
- **Acceptance criteria:** Runtime rejects out-of-order section access when release requires sequence.
- **Status:** open

### LRN-007
- **Problem:** Analytics scoping may include unrelated learner instances (e.g. self-started alongside assigned).
- **Severity:** High
- **Canonical owner:** `learn/analytics`
- **Why deferred:** Product decision on class-vs-assignment scope; D6C documents and asserts current over-broad behavior.
- **Dependencies:** DATA-002, DATA-005
- **Acceptance criteria:** Class/lesson overview includes only instances linked to the class assignment (or explicit product rule).
- **Status:** asserted-as-is

### LRN-008
- **Problem:** ImageHotspot/DragLabel spatial authoring incomplete.
- **Severity:** Medium
- **Canonical owner:** `packages/lectio-learn`, `learn/authoring`
- **Why deferred:** Authoring feature work; not on Unit path golden chain.
- **Dependencies:** LEARN-009
- **Acceptance criteria:** Spatial blocks round-trip builder → release → student without Print-era stubs.
- **Status:** open

### LRN-010
- **Problem:** `runtime_routes` imported `_utcnow` from shim `learn.runtime_service` (`import *` skips `_` names) → attempt submit ImportError.
- **Severity:** High (blocking runtime HTTP)
- **Canonical owner:** `learn/runtime/runtime_routes`
- **Why deferred:** n/a — fixed in D6C.
- **Dependencies:** none
- **Acceptance criteria:** Attempt/complete routes import `_utcnow` from `learn.runtime.runtime_service`; D6C green.
- **Status:** fixed-in-d6

---

## Data model

### DATA-001
- **Problem:** Float scores rather than precise numeric types.
- **Severity:** Medium
- **Canonical owner:** `infra/database`, `learn/runtime`
- **Why deferred:** Migration + API contract change.
- **Dependencies:** LRN-002
- **Acceptance criteria:** Scores stored as Decimal/numeric with documented precision; no silent float drift in tests.
- **Status:** open

### DATA-002
- **Problem:** LearningInstance should likely relate to assignment recipient more strongly.
- **Severity:** Medium
- **Canonical owner:** `learn/distribution`, DB
- **Why deferred:** Schema evolution; D6C asserts current recipient.`learning_instance_id` linkage as-is.
- **Dependencies:** DATA-005
- **Acceptance criteria:** Clear FK/invariant between recipient and instance; orphan instances prevented.
- **Status:** asserted-as-is

### DATA-003
- **Problem:** Auth LearnerSession vs lesson-visit session semantics conflated.
- **Severity:** Medium
- **Canonical owner:** `learn/runtime`
- **Why deferred:** Tied to LRN-001 redesign.
- **Dependencies:** LRN-001
- **Acceptance criteria:** Separate models/APIs for auth session vs lesson visit.
- **Status:** open

### DATA-004
- **Problem:** Class ownership/membership invariants overlap.
- **Severity:** Medium
- **Canonical owner:** `learn/distribution/classes`, DB
- **Why deferred:** Domain cleanup after retirement; not blocking D6 chain.
- **Dependencies:** none
- **Acceptance criteria:** Single ownership path; membership mutations enforce invariants in service + DB.
- **Status:** open

### DATA-005
- **Problem:** Assignment/release ownership validation needs strengthening.
- **Severity:** High
- **Canonical owner:** `learn/distribution/assignments`
- **Why deferred:** Security hardening pass after live run.
- **Dependencies:** DATA-002
- **Acceptance criteria:** Cross-tenant assign/load rejected with tests.
- **Status:** open

### DATA-006
- **Problem:** Documented Alembic head `20260907_0040` (drop `skeleton_shadow_records`) was missing on disk while DBs were stamped.
- **Severity:** High (migration integrity)
- **Canonical owner:** `infra/database/migrations`
- **Why deferred:** n/a — fixed in D6D.
- **Dependencies:** D4 retirement
- **Acceptance criteria:** `alembic heads` → single `20260907_0040`; `upgrade head` succeeds; file present under infra (+ core mirror).
- **Status:** fixed-in-d6

---

## Print

### PRINT-001
- **Problem:** Playwright PDF fixture/process may hang after successful output.
- **Severity:** Medium
- **Canonical owner:** `print/rendering/pdf`
- **Why deferred:** Process lifecycle fix separate from Unit path proof; D6A uses `render_document_pdf`.
- **Dependencies:** none
- **Acceptance criteria:** `export_v3_studio_pdf` (or successor) exits cleanly in CI within timeout after valid PDF bytes.
- **Status:** open

---

## Packages

### LEARN-009
- **Problem:** `@lectio/learn` retains Print-era helpers; quiz evaluate feedback test fails (expects "Not quite!").
- **Severity:** Low–Medium
- **Canonical owner:** `packages/lectio-learn`
- **Why deferred:** Package cleanup/product copy; recorded in D6D, not redesigned.
- **Dependencies:** LRN-008
- **Acceptance criteria:** Package tests green; Print-only helpers removed or clearly namespaced.
- **Status:** open

---

## Architecture / frontend

### ARCH-001
- **Problem:** `v3_*` remains historical shared machinery.
- **Severity:** Medium
- **Canonical owner:** progressive extraction on touch
- **Why deferred:** Incremental; guards prevent new cross-domain imports.
- **Dependencies:** FE-001
- **Acceptance criteria:** No new `v3_*` call sites outside Print owners; inventory shrinks over time.
- **Status:** open

### ARCH-002
- **Problem:** `core/` retains routes/entities/shims.
- **Severity:** Low
- **Canonical owner:** `infra` / application
- **Why deferred:** Post-retirement shim burn-down.
- **Dependencies:** ARCH-001
- **Acceptance criteria:** No production imports from retired shim modules without explicit allowlist.
- **Status:** open

### ARCH-003
- **Problem:** Resource-spec ownership still partly mixed across Print/Learn.
- **Severity:** Low
- **Canonical owner:** `print/resources`, `learn/resources`, shared contracts
- **Why deferred:** Contract split follow-up; D6B notes Print vs Learn role mismatch separately.
- **Dependencies:** ARCH-005
- **Acceptance criteria:** Each resource-spec role owned by one domain with shared contracts only.
- **Status:** open

### ARCH-004
- **Problem:** Unit Learn prepare with `native_whole_lesson` shallow-replaced `chunked_state.context`, wiping form/signals from `persist_structural_plan`.
- **Severity:** High (blocking Learn Unit path)
- **Canonical owner:** `application/unit_lesson/dispatch`
- **Why deferred:** n/a — fixed in D6B.
- **Dependencies:** none
- **Acceptance criteria:** Context merge preserves structural plan fields; D6B green.
- **Status:** fixed-in-d6

### ARCH-005
- **Problem:** Print skeleton slot roles (`organise`/`guided`/…) are not Learn resource-spec roles; Unit→Learn cannot admit Print skeleton as Learn plan without a Learn-compatible structural plan.
- **Severity:** Medium
- **Canonical owner:** `application/unit_lesson`, `learn/generation`, shared intent contracts
- **Why deferred:** Cross-domain plan mapping is product/architecture work beyond minimal D6 wiring; D6B keeps Unit-owned generation then admits Learn-compatible plan via `intent_plan_to_structural_plan`.
- **Dependencies:** ARCH-003
- **Acceptance criteria:** Documented mapping or separate Learn skeleton from Unit path; no silent role coercion.
- **Status:** open

### FE-001
- **Problem:** Frontend import aliases still point at pre-move paths (`$lib/studio/*`, `$lib/api/shared/auth`, `$lib/components/studio/*`, nested `builder/.../print/...`), so `app:test` / `app:check` / `build` fail after Print/Learn ownership moves.
- **Severity:** High (blocks FE CI and browser live run prep)
- **Canonical owner:** `apps/textbook-agent/frontend`
- **Why deferred:** Broad path retarget; D6 proves backend Unit path only. Frontend prepare→`/studio` hop may also remain.
- **Dependencies:** ARCH-001
- **Acceptance criteria:** `pnpm app:test`, `pnpm app:check`, and frontend `build` pass; imports resolve to `print/` / `learn/` / `shared/` owners.
- **Status:** open

---

## Index

| ID | Severity | Status |
|---|---|---|
| LRN-001 | High | open |
| LRN-002 | Critical | open |
| LRN-003 | High | open |
| LRN-004 | High | open |
| LRN-005 | Medium | open |
| LRN-006 | Medium | open |
| LRN-007 | High | asserted-as-is |
| LRN-008 | Medium | open |
| LRN-010 | High | fixed-in-d6 |
| DATA-001 | Medium | open |
| DATA-002 | Medium | asserted-as-is |
| DATA-003 | Medium | open |
| DATA-004 | Medium | open |
| DATA-005 | High | open |
| DATA-006 | High | fixed-in-d6 |
| PRINT-001 | Medium | open |
| LEARN-009 | Low–Medium | open |
| ARCH-001 | Medium | open |
| ARCH-002 | Low | open |
| ARCH-003 | Low | open |
| ARCH-004 | High | fixed-in-d6 |
| ARCH-005 | Medium | open |
| FE-001 | High | open |
