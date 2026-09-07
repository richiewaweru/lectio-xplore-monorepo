# D5 Acceptance

PASS only when:
- unsupported historical trees are gone,
- Unit orchestration is really under application/unit_lesson,
- Print/ Learn/ Curriculum/ Infra ownership is obvious,
- no production imports hit retired namespaces,
- no frontend route/API calls retired endpoints,
- no worker/startup/telemetry/config depends on retired flows,
- DB retirement is migration-backed,
- no legacy-only tests/docs remain,
- active backend is effectively app.py + application + curriculum + print + learn + infra,
- structural regressions remain green.
