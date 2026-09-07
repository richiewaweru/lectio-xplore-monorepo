# Known Deferred Product Fixes

Do **not** implement these during the refactor. Preserve them as explicit post-refactor work:

1. Separate learner authentication from teacher JWT fallback.
2. Move scoring/evaluation authority server-side.
3. Derive concept bindings/misconceptions from immutable LearnRelease instead of trusting client payload.
4. Wire interaction UIs to persistent attempt submission end to end.
5. Add explicit section completion events.
6. Enforce sequential student navigation and completed-section revisit semantics.
7. Scope analytics through class/assignment/recipient context.
8. Improve ImageHotspot/DragLabel true spatial authoring/runtime behavior.
9. Replace Float score storage with precise Numeric/Decimal where appropriate.
10. Remove retained legacy `v3_studio`.
11. Remove remaining internal Component-Lectio print helpers once safe.
12. Fix Page PDF fixture process hang after successful output.

The refactor should make the eventual location of each fix obvious.
