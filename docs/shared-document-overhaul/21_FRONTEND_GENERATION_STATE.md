# Frontend Generation State

## One build view

Example:

```text
Teaching Plan        ✓ Approved

Shared Document      Running
  Composition        ✓
  Orient             ✓
  Recall             ✓
  Explain            ↻ Attempt 2
  Contrast           ✓
  Check              ✓
  Continuity         Waiting
  Document QA        Waiting

Learn                Not started
Print                Not started
```

## Rules

- render backend-authoritative status/stage;
- show work-item progress;
- surface recoverable failure immediately;
- stop polling at non-active states;
- expose only backend-provided actions;
- never imply success while required child work failed;
- concise user-safe error by default;
- detailed diagnostics only in advanced/debug surface.

## Teaching Plan review

Default teacher view should show human pedagogy: learner title, section title, purpose, learner actions and expected evidence.

Continuity internals may appear under expandable instructional details.

## Shared preview

A ready SharedDocument should be previewable before/alongside Learn/Print realization. This helps prove author-once behaviour.
