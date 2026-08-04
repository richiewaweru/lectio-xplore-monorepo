# v3 Patchwork — Thinking Type Fix + Blueprint Error Surfacing

## Two fixes, one pass

### Fix 1 — `thinking.type` deprecated warning

**File:** `backend/src/v3_execution/config/models.py`

Change `lesson_architect_model_settings()`:

```python
# Before
def lesson_architect_model_settings() -> dict:
    return {
        "anthropic_thinking": {
            "type": "enabled",
            "budget_tokens": LESSON_ARCHITECT_THINKING_BUDGET_TOKENS,
        }
    }

# After
def lesson_architect_model_settings() -> dict:
    """Anthropic adaptive thinking for Lesson Architect.

    Uses 'adaptive' per Anthropic guidance:
    https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking

    'adaptive' does NOT accept budget_tokens — that field is only valid
    for the deprecated 'enabled' type. With 'adaptive', Opus decides
    when and how much to think based on task complexity.
    """
    return {
        "anthropic_thinking": {
            "type": "adaptive",
        }
    }
```

---

### Fix 2 — Blueprint endpoint error surfacing

**File:** `backend/src/generation/v3_studio/router.py`

Add try/except and logger import so the real exception surfaces in
Railway logs and in the HTTP response body during debugging:

```python
# At top of file — add logger if not already present
import logging
logger = logging.getLogger(__name__)

# Replace the bare post_blueprint handler:

@v3_studio_router.post("/blueprint", response_model=BlueprintPreviewDTO)
async def post_blueprint(
    body: GenerateBlueprintRequest,
    current_user: User = Depends(get_current_user),
) -> BlueprintPreviewDTO:
    try:
        bp = await generate_production_blueprint(
            signals=body.signals,
            form=body.form,
            clarification_answers=body.clarification_answers,
            trace_id=str(uuid.uuid4()),
        )
        blueprint_id = str(uuid.uuid4())
        template_id = "diagram-led"
        await v3_studio_store.put_blueprint(
            current_user.id, blueprint_id, bp, template_id
        )
        return blueprint_to_preview_dto(
            blueprint_id=blueprint_id,
            blueprint=bp,
            template_id=template_id,
        )
    except Exception as exc:
        logger.exception(
            "Blueprint generation failed user=%s error=%s",
            current_user.id,
            str(exc)[:400],
        )
        raise HTTPException(
            status_code=500,
            detail=f"{type(exc).__name__}: {str(exc)[:400]}",
        ) from exc
```

---

## Verification

```
□ No UserWarning about thinking.type=enabled in Railway logs
□ POST /api/v1/v3/blueprint 500 response body contains exception
  type and message instead of generic internal server error
□ Railway logs show "Blueprint generation failed" with error= field
  on next failed attempt
```

## What this tells us next

After deploying these two fixes, retry the Amara brief flow.
The next 500 response body will contain the real exception — either:

- `ValidationError: ...`  → Opus output doesn't match ProductionBlueprint schema
                            → implement manifest injection patch next
- `RuntimeError: lesson architect returned unexpected output`
                            → same root cause, same fix
- `ModelHTTPError: ...`   → API-level failure, check Anthropic status
- `TimeoutError: ...`     → Opus taking too long, increase V3_TIMEOUT_ARCHITECT_SECONDS
```
