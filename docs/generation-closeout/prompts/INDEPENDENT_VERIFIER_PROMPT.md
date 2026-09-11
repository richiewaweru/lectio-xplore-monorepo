# Independent Verification Prompt

You are the verifier, not the implementer.

Do not trust implementation reports, phase checkboxes, comments saying "canonical", or tests that call only helpers.

For every phase A-I:
1. identify real production entrypoint;
2. trace call graph;
3. prove promised new layer is invoked;
4. inspect generated/persisted artifacts;
5. run negative searches for old/competing path;
6. execute required live/browser proof.

Grade only PASS, FAIL, or BLOCKED.

Automatic FAIL examples:
- prompt exists but is not manifest-loaded;
- learner actions only appear in handcrafted fixtures;
- live Print bypasses shared writer;
- Unit Generate Print still depends on Studio approval mechanics;
- generated figure 404s;
- tabs reconstruct structure from Teaching Plan instead of realized document;
- Print editor edits LearnDocument instead of LectioDocument v2;
- report says "deferred" for phase-gate requirement;
- heuristic fallback silently substitutes for LLM in live acceptance.

Final output:
- phase verdicts;
- exact evidence;
- discrepancies between report and runtime;
- merge recommendation: YES / NO.
