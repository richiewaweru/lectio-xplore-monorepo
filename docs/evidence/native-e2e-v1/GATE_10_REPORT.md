# Gate 10 — Real LLM smoke

## Pass A

Real provider smoke completed through the production writer path (`dispatch_writer_async`) for non-assessment blocks; assessment blocks used the deterministic assembler. Document persisted and reloaded.

## Command

```bash
cd apps/textbook-agent/backend
.venv\Scripts\python.exe tools\run_native_e2e_fixture.py --provider real --output C:\Projects\lectio\docs\evidence\native-e2e-v1
```

## Result

`docs/evidence/native-e2e-v1/real-llm-run-report.json`

- status: **PASSED**
- credentials present: Anthropic / OpenAI / XAI / DeepSeek (from backend `.env`)
- blocks written: 8 (prose, aside, list, figure pending, table, worked-example, questions, choices)
- figure status: `visual_pending` (pending placeholder path)
- reload_ok: true
- no unexplained application crash

## Classification

Provider-output issues: none observed in this smoke (all blocks ready or intentionally pending visual).

Application issues: none.

Intentionally deferred: live image generation / visual completion callback (pending figures by design for this pass).
