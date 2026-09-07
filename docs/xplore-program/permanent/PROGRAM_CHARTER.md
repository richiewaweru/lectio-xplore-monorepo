# Program Charter

## North star

Xplore becomes an instructional system in which a teacher can intentionally design a lesson once, realize it as Print or Learn, publish an immutable Learn realization, distribute it to learners, receive concept-linked learning evidence, and inspect useful analytics.

```text
AUTHOR
  ↓
EDIT
  ↓
┌──────────────┬─────────────────────────┐
│              │                         │
PRINT         LEARN DRAFT                │
│              ↓                         │
@lectio/page  STUDENT PREVIEW            │
│              ↓                         │
PDF          EXPLICIT PUBLISH            │
               ↓
           LearnRelease
               ↓
           DISTRIBUTE
               ↓
        LearningInstance
               ↓
            RUNTIME
               ↓
      Attempts / Evidence
               ↓
            INSIGHT
```

## Source repositories at program design time

Target monorepo:
- `richiewaweru/lectio-xplore-monorepo`
- observed main head when this packet was authored: `bd19a9060b637b84f6d86c002cbf01513adf1e4b`

Active component-Xplore source:
- `richiewaweru/text-book-generator`
- branch: `xplore`
- observed head: `8509233c9da462a2f163e1acc735f1092fcdb4ce`

Standalone component Lectio:
- `richiewaweru/lectio`
- branch: `master`
- observed head: `f71e78cdbb06a2169c60b937213fa4db6996c69f`

These SHAs are historical anchors only. Phase 0 MUST record the actual SHAs and working-tree state before any implementation begins.

## Immutable product decisions

1. `@lectio/page` owns Print/PDF.
2. Component Lectio becomes web-native `@lectio/learn`.
3. Print and Learn share lesson meaning upstream, not realization machinery.
4. Existing working component generation is preserved unless a verified incompatibility requires change.
5. Existing Builder/edit-in-place experience is preserved and becomes the Learn authoring surface.
6. Existing document persistence/history/offline sync are reused.
7. Page inline editing is deferred.
8. Publishing is explicit.
9. Published `LearnRelease` is immutable.
10. Default learner navigation is sequential forward; completed sections are revisitable.
11. V1 completion = required sections completed + required interactions attempted.
12. Practice and graded evidence are separate and both visible.
13. Learner attempts are immutable source truth; scores/progress are derived.
14. V1 concept state uses simple transparent bands such as Strong / Developing / Needs Practice.
15. Distribution supports multiple classes, multiple learners, invitations, teacher-created learners, whole-class and selected-student assignment.
16. Default assignment audience policy is rolling.
17. A `LearningInstance` bridges distribution and runtime.
18. Student lessons are section/tab oriented, not long-scroll by default.
19. New UI extends the existing Xplore visual language instead of inventing a separate product aesthetic.
