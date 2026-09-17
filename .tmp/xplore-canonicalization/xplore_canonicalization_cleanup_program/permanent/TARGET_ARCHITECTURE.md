# Target Architecture

```text
backend/src/
├── app.py
├── application/
│   └── unit_lesson/      # thin cross-domain orchestration only
├── curriculum/           # shared instructional meaning
├── print/
│   ├── generation/
│   ├── rendering/
│   ├── resources/
│   └── contracts/
├── learn/
│   ├── authoring/
│   ├── generation/
│   ├── publishing/
│   ├── runtime/
│   ├── distribution/
│   ├── evidence/
│   ├── analytics/
│   ├── resources/
│   └── contracts/
└── infra/
    ├── auth/
    ├── database/
    ├── llm/
    ├── storage/
    ├── media/
    ├── telemetry/
    ├── logging/
    ├── config/
    └── errors/
```

Frontend:
```text
src/lib/
├── shared/
├── curriculum/
├── print/
└── learn/
    ├── authoring/
    ├── student/
    ├── distribution/
    └── insight/
```

Packages:
```text
packages/
├── lectio-page/
└── lectio-learn/
```

`application/` may orchestrate Print/Learn but must not become another generic generation/planning bucket.
