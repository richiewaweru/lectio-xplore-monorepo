# Target Architecture

## Backend

```text
apps/textbook-agent/backend/src/
│
├── app.py
│
├── curriculum/
│   ├── units/
│   ├── concepts/
│   ├── misconceptions/
│   ├── paths/
│   ├── objectives/
│   ├── evidence/
│   └── teaching_plan/
│
├── print/
│   ├── api/
│   ├── generation/
│   │   ├── planning/
│   │   ├── forms/
│   │   ├── prompts/
│   │   ├── writers/
│   │   ├── validation/
│   │   ├── assembly/
│   │   ├── retry/
│   │   └── events/
│   ├── resources/
│   ├── rendering/
│   │   ├── page_objects/
│   │   ├── figures/
│   │   └── pdf/
│   └── contracts/
│
├── learn/
│   ├── api/
│   ├── authoring/
│   │   ├── builder/
│   │   ├── persistence/
│   │   └── preview/
│   ├── generation/
│   │   ├── planning/
│   │   ├── component_selection/
│   │   ├── prompts/
│   │   ├── writers/
│   │   ├── validation/
│   │   ├── assembly/
│   │   ├── retry/
│   │   └── events/
│   ├── publishing/
│   ├── runtime/
│   ├── distribution/
│   │   ├── classes/
│   │   ├── enrollment/
│   │   ├── invites/
│   │   └── assignments/
│   ├── evidence/
│   ├── analytics/
│   └── resources/
│
└── platform/
    ├── auth/
    ├── database/
    ├── llm/
    ├── storage/
    ├── media/
    ├── jobs/
    ├── telemetry/
    ├── logging/
    ├── config/
    └── errors/
```

This is a direction, not a demand that every leaf directory exist immediately. Prefer meaningful ownership over empty scaffolding.

## Frontend

```text
apps/textbook-agent/frontend/src/lib/
│
├── shared/
│   ├── ui/
│   ├── api/
│   ├── auth/
│   └── layout/
│
├── curriculum/
│   ├── units/
│   ├── concepts/
│   └── planning/
│
├── print/
│   ├── preview/
│   └── export/
│
└── learn/
    ├── authoring/
    │   └── builder/
    ├── student/
    │   ├── lesson/
    │   ├── home/
    │   └── progress/
    ├── distribution/
    │   ├── classes/
    │   └── assignments/
    └── insight/
```

SvelteKit route files remain route-oriented but should become thin feature entrypoints.

## Packages

```text
packages/
├── lectio-page/
└── lectio-learn/
```

`@lectio/learn` must not own classes, DB runtime, assignments, or teacher analytics.
`@lectio/page` must not own curriculum or user/application concerns.
