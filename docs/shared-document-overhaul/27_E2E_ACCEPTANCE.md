# End-to-End Acceptance

Prove through real application surfaces:

```text
create lesson
→ prepare
→ Structural Plan
→ Teaching Plan
→ approve
→ SharedDocument run
→ shared preview
→ Learn realization/open/runtime/publish
→ Print realization/open
→ PDF export
```

Operational cases:
- refresh during each stage;
- backend restart;
- one-section failure/retry;
- continuity repair;
- media failure;
- Learn and Print sibling isolation;
- duplicate request;
- source-hash conflict;
- cancellation.

Content assertions:
- learner title is not raw Teaching Plan arc;
- section title is learner-facing;
- no internal IDs/planning text;
- no repeated paragraph/callout paraphrase pattern;
- lists/figures/tables render semantically;
- task position is shared;
- Learn and Print pin the same SharedDocument hash;
- Print answer key has human labels;
- visual readiness is truthful.
