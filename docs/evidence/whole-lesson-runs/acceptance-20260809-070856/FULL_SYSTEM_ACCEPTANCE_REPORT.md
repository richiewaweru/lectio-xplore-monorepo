# Xplore Full-System Acceptance Report

Date: 2026-08-09 (Africa/Nairobi)  
Verdict: **NOT YET STABLE**

## Environment freeze

- Branch: `main`
- Baseline and final HEAD: `ba9dccda18be815c8e0239490029612aeec119a7`
- Required services: frontend `127.0.0.1:5173`; backend/native worker `127.0.0.1:8000`; Docker Postgres `127.0.0.1:5432/textbook_agent`
- Unrelated listeners `8001` and `5174` were not touched.
- Database container: `textbookagent-db-1`, PostgreSQL 16, healthy.
- Native routing: enabled; successful native records persisted `native_whole_lesson=true`.
- Text provider: OpenAI-compatible DeepSeek (`deepseek-v4-flash` / configured pro tier).
- Image provider: xAI, `grok-imagine-image`.
- Credential values were not recorded. Presence checks only were used.
- Pre-existing untracked evidence and temporary files were preserved.

## Run records

| Run | Requested lesson | Generation | Native | Result | Duration / terminal evidence |
|---|---|---|---|---|---|
| 1 | Grade 4 Science — Why plants need light to make food | `f514db66-b565-4c78-a53e-cc15093b5131` | yes | `failed_terminal` | 04:31Z–04:57Z; item timeout recovered through visible retry, then form planner timed out twice and was misclassified terminal |
| 2 | Grade 6 Mathematics — Understanding ratios using real-life comparisons | `3099d8e2-d919-4da7-9718-a54eed342791` | yes | `ready` | 05:01Z–05:13Z, approximately 12 minutes |
| 3 | Grade 7 Social Studies — How trade routes shaped East African coastal cities | `68d8e184-f3e5-45e4-874c-c0191c759a98` | no | stopped at `awaiting_review` | The Home/New lesson UI created a legacy builder record after structural review. Stopped immediately; not counted as a native acceptance success. |
| 4 | Grade 6 Science — The water cycle with labelled diagram direction | — | — | not run | Further provider use stopped after mandatory P1 failures and loss of reliable in-app-browser navigation. |

The four required native successful runs were therefore **not proven**.

## Detailed stage evidence

### Run 1

| Stage | Evidence | Classification |
|---|---|---|
| Intent/path | Unit `a388f556-6876-4181-a1ef-8de7ce8a308f`; browser gates used normally | EXPECTED |
| Structural approval | Approved through UI at about 04:37:51Z | EXPECTED |
| Browser interruption | Original tab became unusable; a fresh tab reloaded persisted progress while generation continued | RECOVERED |
| Items | First provider attempt timed out; persisted `failed_recoverable` | RECOVERED after UI fix and visible `Retry lesson items` action |
| Teaching | Reached teacher gate; approved through UI at about 04:55:15Z | EXPECTED |
| Form planning | Two provider attempts timed out; wrapper converted timeout to unknown terminal failure | BUG, P1 |
| Viewer/PDF | Unavailable because generation was terminal | FATAL for this run |

### Run 2

| Stage | Approximate evidence | Classification |
|---|---|---|
| Start/readback | 05:01:34Z / 05:02:14Z | EXPECTED |
| Prepare | 05:03:53Z | EXPECTED |
| Structural approval | about 05:05:42Z | EXPECTED |
| Teaching gate/approval | about 05:10:30Z / 05:10:38Z | EXPECTED |
| Form/writers/assembly | completed; DB `status=ready`, state `stage=ready`, document revision observed as 6 during live checkpointing | EXPECTED |
| Review UI after ready | remained “Building your lesson…” until manual route change/reload | BUG, P1 |
| Viewer | `/studio/generations/3099d8e2-d919-4da7-9718-a54eed342791`; V2 document, 5 ordered sections, fully loaded | PASS |
| Teacher PDF | visible UI request, answers enabled, backend HTTP 200, print-ready selector found | PASS after export-status fix |
| Student PDF | visible UI request, answers disabled, backend HTTP 200, print-ready selector found | PASS after export-status fix |

## Persistence and state consistency

- Run 1: `GenerationModel.status=failed_terminal`, `chunked_state_json.stage=failed_terminal`, `native_whole_lesson=true`; UI terminal state agreed after reload.
- Run 2: `GenerationModel.status=ready`, `chunked_state_json.stage=ready`, `native_whole_lesson=true`; the standalone viewer loaded a fresh V2 document correctly.
- Run 2 `report_json.booklet_status` remained `streaming_preview` even though the native document was ready. The viewer initially synthesized an unsupported `final` status, disabling PDF export.
- `document_sha256`, `reloaded_sha256`, and `reload_verified` were empty in persisted report telemetry for both native runs. Exact hash equality is **NOT PROVEN** even though fresh document reload rendered successfully.
- `generation_steps` contained no rows for these native generations. Recalculation and per-writer persistence cannot be audited from that table.

## Viewer, PDF, and visual evidence

