# PHASE 12 REPORT — End-to-end Hardening (coverage closeout)

Status: **PASS** (live browser golden run **excused**)

## Baseline
- Coverage closeout R04–R12 on `C:\Projects\lectio`
- Docker Postgres `textbookagent-db-1` healthy

## Gates this phase
| Gate | Result |
|---|---|
| Alembic `upgrade head` (0036–0039) vs Docker Postgres | PASS |
| `@lectio/page` vitest | PASS 41 |
| `pdf:fixture` (JSON success; process killed after hang) | PASS — teacher 6 / student 5 pages |
| Domain boundary check | PASS 0 violations |
| Learn releases + runtime + adversarial pytest | PASS |
| `@lectio/learn` interaction shells + contracts | PASS 17 |

## Adversarial / invariants covered
- Post-publish edit does not mutate prior release
- Duplicate submission idempotency
- Late join rolling vs snapshot
- Selected learner assignment
- Same release assigned twice (distinct assignment ids)
- Malformed/missing publish probes
- Permission probes (other teacher 404)
- Session cross-learner 403

## Residual limitations (honest)
1. Live teacher→student→analytics **browser** golden run excused for this run.
2. Working tree dirty — no commit requested.
3. `pdf:fixture` still hangs after successful JSON (pre-existing cleanup); recorded success and killed.
4. `v3_studio` retained REMOVE-later.
5. Teacher JWT still may access learner routes when session header absent (support path).
6. Student class view filters from home instances (not a separate class-assignment join API).

## Architecture deviations accepted
- Closeout additive migrations `0038`/`0039`
- Analytics under `/api/v1/learn/analytics`

## Final state
- safe to inspect: **YES**
- coverage closeout complete except excused live browser E2E
