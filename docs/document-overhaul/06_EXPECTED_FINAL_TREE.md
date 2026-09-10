# Expected Final Ownership Shape

Exact filenames may vary after live implementation, but ownership should converge toward:

```text
apps/textbook-agent/backend/src/
├── app.py
│
├── curriculum/
│   └── teaching_plan/
│       ├── models.py
│       ├── service.py
│       ├── revisions.py
│       ├── consumers.py
│       └── coverage.py
│
├── document/                       # neutral ordinary content vocabulary
│   ├── models.py                   # Paragraph/Heading/List/Figure/Table/Callout
│   └── validation.py
│
├── application/
│   └── unit_lesson/
│       ├── realizations.py         # independent path identity
│       ├── realization_contracts.py
│       ├── dispatch.py
│       └── status.py
│
├── print/
│   ├── generation/
│   │   ├── document_realizer.py
│   │   ├── native_production.py
│   │   └── whole_lesson/...
│   ├── rendering/
│   ├── resources/
│   └── contracts/
│
├── learn/
│   ├── generation/
│   │   ├── document_realizer.py
│   │   ├── native_production.py
│   │   ├── native_execution.py
│   │   ├── document_writer.py
│   │   └── assemble.py
│   ├── interactions/
│   │   ├── registry/contracts
│   │   ├── writers/validation
│   │   └── retained interaction logic
│   ├── authoring/
│   ├── publishing/
│   ├── runtime/
│   ├── analytics/
│   └── distribution/
│
└── infra/
```

Frontend:

```text
apps/textbook-agent/frontend/src/lib/
├── curriculum/
├── print/
├── learn/
│   ├── document/
│   │   ├── renderers/
│   │   ├── editors/
│   │   └── document state
│   ├── interactions/
│   ├── authoring/
│   └── student/
├── shared/
└── api/
```

Packages:

```text
packages/
├── lectio-contracts/     # keep only if genuinely neutral/shared
└── lectio-page/          # Print/page engine

# lectio-learn removed if all retained Learn code is application-owned
```

The final tree must be driven by live ownership, not by preserving these names for their own sake.
