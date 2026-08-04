## Feature: V3 PDF cross-repo completion

**Classification**: major
**Subsystems**: backend/frontend/both

### Progress
- [x] Understood requirements and identified scope
- [x] Read relevant source code and project rules
- [x] Published Lectio 0.4.4
- [x] Updated Textbook Agent to Lectio 0.4.4
- [x] Synced contracts and generated adapter
- [x] Hardened PDF diagnostics/logging
- [x] Verified V3 answer-key export behavior
- [x] Ran validation (backend + frontend)
- [x] Self-reviewed against agents/standards/review.md
- [x] Wrote commit message(s) following agents/standards/communication.md
- [x] Updated handoff notes with validation evidence and risks

### Validation Evidence
- Lectio release:
  - `pnpm run check`
  - `pnpm run test`
  - `pnpm run build`
  - `pnpm run package`
  - `pnpm run export-contracts`
  - Published `lectio@0.4.4` and confirmed availability with `npm view lectio@0.4.4 version`
- Frontend:
  - `npm run test -- src/lib/lectio-lockfile-sync.test.ts`
  - `npm run check`
  - `npm run build`
  - `uv run --with pyyaml --with jinja2 python tools/agent/validate_repo.py --context docs/project/context-summary.yaml --scope frontend`
- Backend targeted checks:
  - `uv run --directory backend ruff check src/generation/pdf_export/rendering/playwright.py tests/generation/test_playwright_rendering.py`
  - `uv run --directory backend pytest ../backend/tests/generation/test_playwright_rendering.py ../backend/tests/generation/test_answers_v3.py ../backend/tests/generation/test_v3_pack_pipeline_document.py ../backend/tests/generation/test_v3_generation_writer.py -q`
  - `uv run --with pyyaml --with jinja2 python tools/agent/check_architecture.py --format text`
- Manual QA:
  - Seeded `manual-v3-pdf-qa-001` into `backend/textbook_agent.db`
  - Exported `outputs/manual-v3-pdf-qa-001-with-answers.pdf` and `outputs/manual-v3-pdf-qa-001-no-answers.pdf`
  - Verified `DefinitionFamily` content rendered in the PDF text
  - Verified worked-example markdown and inline note text rendered in the PDF text
  - Verified answer-key pages are present when `include_answers=true` and absent when `include_answers=false`
  - Verified `report_json.pdf.last_debug.print_page` persisted `renderer`, `fetch_status`, `section_count`, and image counters
- Contract sync:
  - `uv run python tools/update_lectio_contracts.py`
  - No downstream schema/type diffs were required after the sync

### Risks and Follow-up
- Repo-wide backend validation is still not green:
  - `uv run --with pyyaml --with jinja2 python tools/agent/validate_repo.py --context docs/project/context-summary.yaml --scope backend`
  - This still fails on unrelated pre-existing backend tests outside the PDF export slice.
- The local manual QA generation `manual-v3-pdf-qa-001` and exported PDFs in `outputs/` are test artifacts. Remove or regenerate them intentionally if they should not persist in a follow-up session.
- The browser-only print route inspection was less reliable than the actual export path because the in-app browser stalled on the long authenticated print URL. The real backend export, persisted debug payload, and extracted PDF text were used as the source of truth for sign-off.
