# Status / Stage Matrix

| Run type | Typical stages | Lifecycle statuses |
|---|---|---|
| preparation | structural_planning, item_generation, teaching_planning | queued, running, awaiting_review, ready, failed_recoverable, failed_terminal, cancelled |
| shared_document | section_composition, section_writing, media_generation, continuity_validation, document_qa | queued, running, ready, failed_recoverable, failed_terminal, cancelled |
| learn | learn_realization, learn_validation | queued, running, ready, failed_recoverable, failed_terminal, cancelled |
| print | print_realization, print_layout, print_validation | queued, running, ready, failed_recoverable, failed_terminal, cancelled |
| publish | publish | queued, running, ready, failed_recoverable, failed_terminal, cancelled |
| pdf | pdf_render | queued, running, ready, failed_recoverable, failed_terminal, cancelled |

Human approval stages never hold worker leases.
