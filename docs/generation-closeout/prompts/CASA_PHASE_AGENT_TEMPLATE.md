# CASA Phase Agent Template

Implement Phase <X> only.

Before editing:
- read repo instructions and closeout pack;
- open every active file for this phase;
- search all callers/consumers;
- record branch + HEAD;
- run focused baseline tests.

Create a checklist phrased as observable runtime outcomes, not file changes.

For every item record:

```text
CURRENT:
CHANGE:
CANONICAL CALLER:
TEST:
LIVE PROOF:
STATUS:
```

Rules:
- no partial PASS;
- no silent fallback in acceptance proof;
- no fixture-only completion where Unit/browser proof is required;
- no duplicate subsystem;
- no hardcoded mutable LLM guidance where pack requires Markdown/YAML;
- do not proceed to next phase if this phase is FAIL/BLOCKED.

Return changed/deleted files, exact tests/results, live ids/routes, unresolved risks, commit SHA, and PASS/FAIL/BLOCKED.
