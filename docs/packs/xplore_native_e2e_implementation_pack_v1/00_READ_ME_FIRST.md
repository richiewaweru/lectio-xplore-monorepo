# Xplore Native End-to-End Implementation Pack

## Mission

Make the `richiewaweru/lectio-xplore-monorepo` repository produce a real native `LectioDocumentV2` from a lesson request, with:

- native-only runtime routing;
- all Lectio content forms exercised;
- section-level parallel writing;
- strict form-specific validation;
- one informed repair attempt for broken LLM output;
- stable question-to-answer-key references;
- pending figure placeholders;
- persistence and resume;
- honest native status reporting;
- student and teacher rendering and PDF export.

Target branch: `pageobject-integration`  
Baseline inspected: `0cc0ff3454f231cdbd357f4040fa27d0f2bb144e`

## How to use this pack

1. Give Grok `01_MASTER_GROK_IMPLEMENTATION_PROMPT.md`.
2. Place this complete pack where Grok can read it.
3. Require Grok to execute the gates in `04_STAGE_GATED_IMPLEMENTATION_PLAN.md` in order.
4. Grok must use the fixtures and scripted mock scenarios before any real LLM run.
5. Grok must write evidence into `docs/evidence/native-e2e-v1/`.
6. A gate is not complete until its test command and actual output are recorded.
7. The pass is complete only when the fixture lesson produces:
   - valid persisted `LectioDocumentV2`;
   - student render and PDF;
   - teacher render and PDF with answer key;
   - machine-readable stage report;
   - no unexplained `500`, `error: null`, or stuck polling.

## Non-negotiable rule

Do not diagnose the real LLM until the complete flow passes with controlled mock outputs, including deliberately invalid outputs.

## Intended architecture

```text
lesson request
→ native planning
→ teacher approval
→ form plan
→ section jobs, maximum 4 concurrently
→ form-specific writing and validation
→ one informed repair when validation fails
→ persist validated section outcomes
→ deterministic assembly
→ answer-key integrity validation
→ LectioDocumentV2 validation
→ student and teacher rendering
→ PDF export
```

## Definition of acceptable LLM failure

An LLM may return malformed or contract-invalid output. The system must:

```text
reject invalid output
→ record exact validation errors
→ attempt one informed repair
→ succeed OR return a named recoverable failure
```

It may not crash the application, persist invalid content, hide the error, or strand the UI.
