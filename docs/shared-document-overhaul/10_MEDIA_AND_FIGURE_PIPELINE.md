# Media and Figure Pipeline

## Timing

A validated semantic FigureNode is enough to start media generation.

```text
Section Writer
  ↓
validate FigureNode
  ↓
freeze figure semantic/spec
  ↓
enqueue media work item
```

Different figures may run concurrently while other sections are still writing.

## Required media

If a composed figure is needed to satisfy the section contract, its failure blocks SharedDocument READY.

Do not claim visual readiness with a required failed figure.

Avoid decorative media in the first cutover.

## Separation

Never expose provider errors as captions/alt text. Keep display/accessibility/diagnostics separate.

## Runtime

Media uses the same durable work-item mechanics: lease/fence, bounded retries, checkpoint, typed failure and targeted retry.

## Model slots

Visual text QC: **FAST** by default.

Actual image generation remains behind the existing media provider abstraction.
