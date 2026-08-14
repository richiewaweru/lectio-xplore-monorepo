# Lesson-approach prompt v2 amendment

Date: 2026-08-11

The native whole-lesson planner now uses the corrected lesson-approach prompt
as version 2. The correction makes assessment ownership explicit: a
multiple-choice `source_question_ids` array is empty or a singleton, may only
appear on an eligible assessment intent, and an approved item may be owned by
one teaching block at most.

## Registered prompt artifacts

| Role | Resource | SHA-256 | Use |
| --- | --- | --- | --- |
| Active | `lesson-approach-planner-v2.txt` | `2ccc4c7b1a36000040d74930ce5d8ada55de1a2279b0df0c08ae286650032004` | Native whole-lesson planner |
| Historical | `lesson-approach-planner-v1.txt` | `475b8b178f74c1397742b12002a324e18ae3e39a4fffd9e7a4c199713780a9cd` | Frozen compatibility/reference artifact |
| Unchanged | `form-planner-v1.txt` | `b1990a00f0b5bf75a7dec02babf7c567b12b36a336419da029c233790fd78316` | Form planner |

The active accessor is `planning.prompts.lesson_approach_planner_prompt()`;
its version constant points to v2. The v1 name remains registered in the
resource accessor and has a dedicated historical accessor for read-only
verification. Evidence capture writes the active prompt file, version, and
checksum into each run manifest.

The v2 amendment also makes a fixed `visual_required: true` slot contractual.
The planner must express the visual teaching job through a permitted intent
such as `show-structure`, `trace-flow`, `sequence`, or `name-parts`; its brief
must carry the exact subject, labels/stages, relationships, and anchor use.
The prompt deliberately forbids page-object IDs and renderer/layout language,
so the visual handoff remains pedagogical and implementation-independent.

## Verification

The offline verifier checks all three checksums and continues to reject the
retired `section-block-planner-v1.txt` resource. Focused tests cover active
accessor selection, historical v1 byte identity, manifest metadata, and
capture output. The amendment does not change form-planner content or any
provider, server, database, or browser behavior.
