# Testing

Rules for writing tests that catch real bugs without slowing you down. Test what matters, skip what doesn't.

## What to Test

- Every behavioral change needs at least one test. If you changed how something works, prove the new behavior is correct.
- Test the public interface, not internal implementation. If you refactor internals without changing behavior, existing tests should still pass.
- Test the happy path first. Then add the most likely failure case. Then stop unless the function is safety-critical or has tricky edge cases.
- Test boundary conditions: empty inputs, zero values, maximum values, off-by-one scenarios.

## What NOT to Test

- Don't test framework behavior. If you're testing that FastAPI returns 200 when your route returns a dict, you're testing FastAPI, not your code.
- Don't test simple getters, setters, or data classes unless they have logic.
- Don't write tests for code you didn't change, unless you're adding coverage for a known gap.
- Don't test implementation details. If your test breaks every time you refactor but behavior hasn't changed, the test is too coupled.

## Test Structure

- One concept per test. If a test name needs "and," split it.
- Name tests for what they verify: `test_expired_token_returns_401`, not `test_auth_3`.
- Follow Arrange-Act-Assert (or Given-When-Then). Keep each section visually clear.
- Keep tests independent. No test should depend on another test's state or execution order.
- Keep test data minimal. Only set up what the test actually needs. Use factories or fixtures for common objects.

## Unit vs. Integration

- **Unit tests**: fast, isolated, test one function/class. Use these for logic, calculations, transformations.
- **Integration tests**: hit real infrastructure (database, API, filesystem). Use these for data access, API contracts, end-to-end flows.
- Default to unit tests. Use integration tests when the behavior you're verifying genuinely depends on the integration (e.g., SQL query correctness, API response format).
- Don't mock what you own. If you're mocking your own code extensively, you probably need to restructure, not mock harder.

## When Mocks Are Appropriate

- External services you don't control (third-party APIs, payment processors)
- Expensive operations in unit tests (LLM calls, file generation)
- Time-dependent behavior (use a clock abstraction)

When mocks are NOT appropriate:
- Your own database layer (use a test database instead)
- Your own internal modules (test through the real code path)
- Anything where mock/production divergence has burned you before

## Flaky Tests

- A flaky test is worse than no test. It erodes trust in the entire suite.
- If a test fails intermittently, fix it or delete it. Don't add retries or sleeps to paper over it.
- Common causes: shared mutable state, time-sensitive assertions, network calls, race conditions.

## Test Maintenance

- When you change behavior, update the tests in the same commit. Don't leave failing tests for a follow-up.
- When deleting code, delete its tests too. Dead tests are noise.
- Review test quality during code review. Weak assertions (asserting only that no exception was thrown) are almost as bad as no test.

## Coverage

- Coverage is a tool, not a target. High coverage with weak assertions is useless.
- Focus on covering critical paths, not hitting a percentage number.
- If a function is hard to test, that's usually a design smell -- consider refactoring it.
