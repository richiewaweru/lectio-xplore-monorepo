# Run D — downstream after the teacher gate

**Generation:** `ee64d939-6f31-4fc4-9702-395580d25302` ("Plants as Producers")
Prepared and driven entirely through the browser after Corrections 4 and 5.

This run reached **far** deeper than any previous attempt: form planner, writers,
assembly, persistence and a hash-verified reload all executed.

## Stage sequence

```
awaiting_review          -> structural plan rendered, approved in browser
stage2_running           -> item generation (2 attempts, 1 discarded)
awaiting_teaching_approval  <- TEACHER GATE (see 40-teacher-gate-proof.md)
planning_forms           -> form planner            PASS
writing_sections         -> 8 writer blocks         PASS
document_assembling      -> LectioDocumentV2        PASS
awaiting_visuals         <- STALLED HERE
```

## Post-approval latency

| Stage | Duration | Attempts | Result |
|---|---|---|---|
| Form planner | **63.21 s** | 1 | PASS |
| Writers (10 provider calls, parallel) | see below | 1 each | PASS |
| Assembly + persist + reload | ~1.6 s | 1 | PASS |

**Writers — parallel, measured correctly:**

```
calls:                10
fastest:              15.18 s
slowest:              67.43 s
sum of durations:    352.18 s   <- NOT the elapsed time; do not report this as total
WALL-CLOCK total:    162.70 s   <- the real cost
```

Six writers launched concurrently at 17:14:46–47. Summing parallel durations would
overstate writer cost by **2.2x**.

## Persistence and reload — PROVEN

```
execution.document_sha256           c3d7566a4486e590c96a30d09369c5b0e62072aa4339b123c1c059b9b6c64708
execution.candidate_document_sha256 c3d7566a4486e590c96a30d09369c5b0e62072aa4339b123c1c059b9b6c64708
execution.reloaded_sha256           c3d7566a4486e590c96a30d09369c5b0e62072aa4339b123c1c059b9b6c64708
execution.reload_verified           true
execution.attempt                   1
generations.document_json           NOT NULL (4,278 bytes)
document_revision                   1
```

All three hashes identical and `reload_verified: true` — the document was written to
Docker Postgres, read back, and the hash matched. This is the DB-first assembly plus
reload verification the architecture requires, and it is **CONFIRMED**.

Note `execution.worker_id` and `claimed_at` remain `null` while `attempt=1` and
`lease_token=1`: this execution ran inline rather than through a native-worker claim, so
the worker's claim path is still **UNCERTAIN** — it started cleanly but never had a job
to claim.

## The assembled document is genuine LectioDocumentV2

```
document_version : 2
kind             : v3_booklet_pack
lectio_document  : id, title, language, metadata, sections, answer_key, contract_version
metadata         : subject=Science, grade_level=Grade 4, lesson_mode=first_exposure,
                   knowledge_type=conceptual, native_whole_lesson=true,
                   catalogue_version=1.1.0
sections         : 4
answer_key       : present
```

Content is real and traceable to the approved teaching plan. `orient-b1` renders the
garden anchor the teacher approved:

> "Imagine a sunny garden where sunflowers, tomato plants, and green beans grow a little
> taller each day… nobody ever adds plant food or fertilizer… If no one is feeding them,
> where does the plant's food come from?"

Blocks carry `id`, `intent`, `object` (`prose`, `list`, …), `layout.placement` and
`position`. No fixtures, no placeholders, no legacy conversion.

## Where it stops — `awaiting_visuals` (classification: ORCHESTRATION)

```
17:17:30.549  visual_pending          block_id=explain-b1  section_id=explain
17:17:30.742  document_assembling
17:17:31.090  document_awaiting_visuals
```

Then nothing. Stage has remained `awaiting_visuals` with **no further activity of any
kind** — and, decisively, **no image-provider call was ever made**. The backend log
contains zero requests to the configured image provider (`PIPELINE_IMAGE_PROVIDER=xai`,
`grok`), so nothing is in flight and nothing will arrive.

The document is complete and reload-verified; it simply never leaves `awaiting_visuals`
because the visual for one block (`explain-b1`) is requested and never produced.

Worth noting for the contract trace: the **structural plan marked every section
`visual_required: false`**, yet the form planner selected a visual object for
`explain-b1`. That is legitimate if `visual_required` is advisory to the form planner —
but it means a lesson the structural layer said needs no visuals cannot complete because
of a visual.

**This is the new furthest-reach blocker**, and it is a genuinely different one from the
teaching-plan failure that stopped every earlier attempt.

## Not proven in this run

* **Viewer render** — the documented route `/textbook/[id]` returns 404 (stale docs; the
  real route is `/studio/generations/[id]`). That route sits on "Loading session…" and
  logs `[chunked stream error] AbortError`, so the reloaded document was **not** rendered
  in the viewer. NOT PROVEN.
* **Teacher / student PDF export** — not reached, because the generation never leaves
  `awaiting_visuals`. NOT REACHED.
* **Answer-key visibility difference** — `answer_key` exists in the persisted document,
  but the two PDFs were never produced, so the difference is unverified. NOT REACHED.
