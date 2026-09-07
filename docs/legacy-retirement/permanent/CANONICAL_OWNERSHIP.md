# Canonical Ownership

application/: cross-domain Unit use-case orchestration only.
curriculum/: units, concepts, objectives, paths, teaching meaning.
print/: page planning/forms/prompts/writers/validation/rendering/PDF.
learn/: generation, authoring, publishing, runtime, distribution, evidence, analytics.
infra/: auth, DB, LLM, storage, telemetry plumbing, logging, config, errors.

Forbidden:
print→learn
learn→print
infra→print/learn
curriculum→print/learn
