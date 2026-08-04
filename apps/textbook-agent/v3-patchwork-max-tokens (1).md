# v3 Patchwork — Add max_tokens to Lesson Architect

## Root cause

`lesson_architect_model_settings()` sets the thinking config but never
sets `max_tokens`. Pydantic-ai uses the Anthropic provider default which
is 1024–2048 tokens. A full `ProductionBlueprint` JSON is 3000–4000 tokens
minimum. The model exhausts the output budget before finishing the response.

## Fix

**File:** `backend/src/v3_execution/config/models.py`

```python
# Before
def lesson_architect_model_settings() -> dict:
    return {
        "anthropic_thinking": {
            "type": "adaptive",
        }
    }

# After
def lesson_architect_model_settings() -> dict:
    """
    Model settings for the Lesson Architect Opus call.

    max_tokens: A full ProductionBlueprint is 3000–4000 output tokens.
    With adaptive thinking Opus generates internal reasoning tokens on top
    of that. 8000 gives safe headroom without being wasteful — Anthropic
    charges per actual tokens used, not the ceiling.

    anthropic_thinking.type = adaptive: Opus decides when and how much
    to think. Do not pass budget_tokens with adaptive (invalid request).
    """
    return {
        "anthropic_thinking": {
            "type": "adaptive",
        },
        "max_tokens": int(os.getenv("V3_ARCHITECT_MAX_TOKENS", "8000")),
    }
```

Make sure `os` is already imported at the top of `models.py` — it is
used by the existing env var loading functions so it should already be there.

## Add to .env.example

```bash
# v3 Lesson Architect output token ceiling
V3_ARCHITECT_MAX_TOKENS=8000
```

## Verification

```
□ No UnexpectedModelBehavior token limit error on blueprint generation
□ Blueprint endpoint returns 200 with valid JSON body
□ Response time is reasonable (30–90 seconds for Opus with adaptive thinking)
□ V3_ARCHITECT_MAX_TOKENS env var overrides the default correctly
```
