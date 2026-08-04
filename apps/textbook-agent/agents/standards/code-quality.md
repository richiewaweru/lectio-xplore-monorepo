# Code Quality

Rules for writing code that is correct, readable, and maintainable. These apply regardless of language or framework.

## Write Obviously Correct Code

- Prefer clarity over cleverness. If a reader has to pause and think about what a line does, rewrite it.
- Name things for what they represent, not how they're implemented. `user_profiles` over `data_list`. `is_eligible` over `flag`.
- Functions should do one thing. If you need "and" in the description, split it.
- Keep functions short enough to read without scrolling. If a function is longer than ~40 lines, it's probably doing too much.

## Don't Over-Engineer

- Only add code that is needed for the current task. Three similar lines are better than a premature abstraction.
- Don't add error handling for scenarios that can't happen. Trust internal code and framework guarantees.
- Don't add feature flags, backwards-compatibility shims, or configuration for hypothetical future requirements.
- Don't create helpers, utilities, or abstractions for one-time operations.
- If you're building something "just in case" -- stop. Build it when the case arrives.

## Handle Errors at System Boundaries

- Validate at the edges: user input, API responses, file I/O, database results.
- Inside the system, trust your own types and invariants. Don't defensively check what you just constructed.
- When an error happens, fail fast with a clear message. Don't swallow exceptions or return ambiguous defaults.
- Log errors with enough context to debug them: what was attempted, what went wrong, what state matters.

## Dependencies

- Prefer standard library over third-party when the functionality is simple.
- When adding a dependency, verify it's maintained, widely used, and doesn't pull in a large transitive tree.
- Pin dependency versions. Use lock files.
- Don't vendor or copy-paste library code unless there's a specific reason.

## Code Smells to Fix Immediately

- Dead code: unused imports, unreachable branches, commented-out blocks. Delete them.
- Copy-paste duplication across 3+ locations. Extract a shared function.
- God objects or functions that do everything. Break them apart.
- Magic numbers or strings. Name them as constants.
- Mutable global state. Avoid it. Pass dependencies explicitly.

## When Modifying Existing Code

- Understand the code before changing it. Read the surrounding context.
- Match the existing style. Don't reformat files you're not meaningfully changing.
- Don't add docstrings, type annotations, or comments to code you didn't change, unless asked.
- Don't "improve" nearby code while fixing a bug. Keep the diff focused.
- If you see something that needs fixing but it's outside your current scope, note it as follow-up work.

## Security Basics

- Never commit secrets, tokens, or credentials. Use environment variables.
- Sanitize user input before using it in queries, commands, or rendered output.
- Use parameterized queries, not string concatenation, for database operations.
- Be aware of OWASP top 10 vulnerabilities. If you introduce one, fix it immediately.
