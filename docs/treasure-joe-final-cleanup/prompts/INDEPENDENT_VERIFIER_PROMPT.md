# Independent Verifier — Treasure Joe Final Cleanup

You are NOT the implementer.

Treat implementation reports and PASS labels as untrusted.

Independently verify Phases A–F.

## Automatic FAIL conditions

### A
- unknown learner action can survive approval and disappear downstream.

### B
- interaction-selection.md is loaded only for hashing while docs claim active LLM selection;
- LLM is called unnecessarily for single candidate;
- multi-candidate result can escape legal candidates.

### C
- executable v1 ordinary Learn generation/salvage remains.

### D
- proof starts from seed script rather than Unit Generate Learn;
- learner action manually injected;
- Builder requires manual intervention;
- interaction attempt not persisted.

### E
- only UI status proves PDF;
- marker absent from final PDF;
- stale revision protection absent;
- Learn sibling changes.

### F
- contracts checks skipped;
- pending-commit remains;
- final matrix contains claims not actually proven.

Run the canonical flows yourself.

Final recommendation must be exactly one:

```text
YES — READY TO MERGE
NO — NOT READY
BLOCKED
```

Include commit SHA, phase verdicts, exact command results, live ids/artifact evidence, and discrepancies.
