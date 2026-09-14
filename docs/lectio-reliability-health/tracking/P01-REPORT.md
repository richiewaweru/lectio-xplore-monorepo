# Phase report
Phase: P01
Baseline SHA: a6b75e33d2a56452e05033a510f86db1566891b2
Implementation SHA: 1a1a5ed7dd85289341f5aa3bd414ae9feb39cf0d
Served frontend/backend SHA for live checks: unchanged from P00 (native Vite :5173 + backend :8000); offline gates only this phase

Files changed and purpose (high level):
- Ruff green: FastAPI B008 extend-immutable-calls; mechanical + semantic lint cleanup across backend src/tests
- Authoring/call-budget: document.writer single AuthoringEngine path (no nested quality loop); LLMAuthoringProvider repair/retries=0; shared Print writer maps document-writer:* ↔ Print shapes; AuthoringEngineError bridge
- Health: configure_health_extensions merges unspecified kwargs; mutate readiness list in place (CPython 3.11 LOAD_GLOBAL specialization)
- Core shims: auth/health/storage/llm/middleware alias infra submodules for monkeypatch identity
- Print selection: check-understanding without approved sources yields empty candidates; Learn selection honors primitive budgets
- Tests updated for frozen v2 six primitives / shared writer contracts; retired planning/ package removed (ZERO_LEGACY); scripts import print.generation
- Evidence: p01-pytest-final-junit.xml, p01-validate-repo-backend.txt, p01-pytest-round2.txt

Gate results and exact assertions:
- G03 PASS: `python tools/agent/validate_repo.py --scope backend` → VALIDATE=0 (ruff + pytest). Evidence: evidence/p01-validate-repo-backend.txt; final pytest 1391 passed, 6 skipped
- G04 PASS: `uv run python ../tools/agent/check_architecture.py --format text` → No architecture violations. Root pack scripts: contracts:test/check, page:test/check, app:test/check all 0; `pnpm program:domain-guards` → GUARDS=0 after removing src/planning/

Commands (cwd, start, end, exit, log path):
- cwd apps/textbook-agent/backend: `uv run ruff check src/ tests/` → exit 0
- cwd apps/textbook-agent/backend: `uv run pytest -q --tb=line --disable-warnings` → exit 0 → evidence/p01-pytest-final-junit.xml (1391 passed)
- cwd apps/textbook-agent: `python tools/agent/validate_repo.py --scope backend` → exit 0 → evidence/p01-validate-repo-backend.txt
- cwd apps/textbook-agent/backend: `uv run python ../tools/agent/check_architecture.py --format text` → exit 0
- cwd repo root: `pnpm contracts:test|check`, `page:test|check`, `app:test|check` → exit 0; `pnpm program:domain-guards` → exit 0

Migration/rollback evidence: none (P01 health only)

Live IDs/revisions/artifacts: none new (P00 session retained)

Failures, repairs and reruns:
- Baseline 65 failed + 6 errors → green via product/test alignment (not skips)
- Dual-module core.* vs infra.* monkeypatch breaks fixed via submodule aliases + in-place health list mutation
- Transient planning/ shim removed to satisfy ZERO_LEGACY_GUARD; scripts retargeted to print.generation
- One flaky shared-prefix assertion hardened with cache_clear; full suite reconfirmed 1391 passed

Remaining blockers: none for P02

Next safe continuation: P02 stage contracts, Learn admit-before-production, Print admission idempotency, Alembic additive migration
