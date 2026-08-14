# Form-timeout diagnostic and automatic-retry defect

Date: 2026-08-10

Generation: `5c1407d3-9125-40f1-9b15-531fcee88a3f`

This native successor reached the mandatory teaching-review checkpoint and was approved through
the visible Studio UI. It then proved the typed form timeout but exposed an automatic worker
reclaim loop. Backend 8000 was stopped immediately after diagnosis to halt provider calls. This
generation is diagnostic and cannot count toward targeted proof A or the final matrix.

## Native and teaching-review checkpoint

- Contract/mode: v2 / `v3`
- Native flags: true
- Builder record/route: none
- Supersedes: `607cb648-213c-4be3-b01e-95d7f73b607a`
- Teaching ready: `04:52:08.374641` UTC
- Awaiting approval: `04:52:08.421540` UTC
- Teaching approval: `04:53:05.808973` UTC, revision 2
- Teaching validation: `ok=true`
- Teaching projection hash: `a9530874d702efc409dcd4c87658fe037981b8a8a6ed76e1d95a551ff8885870`
- Audit-only teaching-plan MD5: `81e400aa62c701a82bda8c5d599bc7b8`

One nonblocking teaching-validation issue remained: `MUST_ESTABLISH_UNCOVERED` for `must-1`,
`must-2`, and `must-3`.

## Provider calls before approval

| Node | Attempt | Outcome | Latency |
| --- | ---: | --- | ---: |
| Structural | 1 | success | 34,777.07 ms |
| Items | 1 | success | 81,127.96 ms |
| Teaching | 1 | `UnexpectedModelBehavior` | 118,985.80 ms |
| Teaching | 2 | success | 123,356.23 ms |

Attempt numbering and call-ledger retryable fields were correct.

Exactly five unique non-stale items persisted. The `contrast` misconception block owns exactly
item `i1`; the `check` block owns exactly item `i2`; both match persisted approved records. No
non-assessment block owns an item and no assessment block owns multiple item IDs.

## Form-timeout proof and queue defect

The backend was intentionally started with `PAGE_FORM_PLAN_TIMEOUT_SECONDS=1`. The first form call
began at `04:53:07.638902` UTC, after teacher approval. Each form invocation correctly performed
attempts 1 and 2, both typed `[TimeoutError]`, retryable true, at about 0.98–1.14 seconds.

However, `CLAIMABLE_STATUSES` included `failed_recoverable`. After each persisted recoverable
failure, the worker immediately claimed the same generation again and transitioned it through
`queued` back to `planning_forms` without a user retry.

At the final read before shutdown:

- 65 form-planner invocations;
- 130 failed LLM calls;
- 65 attempt-1 and 65 attempt-2 rows;
- lease token 66;
- execution attempt 131.

The recoverable checkpoint therefore existed only for milliseconds. Normal UI polling usually
saw `planning_forms` plus the previous `TimeoutError`, rendering “Building” instead of the required
`retry_native` action.

Backend listener 8000 was stopped after confirming the loop. Frontend 5173 remained running.

## Checkpoint preservation

- Item and teaching hashes remained unchanged through all observed form attempts.
- Form plan and form projection hash remained null.
- Block outcomes, generation steps, and writer calls remained zero.
- No document was created.

This proves post-teacher checkpoint isolation but not the required user-controlled retry. The queue
contract must exclude parked `failed_recoverable` generations; only explicit native retry
acceptance may make them claimable again.

## Corrected visual retry and native PDF export evidence

After the queue fix, the generation completed through the visible native visual-retry action and
automatically navigated to the native generation viewer. The first two PDF exports still reported
`PDF image failures` because the local image store advertised a missing object URL. The exact
persisted PNG was uploaded to that missing object key without replacing an existing object, and
the exports were repeated through the native PDF endpoint. Subsequent render diagnostics contained
no `PDF image failures`.

Corrected artifacts (API-direct export, 2026-08-10 UTC):

| Edition | Artifact | Pages | Bytes | SHA-256 |
| --- | --- | ---: | ---: | --- |
| Teacher | `5c1407d3-teacher.pdf` | 5 | 543,858 | `AE79629E590E30948BD498C784321BA4B4A663818BED5998C40ABB45F87A77E0` |
| Student | `5c1407d3-student.pdf` | 4 | 530,191 | `22EECC8B263D89F6E7D40A9B88A9C6E7A82F16F20C013F4B6B3601B56D83F047` |

The PDFs were rendered with Poppler `pdftoppm.exe` at 144 DPI and every page was inspected:

- Teacher pages 1-5 and student pages 1-4 render without clipping or broken-image placeholders.
- The sunflower photosynthesis figure is visible on page 3 in both editions.
- Teacher contains one answer-key page (page 5) with two entries; no duplicate answer appendix is
  present.
- Student contains no answer-key page or answer-key text.
- Each PDF embeds one 1024x1024 JPEG figure image.

This is targeted recovery/visual/PDF evidence only. Generation `5c1407d3-9125-40f1-9b15-531fcee88a3f`
is diagnostic and must not count as any of the four new final-matrix runs.

### Persisted reload and telemetry closure (2026-08-11)

A read-only query against the configured PostgreSQL database closed the remaining persistence
gap. The generation is `ready`; `page_document_v2.execution` records:

- `document_sha256=f94de30f5f9b966e8c9e1986c037e930f017453286f3d01eb4dcda714262ad3d`;
- `reloaded_sha256=f94de30f5f9b966e8c9e1986c037e930f017453286f3d01eb4dcda714262ad3d`;
- `reload_verified=true`;
- final lease token `68`, no worker owner, no active work kind, and `last_error=null`.

The authoritative `llm_calls` ledger contains 148 historical rows. The large count is the preserved
evidence of the pre-fix automatic form-reclaim loop, not the corrected retry policy. The successful
explicit recovery call is the single form-planner success at `2026-08-10 05:06:16.877937` UTC
(attempt 1, 53,076.6 ms). All item and teaching calls precede it. Writers follow from 05:06:31
through 05:09:42 UTC. The only visual provider call succeeded at 05:10:14 UTC using
`xai/grok-imagine-image` (30,945.7 ms), followed by one successful visual-QC call at 05:10:19 UTC
(5,394.2 ms).

There are no item, teaching, form, or writer ledger rows after that visual-QC row. The visible
visual-only retry therefore did not rerun upstream work or make another provider call; it reused the
persisted/cached visual result before final reload verification. `started_at` and `completed_at` are
null on these historical rows, so ordering is reported from the populated `created_at` ledger field.

C1 is now closed for persisted hashes, telemetry ordering, retry isolation, viewer, and both PDF
editions. This remains a targeted diagnostic generation and is not eligible for the final matrix.
