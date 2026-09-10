# Active Runtime Entrypoints and Major Owners

Baseline: `1dabd746af65ac9d9272fcb7c49f000632407754`

## Application runtime

### Backend composition root

`apps/textbook-agent/backend/src/app.py`

Run command documented by the repo:

```bash
cd apps/textbook-agent/backend
uv run uvicorn app:app --reload --app-dir src
```

The composition root currently wires curriculum, unit generation, Print studio/builder, Learn builder/publishing/runtime/analytics, auth, shares, prompts, telemetry, and the Print whole-lesson worker.

### Frontend

`apps/textbook-agent/frontend/`

Run:

```bash
cd apps/textbook-agent/frontend
pnpm dev
```

Main source owners:
- `frontend/src/routes/`
- `frontend/src/lib/curriculum/`
- `frontend/src/lib/print/`
- `frontend/src/lib/learn/`
- `frontend/src/lib/api/`
- `frontend/src/lib/shared/`

## Shared instructional path

Key active files:

```text
backend/src/curriculum/routes.py
backend/src/curriculum/agents.py
backend/src/curriculum/prompts.py

backend/src/curriculum/teaching_plan/
├── models.py
├── service.py
├── revisions.py
├── consumers.py
├── coverage.py
├── projections.py
├── compatibility.py
└── instance_ids.py

backend/src/application/unit_lesson/
├── prepare.py
├── dispatch.py
├── realization_contracts.py
├── realizations.py
├── dual_native.py
├── status.py
└── contracts.py
```

Current strength to preserve:
`application/unit_lesson/realizations.py` already admits Print and Learn as independent realizations pinned to Teaching Plan identity/revision/hash.

## Current Print path

```text
backend/src/print/generation/
├── native_production.py
├── selection_snapshot.py
├── work_orders.py
├── authoring_adapter.py
├── catalogue_projections.py
├── page_blocks.py
├── page_projections.py
├── source_resolver.py
├── prompts.py
└── whole_lesson/
    ├── executor.py
    ├── form_agent.py
    ├── form_plan.py
    ├── prompt_render.py
    ├── legality.py
    ├── native_retry.py
    ├── native_routing.py
    ├── failure_policy.py
    ├── failure_injection.py
    ├── events.py
    ├── figure_ids.py
    └── worker.py

backend/src/print/rendering/
backend/src/print/resources/
backend/src/print/contracts/
backend/src/print/http/v3_studio/
```

Print package:

```text
packages/lectio-page/
├── contracts/
│   ├── lectio-document-v2.schema.json
│   ├── object-catalogue.v1.json
│   ├── intent-catalogue.v1.json
│   ├── base-print.css
│   ├── authoring/
│   └── generated/
└── src/lib/
    └── print/...
```

## Current Learn path

```text
backend/src/learn/generation/
├── native_selection.py
├── native_production.py
├── native_execution.py
├── work_orders.py
├── ordered_assemble.py
├── interaction_writer.py
├── activity_authoring.py
├── authoring_adapter.py
├── contracts.py
├── canonical.py
└── component_lectio/
    ├── service.py
    ├── launcher.py
    ├── lane_dispatch.py
    ├── payload_strategies.py
    ├── payload_validation.py
    ├── pipeline.py
    ├── coverage_audit.py
    ├── fixtures.py
    └── errors.py
```

Canonical Learn document validation is currently component-oriented:

`backend/src/learn/contracts/lesson_document.py`

The active builder/publish/runtime surface includes:

```text
backend/src/learn/authoring/builder/
backend/src/learn/publishing/
backend/src/learn/runtime/
backend/src/learn/analytics/
backend/src/learn/distribution/
backend/src/learn/evidence/
```

Frontend Learn owners already include:

```text
frontend/src/lib/learn/student/StudentLessonShell.svelte
frontend/src/lib/learn/student/OrderedBlockList.svelte
frontend/src/lib/learn/student/student-shell.ts
frontend/src/lib/learn/authoring/
frontend/src/routes/learn/lessons/[id]/+page.svelte
frontend/src/routes/learn/instances/[instanceId]/+page.svelte
```

## Current Learn package

`packages/lectio-learn/`

It currently owns the old registry-driven content model, templates, schemas, exports, and interactions. Existing interaction renderers include:

```text
ChoiceInteraction.svelte
ClassifyInteraction.svelte
DragLabelInteraction.svelte
ImageChoiceInteraction.svelte
ImageHotspotInteraction.svelte
MatchPairsInteraction.svelte
MultiSelectInteraction.svelte
NumericInteraction.svelte
SequenceInteraction.svelte
ShortResponseInteraction.svelte
```

The package also currently contains Print-specific concerns such as `src/lib/print/RuledLines.svelte`; those violate the new desired boundary and must not survive in Learn ownership.

## Root validation/export surface

`package.json` currently exposes:
- `contracts:test`, `contracts:check`, `contracts:export`
- `learn:test`, `learn:export`
- `page:test`, `page:check`, `page:export`, `page:pdf`
- `app:test`, `app:check`
- `contracts:sync`
- `program:phase00`
- `program:domain-guards`

The final cleanup must update these scripts so deleted package paths cannot remain falsely green.
