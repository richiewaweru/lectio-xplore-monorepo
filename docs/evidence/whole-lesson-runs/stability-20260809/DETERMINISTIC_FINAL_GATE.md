# Deterministic final gate and first live native handoff (2026-08-09)

## Outcome

All repository-wide deterministic checks now pass. The authenticated live matrix is still
pending manual sign-in and must not be inferred from these results.

## Defects exposed and corrected by the gate

1. Native queue contention fixtures seeded `queued` and `writing_blocks` generations with a
   pending teaching review. The fixture now models the production invariant: work that has
   crossed the mandatory teacher gate carries an approved review.
2. Derived provider trace IDs such as `path-prepare:<user>:<request>:structural1` were not
   resolved through their registered parent trace, causing a live
   `Skipping llm_call persistence without user_id` warning. The telemetry registry now walks
   colon-delimited parent traces, with a regression proving the derived structural call keeps
   the registered user.
3. The canonical path JSON Schema omitted the active `scope.terminology` field, and one
   skeleton test still expected the obsolete `modules` fixture shape. The schema and test now
   match the active canonical `scope + lessons` contract.
4. Repository Ruff found 27 stale unused imports/exports. They were removed; the active dynamic
   prompt accessor remains available while its stale `__all__` entry is gone.
5. Windows production builds failed when the Vercel adapter attempted a pnpm symlink whose
   package lived in the workspace-level `node_modules`. The safe adapter now searches ancestor
   workspace package roots and falls back to its copy path. The production build completes.
6. Three unused unit-page CSS selectors were removed, taking Svelte diagnostics from three
   warnings to zero.

## Exact deterministic evidence

Focused queue correction:

```powershell
cd C:\Projects\lectio\apps\textbook-agent\backend
.\.venv\Scripts\python.exe -m pytest tests\planning\test_phase02_queue_and_lease.py::test_two_workers_cannot_both_claim_queued tests\planning\test_phase02_queue_and_lease.py::test_stale_active_contention_one_winner -q --tb=short
```

Result: **2 passed**.

Native hardening and recovery command from `PLAN.md`:

```powershell
$nativeTests = @(
  'tests\planning\test_native_only_routing.py',
  'tests\planning\test_native_status_payload.py',
  'tests\planning\test_native_retry_pre_worker.py',
  'tests\planning\test_native_retry_durability.py',
  'tests\planning\test_native_retry_lease_fencing.py',
  'tests\planning\test_phase02_queue_and_lease.py',
  'tests\planning\test_phase02_worker_failure_policy.py',
  'tests\planning\test_phase05_visual_dispatch.py',
  'tests\planning\test_visual_dispatch_failure.py',
  'tests\planning\test_phase02_visual_pdf_routes.py'
)
.\.venv\Scripts\python.exe -m pytest @nativeTests -q --tb=short
```

Result: **144 passed**, one pre-existing Pydantic field-name warning.

Telemetry regression:

```powershell
cd C:\Projects\lectio\apps\textbook-agent\backend
.\.venv\Scripts\python.exe -m pytest tests\services\test_telemetry_service.py -q --tb=short
.\.venv\Scripts\python.exe -m ruff check src\telemetry\service.py tests\services\test_telemetry_service.py
```

Result: **5 passed**; Ruff passed.

Frontend/page package gates:

```powershell
cd C:\Projects\lectio
pnpm app:check
pnpm app:test
pnpm page:check
pnpm page:test
```

Results:

- app check: **0 errors, 0 warnings** after unused CSS cleanup;
- app tests: **80 files, 331 tests passed**;
- page check: **0 errors, 0 warnings**;
- page tests: **6 files, 31 tests passed**.

Architecture and repository validation:

```powershell
cd C:\Projects\lectio\apps\textbook-agent
.\backend\.venv\Scripts\python.exe tools\agent\check_architecture.py --format text
.\backend\.venv\Scripts\python.exe tools\agent\validate_repo.py --scope all
```

Final result:

- architecture: **No architecture violations found**;
- backend Ruff: **passed**;
- backend pytest: **985 passed**, one pre-existing Pydantic field-name warning;
- frontend check: **passed, 0 errors and 0 warnings**;
- frontend production build: **passed** (`@sveltejs/adapter-vercel`, `✔ done`);
- tooling tests: **8 passed**;
- validator exit code: **0**.

## Runtime state

Required services were restarted without touching reserved ports:

- frontend `127.0.0.1:5173`: HTTP 200;
- backend `127.0.0.1:8000`: health `ok`, architecture
  `shell-pipeline-native-lectio`, instance `4253a096-aba6-4836-85ac-e10e9fd3e3c3`;
- native worker: `native-3bd1e5fdc5aa`;
- PostgreSQL container: healthy on 5432;
- no listener was started or changed on reserved 5174/8001.

## First live native diagnostic run

The normal authenticated UI created and approved:

- unit: `ac03d8a4-789c-437f-806a-af2fc53af704`;
- path lesson: `0410a02a-36f7-4a04-98de-7cd757d4ea60`;
- generation: `ea292446-abba-40d9-8b5e-6a904fa71653`;
- final persisted status/stage: `failed_terminal` / `writing_sections`;
- persisted `native_whole_lesson`: `true`;
- persisted document contract: `2`;
- no Builder route or record was used in the observed UI flow.

The normal UI progressed through structural review, item generation, mandatory teaching
approval, form planning, and section writing. It then exposed two independent defects:

- provider `ModelAPIError: Connection error` failures were stored as `UNKNOWN` and
  non-retryable instead of recoverable transport failures;
- two `choices` blocks lacked an exact approved-item binding and failed deterministically.

The run also exposed the derived-trace attribution defect described above. Because all three
defects occurred before their fixes, this generation is diagnostic failure evidence, not a
successful targeted or final-matrix proof. Its terminal state remains immutable; recovery must
create a fresh generation through the product regeneration workflow.

## Remaining gate

The user is authenticated and the local services are running. Completion still requires a
fresh post-fix native run, the targeted form-timeout, ready navigation, live visual,
visual-only retry, worker reclaim, PDF inspection, telemetry/hash evidence, and four new
browser-driven native lessons from `PLAN.md`.
