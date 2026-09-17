# Refactor Principles

1. **Move before redesign.**
   Preserve behavior, interfaces, schemas, and public APIs unless a path import must change.

2. **Ownership over historical naming.**
   `v3_execution`, `whole_lesson`, `component_lectio`, etc. are implementation-era names. Durable folders should describe responsibility.

3. **No giant shared bucket.**
   `shared/` or `common/` may contain only truly generic infrastructure/UI. Do not move ambiguous code there to avoid deciding ownership.

4. **Prompts are realization-owned.**
   Print prompts live under Print. Learn prompts live under Learn. Similarity is not sufficient reason to share them.

5. **Writers/validators/renderers are realization-owned.**
   Prefer duplicated thin code to ambiguous cross-domain machinery.

6. **Shared only when semantics are genuinely shared.**
   DB session, auth, LLM client, telemetry: shared.
   Page-form writer vs Learn component writer: not shared.

7. **Thin composition roots.**
   `app.py` and route entrypoints wire domains; they do not contain domain logic.

8. **No circular imports.**
   If moving exposes a cycle, resolve the cycle through a small owned contract or platform seam; do not introduce import hacks.

9. **Compatibility shims must be temporary and named.**
   If import forwarding is required, put it under a clear `compat/` seam, test it, and record removal criteria.

10. **Tests move with ownership.**
    Tests should mirror the new domain structure where practical.

11. **No behavior change hidden in a move.**
    If a behavior fix is necessary to make a move safe, isolate it in a separate commit/step and document it.

12. **Keep git history readable.**
    Prefer file moves/renames with minimal same-step edits. Separate mechanical moves from semantic cleanup.
