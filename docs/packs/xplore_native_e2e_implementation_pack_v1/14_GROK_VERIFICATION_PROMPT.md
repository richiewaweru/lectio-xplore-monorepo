# Grok Verification Prompt

Now verify the implementation you just completed. Do not rely on your earlier reasoning or summaries.

1. Re-read `11_ACCEPTANCE_CHECKLIST.md`.
2. Inspect the actual diff.
3. Run every targeted command in `05_TEST_STRATEGY_AND_COMMANDS.md`.
4. Run the full offline backend suite.
5. Run Lectio package checks and tests.
6. Run frontend checks and tests.
7. Execute every scripted mock scenario.
8. Execute the all-forms mocked end-to-end fixture through the real application services.
9. Reload the persisted document and validate it.
10. Produce student and teacher renders and PDFs.
11. Run one real LLM smoke lesson.
12. Inspect the native status API at every stage.
13. Search the runtime for legacy references and prove none are called.

For each checklist item, mark:

```text
PASS — include evidence path
FAIL — include exact failure
NOT RUN — explain why; this does not count as passing
```

Do not fix tests by weakening assertions, bypassing persistence, constructing the final document directly, disabling forms, or skipping the real application state machine.

At the end, state one of:

- `IMPLEMENTATION COMPLETE`
- `IMPLEMENTATION INCOMPLETE`

Use `IMPLEMENTATION COMPLETE` only if the mocked flow produces a persisted document plus student and teacher PDFs and no application failure remains.
