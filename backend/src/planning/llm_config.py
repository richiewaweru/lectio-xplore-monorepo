from __future__ import annotations

import os

from core.llm import ModelFamily, ModelSlot, ModelSpec

PLANNING_BRIEF_INTERPRETER_CALLER = "brief_interpreter"
PLANNING_BRIEF_INTERPRETER_SLOT = ModelSlot.FAST

PLANNING_MODEL_SPECS: dict[str, tuple[ModelSlot, ModelSpec]] = {
    PLANNING_BRIEF_INTERPRETER_CALLER: (
        PLANNING_BRIEF_INTERPRETER_SLOT,
        ModelSpec(
            family=ModelFamily.ANTHROPIC,
            model_name="claude-haiku-4-5-20251001",
        ),
    ),
}


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
    return None


def _env_override(caller: str, *, base: ModelSpec) -> ModelSpec | None:
    prefix = f"PLANNING_{caller.upper()}"
    family_raw = _first_env(f"{prefix}_PROVIDER")
    model_name = _first_env(f"{prefix}_MODEL_NAME")
    base_url = _first_env(f"{prefix}_BASE_URL")
    api_key_env = _first_env(f"{prefix}_API_KEY_ENV")

    if not any((family_raw, model_name, base_url, api_key_env)):
        return None

    if family_raw is None:
        family = base.family
    elif family_raw.strip().lower() in {"google", "gemini"}:
        family = ModelFamily.GOOGLE
    elif family_raw.strip().lower() in {"openai_compatible", "openai-compatible", "openai"}:
        family = ModelFamily.OPENAI_COMPATIBLE
    elif family_raw.strip().lower() == "anthropic":
        family = ModelFamily.ANTHROPIC
    elif family_raw.strip().lower() == "test":
        family = ModelFamily.TEST
    else:
        raise ValueError(
            f"Unsupported model family '{family_raw}'. "
            "Expected one of: anthropic, google, openai_compatible, test."
        )

    return ModelSpec(
        family=family,
        model_name=model_name or base.model_name,
        base_url=base_url if base_url is not None else base.base_url,
        api_key_env=api_key_env if api_key_env is not None else base.api_key_env,
    )


def get_planning_slot(caller: str) -> ModelSlot:
    try:
        slot, _ = PLANNING_MODEL_SPECS[caller]
        return slot
    except KeyError as exc:
        raise ValueError(f"Planning caller '{caller}' is not registered.") from exc


def get_planning_spec(caller: str) -> ModelSpec:
    try:
        slot, base = PLANNING_MODEL_SPECS[caller]
    except KeyError as exc:
        raise ValueError(f"Planning caller '{caller}' is not registered.") from exc
    override = _env_override(caller, base=base)
    return override or base

