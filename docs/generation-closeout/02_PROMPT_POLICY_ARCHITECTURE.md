# Prompt and Policy Architecture

Reuse the existing prompt manifest/overlay system under:

```text
backend/resources/prompts/manifest.yaml
backend/src/core/prompts/loader.py
```

Do not invent a second prompt subsystem.

## Target prompt files

```text
backend/resources/prompts/
├── learner-action-policy.md
├── document-composer.md
├── document-writer.md
├── interaction-selection.md
├── interaction-writer.md
├── figure-authoring.md
└── print-realization.md
```

Existing composer/writer `.txt` files may remain if renaming adds churn. What matters is that they are manifest-backed, versioned, hashable, and actually loaded by production.

## Target policy files

```text
backend/resources/policies/
├── learner-actions.yaml
├── learn-action-map.yaml
└── print-action-map.yaml
```

### Markdown owns
- when learner action is worthwhile;
- desired action density/balance;
- prediction/retrieval/application guidance;
- document representation guidance;
- interaction choice reasoning;
- interaction authoring quality;
- figure authoring quality;
- Print realization guidance;
- wording/style guidance.

### YAML/JSON owns
- legal learner-action vocabulary;
- aliases/passive actions;
- legal interaction candidates;
- Learn defaults;
- Print defaults;
- policy versions.

### Code owns
- schemas;
- six document primitive kinds;
- interaction response contracts;
- scoring/evaluation;
- revision locking;
- DB transactions;
- retries/fencing;
- pagination;
- renderers;
- dependency boundaries.

Every production LLM stage retained/added in this sweep must have a stable prompt id, file-backed default, version, hash, and canonical loader. If prompt hashes are already stamped on generations, the new stages must participate in that traceability.

`editable: true` in the existing manifest means teacher overlays, not whether developers can edit the file. Keep system-critical prompts locked in the product UI initially if needed.
