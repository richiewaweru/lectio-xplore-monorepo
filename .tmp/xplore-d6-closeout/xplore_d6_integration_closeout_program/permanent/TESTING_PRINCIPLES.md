# Testing Principles

Prefer real:
- FastAPI/service composition
- ORM + DB transactions
- serialization/validation
- persistence/reload
- @lectio/page and @lectio/learn contracts

Mock only:
- LLM providers
- image/network providers
- external storage where unavoidable

Assert meaning, not only status codes. Verify IDs, ownership, persistence, immutable releases, correct instance/release linkage, and failure/retry state.
