# Phase B — Learner-action planning

Status: PASS

## CURRENT
Policy markdown not fed into Teaching Plan; check/practice null actions unvalidated.

## CHANGE
`render_teaching_prompt` injects `learner-action-policy` via canonical loader. `_missing_check_practice_action_errors` fails closed on evidence-bearing check/practice without action while allowing passive blocks.

## CANONICAL CALLER
`print.generation.whole_lesson.teaching_agent.run_lesson_approach_planner` → `render_teaching_prompt` → `effective_prompt_text("learner-action-policy")`

## TEST
`uv run pytest tests/print_learn/test_learner_action_policy.py -q`

## LIVE PROOF
Two fresh Teaching Plans (different knowledge shapes):
1. Conceptual covered-leaf (`docs/generation-closeout/evidence/phase-b-conceptual-plan.json`) — orient `select-one` + check `select-one`
2. Conceptual ratios (`docs/generation-closeout/evidence/phase-b-ratio-plan.json`) — orient `describe-in-own-words`, explain `order-items`, check `select-one`

Evidence: `docs/generation-closeout/evidence/phase-b-c-d-live.json`

## STATUS
PASS
