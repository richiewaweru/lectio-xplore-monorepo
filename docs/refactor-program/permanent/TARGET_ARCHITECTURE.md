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
│   │   ├── document_realizer.py   # Teaching Plan → Print page document
│   │   ├── document_form_map.py
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
├── document/                      # shared ordinary content vocabulary
│   ├── models.py                  # Paragraph/Heading/List/Figure/Table/Callout
│   ├── composition.py
│   └── validation.py
│
├── learn/
│   ├── api/
│   ├── authoring/
│   │   ├── builder/
│   │   ├── persistence/
│   │   └── preview/
│   ├── generation/
│   │   ├── document_realizer.py   # Teaching Plan → LearnDocument v2
│   │   ├── document_writer.py
│   │   ├── assemble.py
│   │   ├── native_production.py
│   │   ├── native_execution.py
│   │   ├── prompts/
│   │   ├── writers/
│   │   ├── validation/
│   │   └── events/
│   ├── interactions/              # retained KEEP-set interaction contracts only
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
    ├── document/          # app-owned LearnDocument canvas / renderers / editors
    ├── interactions/      # retained KEEP-set UI shells
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
├── lectio-contracts/   # shared instructional intents / learner actions
├── lectio-page/        # Print page-document engine
└── lectio-learn/       # retained interaction UI only (ordinary Learn document path is app-owned)
```

`@lectio/contracts` owns shared instructional vocabulary used by Teaching Plan and both paths.
`@lectio/learn` must not own classes, DB runtime, assignments, teacher analytics, or ordinary document primitives.
`@lectio/page` must not own curriculum or user/application concerns.

Learn generation realizes ordinary content from `backend/src/document/` primitives plus the retained interaction KEEP set; it does not select ExplanationBlock-style content components.
