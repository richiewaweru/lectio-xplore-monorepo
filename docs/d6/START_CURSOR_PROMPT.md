Execute D6 in `C:\Projects\lectio`. Start with D6A only.

Prove the refactored system through automated integration/E2E tests:
Unit→Print→PDF; Unit→Learn→Builder→Preview→Publish; LearnRelease→Assignment→Runtime→Analytics; then run architecture/migration/regression gates and finalize the technical-debt register.

Use real DB integration and canonical services. Mock only external providers. Do not perform another broad refactor or the live browser run. Report every failure, update D6 state only on PASS, and stop after each subphase.
