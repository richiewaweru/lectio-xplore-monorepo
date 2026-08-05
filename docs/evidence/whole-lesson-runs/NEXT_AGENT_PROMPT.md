# Next Agent — Paste This Entire Block

```
You are continuing whole-lesson native E2E proof work on the lectio monorepo.

READ FIRST (full context):
- docs/evidence/whole-lesson-runs/AGENT_HANDOFF_BROWSER_RUN01.md
- docs/authority/whole-lesson-e2e-pack-v1.2/04_PROOF_RUNS/FOUR_RUN_PROOF_PROTOCOL.md (Run 01 + gate §10)

Branch: whole-lesson-native-e2e
Repo: C:\Projects\lectio
App root: apps/textbook-agent

GOAL (now): Get ONE lesson working end-to-end via the real UI — Run 01 Science
(Why plants need light to make food). Do NOT use fixtures or auto-approve teaching.
Fix bugs you hit in code; do not commit .env.

MANDATORY APPROACH:
1. Use Codex's own in-app browser for the Xplore UI — drive the full flow in the browser, not API-only scripts.
2. Start servers yourself and keep backend WITHOUT --reload during LLM waits.

Start servers:
  Terminal 1: cd C:\Projects\lectio\apps\textbook-agent\backend && uv run uvicorn app:app --host 127.0.0.1 --port 8000
  Terminal 2: cd C:\Projects\lectio\apps\textbook-agent\frontend && npm run dev
  Open: http://localhost:5173 (localhost for Google OAuth)

Preflight:
  curl http://127.0.0.1:8000/health
  cd backend && uv run python scripts/verify_whole_lesson_prompts.py

Browser flow (Run 01):
  /units → create Science Grade 4 unit (objective: plants need light to make food)
  → path plan → resolve assumptions → path approve
  → prepare conceptual first_exposure lesson (pick objective re light/photosynthesis)
  → /studio?generation_id=... → approve structural plan
  → wait for awaiting_teaching_approval → review last brief FIRST → approve teaching
  → wait for document complete → export teacher + student PDFs
  → uv run python scripts/capture_whole_lesson_evidence.py <generation_id> --run run-01-science

Known fixes already in working tree (verify still present):
  planning/bridge.py — native path clears legacy components; normalizes ConceptCard
  planning/whole_lesson/repository.py — await load_chunked_state / persist_chunked_state
  planning/agents.py — page structural planner prompt when native_whole_lesson

If prepare fails (422 SectionPlan/ConceptCard) or stage2 crashes (coroutine .get), fix and retry.
If stuck >10 min on one stage, check backend terminal logs.

Success = run-01-science/ has capture artifacts + PDFs + 30-reloaded-lectio-document.json + Run 1 gate pass.
Update docs/evidence/whole-lesson-runs/FOUR_RUN_REPORT.md when done.
Stop after Run 01 unless gate passes and user asks for 02–04.
```

Human step: sign in with Google when the browser opens (OAuth cannot be scripted without test credentials).
