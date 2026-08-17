# V3 Provider Compatibility

This note is the source of truth for provider-specific structured-output behavior in
the V3 pipeline and block-generation surfaces.

## Baseline posture

- Anthropic is the default baseline when no `V3_*` slot overrides are set.
- OpenAI-compatible providers such as DeepSeek are opt-in through
  `V3_FAST_*`, `V3_STANDARD_*`, and `V3_PREMIUM_*`.
- Nodes declare only their schema and slot; provider quirks are handled centrally.

## Structured output policy

- Anthropic keeps the normal structured-output path used by `pydantic_ai`.
- DeepSeek structured calls use one canonical schema and a shared helper:
  `backend/src/v3_execution/llm_helpers.py::structured_output_for_model(...)`.
- `DEEPSEEK_STRUCTURED_MODE=strict_tool` uses DeepSeek Beta (`/beta`) with strict
  `ToolOutput` and a DeepSeek-specific JSON Schema projection.
- `DEEPSEEK_STRUCTURED_MODE=prompted_json` keeps the legacy prompted JSON fallback.
- Downstream Pydantic/Lectio validation and outer repair remain authoritative.

## Where the policy applies today

- Whole-lesson planners, native page-object writers, V3 Studio helpers, blueprint
  planners, block generation, item/question/section writers, and QC nodes.

When adding a new structured-output node, route it through `prepare_structured_agent`
or `run_structured_agent` instead of adding provider-specific branching locally.

## Operational guidance

- To keep Anthropic as the deployment baseline, leave `V3_*` slot overrides unset.
- To run DeepSeek, set the `V3_*` slot overrides plus `DEEPSEEK_API_KEY`.
- Roll back strict mode with `DEEPSEEK_STRUCTURED_MODE=prompted_json`.
