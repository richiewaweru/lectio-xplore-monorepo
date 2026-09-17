# D6 Test Matrix

| Flow | Real DB | Provider mocked | Core assertions | Status |
|---|---:|---:|---|---|
| Unit→Print | yes | yes | document/reload/PDF | |
| Print retry | yes | yes | recoverable resume | |
| Unit→Learn | yes | yes | valid Learn document | |
| Builder persistence | yes | no | edit/save/reload | |
| Publish versioning | yes | no | immutable v1/v2 | |
| Assignment/runtime | yes | no | correct instance/release | |
| Attempt/progress | yes | no | persisted evidence | |
| Analytics | yes | no | intended scope | |
| Architecture guards | n/a | n/a | zero forbidden imports | |
| Migrations | yes | n/a | upgrade/head valid | |
