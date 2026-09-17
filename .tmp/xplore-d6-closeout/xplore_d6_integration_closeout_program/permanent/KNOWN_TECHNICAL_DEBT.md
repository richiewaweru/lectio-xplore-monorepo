# Known Technical Debt

| ID | Problem | Severity | Canonical owner |
|---|---|---|---|
| LRN-001 | learner auth still mixes learner session and teacher JWT semantics | High | `learn/runtime`, `infra/auth` |
| LRN-002 | client can influence score/outcome/evidence | Critical | `learn/runtime/evaluation` |
| LRN-003 | concept/misconception bindings should derive from LearnRelease | High | `learn/evidence`, `learn/runtime` |
| LRN-004 | interaction UI→attempt persistence bridge incomplete | High | frontend `learn/student`, backend `learn/runtime` |
| LRN-005 | passive section completion semantics incomplete | Medium | `learn/runtime` |
| LRN-006 | sequential navigation enforcement incomplete | Medium | `learn/runtime`, frontend `learn/student` |
| LRN-007 | analytics scoping may include unrelated learner instances | High | `learn/analytics` |
| LRN-008 | ImageHotspot/DragLabel spatial authoring incomplete | Medium | `packages/lectio-learn`, `learn/authoring` |
| DATA-001 | Float scores rather than precise numeric | Medium | `infra/database`, `learn/runtime` |
| DATA-002 | LearningInstance should likely relate to assignment recipient | Medium | `learn/distribution`, DB |
| DATA-003 | auth LearnerSession vs lesson-visit session semantics conflated | Medium | `learn/runtime` |
| DATA-004 | class ownership/membership invariants overlap | Medium | `learn/distribution/classes`, DB |
| DATA-005 | assignment/release ownership validation needs strengthening | High | `learn/distribution/assignments` |
| PRINT-001 | PDF fixture/process may hang after successful output | Medium | `print/rendering/pdf` |
| LEARN-009 | @lectio/learn retains some Print-era helpers | Low | `packages/lectio-learn` |
| ARCH-001 | `v3_*` remains historical shared machinery | Medium | progressive extraction on touch |
| ARCH-002 | `core/` retains routes/entities/shims | Low | `infra` / application |
| ARCH-003 | resource-spec ownership still partly mixed | Low | `print/resources`, `learn/resources`, shared contracts |
