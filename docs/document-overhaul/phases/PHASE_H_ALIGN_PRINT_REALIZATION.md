# Phase H — Align Print Realization

## Goal
Make Print consume the same Teaching Plan meaning and shared document vocabulary while retaining paper-specific task treatments.

## Open these active files first
- `apps/textbook-agent/backend/src/print/generation/native_production.py`
- `apps/textbook-agent/backend/src/print/generation/work_orders.py`
- `apps/textbook-agent/backend/src/print/generation/whole_lesson/executor.py`
- `apps/textbook-agent/backend/src/print/generation/whole_lesson/form_agent.py`
- `apps/textbook-agent/backend/src/print/generation/whole_lesson/form_plan.py`
- `apps/textbook-agent/backend/src/print/rendering/`
- `packages/lectio-page/`

## Implementation tasks
- Map passive teaching content to the shared six primitive forms.
- Map learner tasks to Print-specific response treatments without leaking those treatments upstream.
- Keep ruled lines, response area sizing, working/drawing space, pagination and page layout strictly in Print.
- Preserve page document v2/PDF machinery where it remains effective.
- Remove duplicated instructional semantics from Print catalogues after shared intent ownership is established.

## Expected outputs
- `new Print realizer output`
- `Print task-treatment mapping`
- `updated page-document assembly`
- `PDF fixtures`

## Acceptance gate
Generate a fresh Print lesson from the same Teaching Plan used by Learn; verify high-quality PDF output and that Print imports no Learn product code.
