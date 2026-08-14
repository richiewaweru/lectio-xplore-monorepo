# Live acceptance runbook

This runbook covers only the acceptance work that deterministic tests cannot
prove. It must be used through the authenticated browser at `http://127.0.0.1:5173`
with the backend on `http://127.0.0.1:8000`.

## Before spending provider credits

- Confirm the user is signed in manually.
- Confirm ports `5173` and `8000` are healthy; do not touch `5174` or `8001`.
- Confirm the current generation is not already being retried by another worker.
- Record the generation ID, unit ID, lesson ID, and start timestamp.
- Do not use hidden endpoints, direct DB edits, legacy Builder conversion, or
  manual viewer navigation as progression.

## Targeted proof order

1. Form timeout/retry: prove `failed_recoverable -> retry` resumes at the form
   checkpoint without rerunning items or teaching.
2. Home/New: create through `/units` and verify native identity from creation
   through structural review.
3. Ready navigation: remain on Studio and capture the automatic viewer route.
4. Visual: require a visual lesson, inspect provider/QC/asset/revision/hash
   evidence, then inspect viewer and both PDFs.
5. Worker reclaim: only if a recoverable checkpoint exists, stop/restart the
   worker without DB edits and capture old/new lease tokens and reclaim event.

## Visual acceptance stop gates

- Stop before approval if the required structural slot is not `visual_required=true`.
- Stop before teaching approval if the required visual intent/brief is missing
  the authoritative entities, stages, movement, labels, and exclusions.
- Stop after form planning if the required slot has no legal `figure` decision or
  no persisted `visual_pending` request.
- Accept only a real provider asset whose final QC is accepted, whose current
  document revision is persisted, and whose fresh-session reload hashes match.
- A flagged/rejected visual is not final evidence. Use only the existing
  visual-only retry path; never rerun upstream stages.
- If deterministic topology recovery is used, capture its persisted topology,
  source/label/evidence digests, renderer version, source/final hashes, and
  prove no image-provider call occurred for that recovery.

## Required evidence per accepted run

Capture path, prepare, structural, items, teaching, form, writers, assembly,
persist/reload, visual, viewer, teacher PDF, student PDF, and total wall time.
For every provider call capture provider/model, stage, attempt, start/end,
duration, outcome, retryability/error class, and whether it was a repair call.
Record parallel writer wall time separately from cumulative provider duration.

## Final matrix

Run four new lessons through the normal UI only:

1. Grade 4 Science — Why Plants Need Light to Make Food.
2. Grade 6 Mathematics — Understanding Equivalent Fractions.
3. Grade 8 Economics — How Supply and Demand Affect Price.
4. Grade 7 English — Distinguishing a Claim from Supporting Evidence.

Do not mark the matrix complete until all four have native identity, accepted
PDF/viewer evidence, current equal reload hashes, attributable telemetry, and a
zero-current-legacy-runtime audit.

## Capture and verify commands

After the authenticated browser has exported the generation-page screenshot and
the teacher/student PDFs, copy those files locally and run:

```powershell
cd C:\Projects\lectio\apps\textbook-agent\backend
.\.venv\Scripts\python.exe scripts\capture_whole_lesson_evidence.py `
  <generation_id> `
  --run run-01-science `
  --generation-page C:\path\to\generation-page.png `
  --teacher-pdf C:\path\to\teacher.pdf `
  --student-pdf C:\path\to\student.pdf

.\.venv\Scripts\python.exe scripts\verify_whole_lesson_acceptance.py `
  C:\Projects\lectio\docs\evidence\whole-lesson-runs\run-01-science
```

Capture is read-only against generation state. It copies the supplied browser
artifacts; it does not manufacture screenshots or PDFs through hidden API
progression. Verifier exit `0` means every represented final gate passed.
Exit `2` means evidence is incomplete or a gate failed. Any other nonzero
exit means the evidence folder is malformed or unreadable.