- The Run 2 real viewer rendered five sections in manifest order and displayed the teacher answer key.
- Both PDF variants reached the native `lectio-page-v2` print route and its ready selector. HTTP responses were 200.
- PDF logs noisily attempted the legacy V3-pack adapter first and emitted five invalid-section warnings before the native V2 renderer succeeded. Classified `NOISY-BUT-HARMLESS` for Run 2.
- The in-app Browser download surface did not expose a durable local download path, so binary file-size inspection and opening the downloaded bytes outside the print renderer are **NOT PROVEN**.
- Run 3's structural plan requested an Indian Ocean route/monsoon diagram, but the attempt was stopped at the legacy routing boundary. The required water-cycle visual provider/asset/patch/viewer/PDF chain is **NOT PROVEN**.

## Recovery proofs

| Recovery | Result |
|---|---|
| Browser interruption/reopen during work | PROVEN on Run 1; persisted reconnection did not stop generation |
| Visible item retry | PROVEN after targeted UI fix; only the recoverable native stage was retried |
| Teaching failure injection | NOT PROVEN; no supported safe acceptance hook was used |
| Worker restart, lease reclaim, old-lease fencing | NOT PROVEN; not attempted after terminal failures |
| Visual-only retry | NOT PROVEN; no actual visual provider failure reached |

## Telemetry population matrix

| Signal | Status | Evidence |
|---|---|---|
| Generation ID/status/stage | WIRED AND POPULATED | DB and status endpoints |
| Native routing flag | WIRED AND POPULATED | `native_whole_lesson=true` for Runs 1–2 |
| Provider/model and HTTP duration | PARTIALLY WIRED | verbose backend provider logs; not consistently persisted |
| Attempts/errors/retry action | PARTIALLY WIRED | state/error plus logs; item retry visible |
| Trace IDs | PARTIALLY WIRED | provider/request logs; no complete persisted end-to-end trace |
| Stage timings | PARTIALLY WIRED | logs/checkpoints; no authoritative stage table |
| LLM call events | WIRED BUT EMPTY | repeated `Skipping llm_call persistence without user_id` warnings |
| Worker leases/fencing | PARTIALLY WIRED | worker identity visible; restart/fencing not exercised |
| Document revision | PARTIALLY WIRED | revision observed live; not exposed in final report fields queried |
| Document/reload hashes | MISSING | persisted fields empty |
| Visual events/assets | MISSING for exercised successful run | no completed visual run |
| PDF terminal status | PARTIALLY WIRED | HTTP/log stages populated; durable file evidence unavailable |
| Terminal completion | WIRED AND POPULATED | Run 2 `ready`; Run 1 terminal failure |

Production debuggability is insufficient: provider logs are detailed but persistence is incomplete, native stage timing is fragmented, and reload hashes and user-attributed LLM events are absent.

## Targeted acceptance-only fixes

No commit or push was made.

1. Added visible native retry handling for recoverable item/teaching/visual stages and corrected the misleading “teaching approved” message.
2. Preserved the original timeout exception after form-planner attempts are exhausted so timeout classification remains recoverable.
3. Mapped completed V2 page documents to `final_ready` so the real viewer enables PDF export.

Regression evidence:

- Frontend Studio suite: 24/24 passed during the run.
- Completed-generation viewer suite: 4/4 passed.
- Backend contract-hardening suite: 20/20 passed (one pre-existing Pydantic warning).

## Issues

| Priority | Finding |
|---|---|
| P1 | Form planner destroyed timeout type and made a recoverable provider timeout terminal. Fixed locally; exact browser scenario not replayed to completion. |
| P1 | Recoverable native failure had no visible retry action and showed an incorrect teaching-state message. Fixed and replayed successfully for item retry. |
| P1 | Native-ready review UI did not transition to the completed viewer. |
| P1 | Completed V2 viewer disabled PDF export due to unsupported synthetic `final` status. Fixed and live-replayed successfully. |
| P1 | Home/New lesson path silently crossed into legacy builder rather than native whole-lesson execution. |
| P1 | Mandatory visual chain and mandatory worker recovery remain unproven. |
| P2 | LLM call persistence drops events when `user_id` is absent. |
| P2 | Native persistence/reload hash telemetry is empty. |
| P2 | PDF export emits invalid legacy-section warnings before successful V2 rendering. |
| P3 | Frequent status/document polling and Svelte history warnings add log noise. |

## Latency and bottlenecks

Only one native run completed, so cross-run statistics are not valid. Run 2 took roughly 12 minutes. Provider waits dominated the observed wall clock; application polling, persistence, and viewer loading were much smaller, although the stale post-ready UI added manual recovery time.

Highest-value improvements (not implemented):

1. Persist per-call/provider and per-stage timing with user and generation attribution.
2. Make the ready transition authoritative and route directly to the completed viewer.
3. Reduce serial provider critical-path work only after telemetry identifies safe parallel handoffs; do not mask timeouts with more retries.

## Scorecard

| Capability | Score |
|---|---|
| Normal native generation | 1/2 attempted native runs completed |
| Visuals | 0/1 mandatory proof |
| Recovery | browser interruption and item retry proven; worker/visual recovery not proven |
| State consistency | partial; DB terminal states coherent, UI ready transition and hash telemetry deficient |
| Latency | poor/insufficient comparative data |
| Telemetry | partial, not production-sufficient |
| Viewer | pass for Run 2 |
| PDF | generation pass for Run 2 after fix; durable opened-file evidence partial |

## Final verdict

**NOT YET STABLE**

Multiple P1 issues were observed, the mandatory visual and worker-recovery paths were not proven, and four successful native browser-driven lessons were not completed.
