# Final End-to-End Acceptance

Use fresh data. Old lesson artifacts are explicitly out of scope.

## Flow 1 — Learn

```text
create Unit
→ concepts/path
→ prepare lesson
→ generate Teaching Plan with learner tasks
→ approve Teaching Plan
→ choose Learn only
→ Learn realizer
→ document writers
→ interaction writer only where task requires
→ assemble LearnDocument
→ persist
→ open editor
→ edit/reorder/add
→ save/reload
→ preview/student shell
→ answer retained interaction
→ runtime evaluation
→ publish/reload release
```

## Flow 2 — Print

```text
same approved Teaching Plan
→ choose Print only
→ Print realizer
→ document content
→ Print task treatment
→ page assembly
→ persist
→ reload
→ PDF
```

## Flow 3 — path independence

1. Generate only Learn and prove no Print output is created.
2. Return to the approved Teaching Plan.
3. Generate Print.
4. Prove Print reads the Teaching Plan/preparation, not LearnDocument.
5. Repeat in reverse on another lesson.

## Final acceptance

- at least 3 fresh lessons across different instructional shapes
- at least one lesson using multiple retained interactions
- at least one Print lesson with written-response treatment
- at least one figure/table-heavy lesson
- no manual database patching
- no manual JSON repair
- no legacy fallback
- exact commit SHA recorded
