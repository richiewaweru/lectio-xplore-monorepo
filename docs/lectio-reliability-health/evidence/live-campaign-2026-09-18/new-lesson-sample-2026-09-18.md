# Fresh new-lesson sample — 2026-09-18

Status: `PASS WITH FLOW FOLLOW-UP`

Purpose: sample two genuinely new teacher-created lessons after the earlier A–D
campaign, measure speed, observe errors, and identify shaky transitions. The
visual figure issue was intentionally left pending and neither sample required
visual generation.

## Runtime

- Browser: authenticated Codex In-app Browser.
- Frontend/backend: local servers on ports 5173/8001.
- Database: repository PostgreSQL container `textbook-agent-db-1` only.
- Provider: configured real provider path; live backend logs showed DeepSeek
  calls returning HTTP 200.
- No credentials or environment files were changed.

## Sample 1 — Water Cycle / Evaporation

- Unit: `b635ceee-ecac-4f05-b0bf-c9abb374ba1d`
- Lesson: `0a7ece4c-072c-4e82-ac06-395408a49bb6`
- Fresh unit prompt: water cycle with evaporation, condensation,
  precipitation, collection, one sequence activity, and one check question.
- Generated lesson title: `Evaporation`.

### Observed flow and timings

| Transition | Observation |
|---|---|
| Readback submission | UI request returned in about 1 second; readback appeared after about 2.5 seconds. |
| Accept readback → unit | Unit workspace appeared after about 3 seconds; five lessons were planned. |
| Lock unit | UI response about 1 second; durable state became `LOCKED IN` after about 1.8 seconds. |
| Prepare Lesson | Request returned in under 1 second; structural plan appeared after about 6 seconds. |
| Review concepts | Request returned in under 1 second; durable generation reached `awaiting_teaching_approval`. A refresh was needed before the Teaching Plan controls appeared. |
| Approve plan | Request returned in under 1 second; approval appeared after about 1.8 seconds. |
| Create Learn | Native Learn row created at `2026-09-18 17:19:58.801717` and became ready at `17:21:38.328862`: about **99.5 seconds**. |
| Learn preview | The Learn row became durably `ready`; the first sample was not opened for a final node-count snapshot. |

### Result

Structural preparation, Teaching Plan approval, and Learn generation succeeded.
The main issue was latency and intermediate status inconsistency: after the
generation had progressed, the page header showed `Ready Learn` while the output
card still showed `Preparing` until a later refresh. This is a status projection
/hydration concern, not a provider failure.

Print was not generated for this sample.

## Sample 2 — Equivalent Fractions / Area Models

- Unit: `645c0ae6-9fe6-47b0-869b-f7133d6e60f2`
- Lesson: `430dbcc2-9b12-43c4-b1ad-3e25df716a3b`
- Fresh unit prompt: equivalent fractions with visual area models, a worked
  example, and a check question.
- Generated lesson title: `Representing Fractions on an Area Model`.
- Learn output: `learn-out-6a553c638720`.
- Print output: `8f2cb480-a71e-4cb3-9b0d-965904f45fb3`.

### Observed flow and timings

| Transition | Observation |
|---|---|
| Readback submission | UI request returned in about 1 second; readback appeared after about 3 seconds. |
| Accept readback → unit | Unit workspace appeared after about 3 seconds; four lessons were planned. |
| Lock unit | UI response about 1 second; durable state became `LOCKED IN` after about 1.8 seconds. |
| Prepare Lesson | Request returned in under 1 second; structural plan appeared after about 7 seconds. |
| Review concepts | Durable generation reached `awaiting_teaching_approval`; a reload was needed before the Teaching Plan controls appeared. |
| Approve plan | Request returned in under 1 second; approval appeared after about 1.6 seconds. |
| Create Learn | Native Learn row created at `2026-09-18 17:24:34.892353` and became ready at `17:26:04.085435`: about **89.2 seconds**. |
| Learn preview | Rendered successfully with 26 nodes, guided interaction, and choice interaction. Preview displayed `PREVIEW — ATTEMPTS ARE NOT SAVED.` |
| Create Print | Print row created at `17:26:51.865568` and became ready at `17:27:01.154024`: about **9.3 seconds**. |
| Print preview | Rendered the lesson, worked example, guided task, check question, and answer key. |
| PDF export | Download dialog opened and the teacher-edition export action was invoked. The browser did not expose a physical PDF file for visual inspection. |

### Result

The complete teacher authoring path through Learn and Print succeeded for this
sample. No user-visible application error appeared. The main operational cost
was provider-backed Learn latency of roughly 1.5 minutes.

## Most common failures and likely source

1. **Long asynchronous Learn generation (observed in both fresh samples).**
   The native row stays `running` for roughly 89–100 seconds while the provider
   performs multiple structured calls. The risk is user impatience, duplicate
   clicks, or a false perception of a stuck job.

2. **Status/projection desynchronization (observed again).** The Plan header and
   output card can disagree during hydration: `Ready Learn` appeared alongside
   `Preparing`. Refreshing reconstructed the durable state. This points to
   competing status projections or a hydration race, not the provider itself.

3. **Visual Print remains provider-bound.** The earlier visual case received an
   xAI HTTP 403 and remains queued with `Figure pending`. This does not affect
   these two non-visual samples, but it is the largest known content-shape
   failure.

4. **Legacy/stale preparation identities.** Earlier seeded lessons exposed stale
   generation IDs and legacy approved snapshots. The normalization and retry
   repairs address this for current paths, but old data remains more fragile
   than newly created lessons.

5. **PDF evidence visibility.** UI export completes, but the in-app browser did
   not expose the resulting file for filesystem inspection. This is an evidence
   and verification gap rather than a confirmed PDF-generation failure.

## Current flow confidence after this sample

For a new non-visual lesson, confidence is now stronger: both fresh lessons
completed preparation, approval, and Learn; one completed Print and preview.
The remaining concerns are asynchronous latency, status truthfulness during
polling, visual-provider access, and PDF artifact verification. These samples
did not include class assignment or learner completion.
