# Four official Phase 02 runs

Frozen prompt set: no planner/writer prompt edits between subjects.

| Subject | Driver artifact | Notes |
|---|---|---|
| Science | `science-run.json` | Conceptual first-exposure |
| Mathematics | `mathematics-run.json` | Same native path |
| Economics | `economics-run.json` | Same native path |
| English | `english-run.json` | Same native path |

## How to execute

```bash
cd apps/textbook-agent/backend
set PHASE02_API_BASE=http://localhost:8000
set PHASE02_AUTH_TOKEN=<token>
set PHASE02_GENERATION_IDS=Science:<id>,Mathematics:<id>,Economics:<id>,English:<id>
uv run python tools/phase02_four_runs_driver.py
```

Pre-create each generation through Studio/native teaching approval gate (`awaiting_teaching_approval`, `document_contract_version=2`) before approve.

## Offline / CI

Unit gates in `test_phase02_*.py` prove queue, lease, isolation, DB assembly, visuals, and PDF conflict without live LLM. Live four-run binaries are produced by the driver against a provisioned environment.
