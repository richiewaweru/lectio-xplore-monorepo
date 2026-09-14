# C00 Report

Starting SHA: `f386ab6893f3068af5db18a0a9d5898ed46b0bff`
Auth: PASS (`auth_me=200`, evidence/c00-auth.json)
Docker db-dev: started
PLAN.md + STATE.json: written
Production call-site map: recorded in PLAN.md

## Commands

```
uv run pytest tests/reliability/test_correction_pass.py -q
```

## Gate

PASS — baseline pinned, auth live, decisions explicit, regressions encoded as tests.
