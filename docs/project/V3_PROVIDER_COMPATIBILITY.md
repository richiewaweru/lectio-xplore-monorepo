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
- DeepSeek thinking models must avoid `tool_choice` structured output.
- For DeepSeek-style OpenAI-compatible thinking nodes, V3 uses prompted JSON instead
  of tool/native structured output.

The central decision point is
`backend/src/v3_execution/llm_helpers.py::structured_output_type_for_model(...)`.

## Where the policy applies today

- V3 Studio helpers: `signals`, `narrow`, `blueprint_adjust`
- V3 planning: `stage1_planner`, `stage2_expander`
- Block generation paths that use structured schema output

When adding a new structured-output node, route it through the shared helper instead
of adding provider-specific branching in the route or prompt.

## Operational guidance

- To keep Anthropic as the deployment baseline, leave `V3_*` slot overrides unset.
- To run DeepSeek, set the `V3_*` slot overrides plus `DEEPSEEK_API_KEY`.
- If a new OpenAI-compatible provider is introduced later, add its compatibility
  behavior in the shared helper rather than forking individual node code.
