## Phase 07 report — browser and reliability proof

### Gate status
**Blocked on live browser/DB identity proof** because Docker Desktop was not running in this environment (`dockerDesktopLinuxEngine` pipe missing).

### What was completed instead
- Deterministic reliability sample: **57/57 passed** across phases 01–06 + resume/fence/PDF suites (`reliability-sample-pytest.txt`)
- Evidence pack created under `docs/evidence/native-hardening-streaming/`
- Latency JSON stubbed with blocker + pointers to prior whole-lesson browser evidence

### Required to close live gate later
1. Start Docker Postgres (`db-dev`) and prove row identity
2. Fresh unit/lesson via real UI (no fixtures, no auto-approve)
3. Observe first streaming snapshot before all writers finish
4. Prove visual provider/executor call for pending figure
5. Final reload hash + viewer render
6. Export teacher + student PDFs
7. Record 3–5 real E2E runs into `reliability-sample.json`
