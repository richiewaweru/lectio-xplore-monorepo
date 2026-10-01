# Learn Realization

## Target

```text
verified SharedLessonDocument
→ copy/realize ordinary nodes
→ TaskAnchor → Learn interaction
→ Learn runtime metadata
→ LearnDocument
```

Learn owns interaction implementation, feedback, attempts/completion, progress, navigation, responsive UX and publish/release.

Learn does not own ordinary composition, ordinary prose writing, section titles, pedagogical continuity or task meaning.

## Cutover

1. Add SharedDocument-based Learn consumer.
2. Prove interaction mapping, open/reload, evaluation, progress and publish.
3. Route all new Learn creation through it.
4. Zero-caller sweep old Learn ordinary authoring.
5. Delete old composition/writer calls/prompts/tests.
6. Add architecture guard: Learn generation cannot invoke ordinary section authoring.

Retry Learn from exact SharedDocument hash. Learn failure does not mutate SharedDocument/Print.
