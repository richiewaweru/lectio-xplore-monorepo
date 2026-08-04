## Handoff

**What changed**: Introduced a multi-vendor, tier-based model registry for the LangGraph pipeline (`backend/src/pipeline/providers/*`) and aligned env configuration in `backend/.env.example`. Nodes now obtain models via `get_node_model` which resolves a `ModelTier` to a `ProviderConfig` (provider + model name) and builds the appropriate Anthropic/OpenAI/Gemini adapter. Added focused tests for the registry in `backend/tests/pipeline/test_providers_registry.py`.

**Current state**: The provider abstraction is in place and wired for Anthropic via `AnthropicLLMProvider`. OpenAI/Gemini adapters exist as stubs that raise `NotImplementedError` on `generate` until real clients are wired. The pipeline continues to default to Anthropic models as before but can be configured per tier via env vars. Other unrelated backend/frontend work on this branch remains in progress and uncommitted.

**Validated**: Registry unit tests pass (`backend/tests/pipeline/test_providers_registry.py`). Basic import structure is sound (no lints reported for the new provider modules). Full backend and frontend test suites have **not** been re-run as part of this specific change.

**Not done yet**: 
- Wire real OpenAI and Gemini clients into `OpenAILLMProvider` and `GeminiLLMProvider` if/when you want the pipeline to actually call those vendors.
- Decide whether pipeline nodes should call `BaseLLMProvider.generate` directly or continue to pass the underlying `AnthropicModel` into pydantic-ai; right now `LLMResponse.raw` exposes the wrapped model for compatibility.
- Extend docs (e.g. `README.md` or a dedicated pipeline doc) with a short section on configuring `LLM_TIER_*_PROVIDER` and `LLM_TIER_*_MODEL` in non-example envs.

**Start here**: 
- For configuration and behavior: `backend/src/pipeline/providers/registry.py` (tier mapping and env overrides) and `backend/src/pipeline/providers/base.py` (shared interface and response type).
- For vendor-specific wiring: `backend/src/pipeline/providers/anthropic.py`, `backend/src/pipeline/providers/openai.py`, and `backend/src/pipeline/providers/gemini.py`.
- For examples of env usage and defaults: `backend/.env.example` and `_DEFAULT_TIER_CONFIG` in the registry.

**Risks**: 
- If someone sets `LLM_TIER_*_PROVIDER` to `openai` or `gemini` before the corresponding adapters are fully implemented, pipeline runs will fail at runtime with `NotImplementedError`. Keep envs pointed at `anthropic` until you are ready to support other vendors.
- Future changes that bypass `get_model`/`get_node_model` and construct provider SDK clients directly will undermine the single-chokepoint design; new code should always go through the registry to keep vendor/model selection centralized.***
