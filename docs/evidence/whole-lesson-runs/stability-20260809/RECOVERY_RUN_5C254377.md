# Fresh superseding native run

Date: 2026-08-09

Generation: `5c254377-4d7f-40bd-a599-d9a9dd3e0bab`

This is the fresh product-native successor to diagnostic terminal generation
`ea292446-abba-40d9-8b5e-6a904fa71653`. It was created from the visible Units
`Start fresh` action; the terminal row was not mutated or requeued.

## Persisted identity at structural review

- Created: `2026-08-09 18:41:38.603063` UTC
- Status/stage: `awaiting_review`
- Mode/template/preset: `v3` / `guided-concept-path` / `v3-studio`
- Document contract: `2`
- `native_whole_lesson`: `true` in root state and context
- Execution started: `false`
- Path: `a428c5ee-5499-4b1b-8ada-3a5c1f9b3b6c`
- Lesson: `0410a02a-36f7-4a04-98de-7cd757d4ea60`
- Objective hash: `ea0293035edd55b66b31f8dbce87f884823264ebf3d6c4e5f1b577abf37e1f90`
- Preparation key: `bce8969315241484a3a683ce31d8f3cff493d1ae1b8a95f91d2fd9f1c9486b65`

There are no items, teaching summary, generation steps, `page_document_v2`, report,
candidate/final/reloaded hashes, or reload proof yet. That is coherent for structural review.

No `editable_lessons` or `learning_packs` record references this generation or its terminal
predecessor.

## Supersession provenance

- New `supersedes_pack_id`: `ea292446-abba-40d9-8b5e-6a904fa71653`
- Regeneration reason: `The previous generation did not finish.`
- Old provenance invalidated: `2026-08-09 18:41:38.669188` UTC
- `path_lessons.pack_id` now points to the fresh generation

This proves the product regeneration workflow preserved terminal history and created a new native
identity rather than weakening the terminal state machine.

## Structural provider call

- Call ID: `2c3a6664-cf68-4130-877d-539be6595902`
- Trace: `path-regenerate:2f297058-f6bc-47bf-9ffd-3208ad8246d4:93304b104ad54087afacd2d720103d39:structural1`
- Node: `v2_path_structural_planner`
- Provider/model: `api.deepseek.com` / `deepseek-v4-pro`
- Attempt/outcome: `1` / success
- Recorded provider latency: `31,401.1462 ms`
- Tokens: 3,087 input; 1,575 output; 1,020 thinking

The backend log independently records HTTP 200 from the provider and HTTP 200 from the
regeneration route. No dropped-attribution warning was found.

The call is intentionally pre-generation and therefore has `llm_calls.generation_id=NULL`.
Correlation is by the unique registered-user regeneration trace and request window, not a
generation foreign key. `started_at` and `completed_at` are also null, so the live timing table
must cite recorded latency plus backend request timestamps and must not imply stronger direct
generation attribution.

## Live item recovery proof

The backend was restarted with `V3_ITEM_EXECUTOR_BASE_URL=http://127.0.0.1:65534` after verifying
that port was closed. The normal Studio `Review concepts` action exhausted three item attempts:

| Attempt | Latency | Class | Retryable |
| --- | ---: | --- | --- |
| 1 | 10,389.21 ms | `TRANSPORT` | true |
| 2 | 7,638.39 ms | `TRANSPORT` | true |
| 3 | 7,449.62 ms | `TRANSPORT` | true |

The authoritative generation status became `failed_recoverable`; checkpoint
`item_generation`; `next_action=retry_items`. Studio truthfully rendered `Retry lesson items` and
`Connection error.` No item, teaching, form, block, or final-document artifact leaked through the
failed checkpoint.

The item endpoint was then restored and the visible retry was accepted. The retry produced
exactly five distinct approved item rows and one successful real provider call. No duplicate item
was created.

## Live worker death and stale-lease reclaim

- Old owner: `native-17cb835acf80`, token `1`, claimed `18:58:26.269549` UTC
- Old listener PID: `33844`
- Old app instance: `a213b4ba-d428-404c-842d-5649685a5260`
- Kill time: `2026-08-09T22:00:10.7972261+03:00`
- Last heartbeat: `19:00:06.742059` UTC
- Lease expiry: `19:01:36.742059` UTC
- New owner: `native-1e907ab8e4f0`, token `2`
- Reclaim: `19:02:32.541906` UTC
- Item checkpoint complete: `19:04:25.276851` UTC

The backend remained stopped beyond the persisted 90-second lease and was restarted normally.
The new worker reclaimed with a larger token and completed the real item call. Zero persisted
events or successful item writes from old token 1 occurred after reclaim. This proves absence of
an accepted stale-owner write; it does not claim that a late write was attempted and rejected.

## Live teaching transport recovery proof

The teaching endpoint was then pointed at the same verified closed port. Both internal planner
attempts failed with `ModelAPIError` at about 7.67 seconds and 7.53 seconds. The newly corrected
boundary preserved the typed failure:

- authoritative status: `failed_recoverable`
- checkpoint: `planning_teaching`
- code/class: `TRANSPORT` / `ModelAPIError`
- `next_action`: `retry_teaching`
- visible UI: `Retry teaching plan` and `Connection error.`

The item count remained exactly five and no form, writer, or final document artifact existed.

## Second diagnostic terminal finding

After restoring the teaching provider, the visible teaching retry ran two real provider attempts.
Both drafts violated current deterministic teaching rules. The final draft still included:

- an excluded term (`cellular respiration`);
- an unknown evidence reference (`approved_item_ids`);
- all five MCQ source IDs in one block, violating `MCQ_SOURCE_CARDINALITY`.

The validator correctly rejected the deterministic content and the run became `failed_terminal`.
However, the system prompt still said that the model could place a plural “questions block” and
name approved items, contradicting the new singular-MCQ ownership invariant. This generation is
therefore retained as a second diagnostic failure and cannot satisfy targeted A/C or the final
matrix. The prompt/repair contract must be synchronized before creating its successor.

## Telemetry discrepancies found

The authoritative item/teaching attempt ledgers correctly record outer attempts and retryable
transport classification, but the corresponding `llm_calls` rows record `attempt=1` and
`retryable=false`. Also, the report projection remained `running/streaming_preview` at the first
recoverable item checkpoint while generation/native status was authoritative
`failed_recoverable`. These are open evidence/projection defects; acceptance reports must not use
the stale fields as authoritative.
