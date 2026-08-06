# Legacy Runtime Removal Checklist

The goal is not necessarily to delete every historical file immediately. The goal is one production generation path.

## Search audit

From repository root, save results to `legacy-reference-audit.txt`:

```bash
rg -n   "document_contract_version.?=.?1|resume_stage2|stage2|/builder|builder/|legacy|convert.*v1|blueprint|SectionContent"   apps/textbook-agent/backend/src   apps/textbook-agent/frontend/src
```

Review every result; do not blindly delete unrelated historical documentation.

## Disable from new generation

- [ ] create endpoint cannot select v1.
- [ ] teacher approval continues native state.
- [ ] retry resumes native section execution.
- [ ] status uses native state.
- [ ] viewer uses native document.
- [ ] PDF uses native document.
- [ ] no fallback conversion on native error.
- [ ] no environment flag silently switches to legacy.

## Historical compatibility

Allowed only if needed:

- read existing legacy records;
- display a clear archived/unsupported notice;
- export an already-created historical artifact.

Not allowed:

- creating new legacy records;
- converting v2 to v1 to render;
- invoking legacy stage2 after native planning;
- using legacy status fields as native truth.

## Test mechanism

Patch/spy known legacy callables so they raise:

```python
AssertionError("legacy runtime invoked by native flow")
```

Run create → approval → write → assembly → render → PDF. The test passes only if no spy is triggered.
