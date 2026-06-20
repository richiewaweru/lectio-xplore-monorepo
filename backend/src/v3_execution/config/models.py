from __future__ import annotations

import os

from core.llm import ModelFamily, ModelSlot, ModelSpec, build_model

# Canonical v3 node names (must match call sites).
V3_SIGNAL_EXTRACTOR = "v3_signal_extractor"
V3_NARROW = "v3_narrow"
V3_STAGE1_PLANNER = "v3_stage1_planner"
V3_STAGE2_EXPANDER = "v3_stage2_expander"
V3_BLUEPRINT_ADJUST = "v3_blueprint_adjust"
V3_SECTION_WRITER = "v3_section_writer"
V3_QUESTION_WRITER = "v3_question_writer"
V3_ANSWER_KEY_GENERATOR = "v3_answer_key_generator"
"""Sonnet-tier answer key when FAST is insufficient (missing expected/working for full_working)."""
V3_ANSWER_KEY_GENERATOR_HEAVY = "v3_answer_key_generator_heavy"

V3_NODE_SLOTS: dict[str, ModelSlot] = {
    V3_SIGNAL_EXTRACTOR: ModelSlot.FAST,
    V3_NARROW: ModelSlot.FAST,
    V3_STAGE1_PLANNER: ModelSlot.PREMIUM,
    V3_STAGE2_EXPANDER: ModelSlot.STANDARD,
    V3_BLUEPRINT_ADJUST: ModelSlot.STANDARD,
    V3_SECTION_WRITER: ModelSlot.STANDARD,
    V3_QUESTION_WRITER: ModelSlot.STANDARD,
    V3_ANSWER_KEY_GENERATOR: ModelSlot.FAST,
    V3_ANSWER_KEY_GENERATOR_HEAVY: ModelSlot.STANDARD,
}

V3_DEFAULT_SPECS: dict[ModelSlot, ModelSpec] = {
    ModelSlot.FAST: ModelSpec(
        family=ModelFamily.ANTHROPIC,
        model_name="claude-haiku-4-5-20251001",
    ),
    ModelSlot.STANDARD: ModelSpec(
        family=ModelFamily.ANTHROPIC,
        model_name="claude-sonnet-4-6",
    ),
    ModelSlot.PREMIUM: ModelSpec(
        family=ModelFamily.ANTHROPIC,
        model_name="claude-opus-4-6",
    ),
}


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
    return None


def _parse_family(family_raw: str | None, *, base: ModelFamily) -> ModelFamily:
    if family_raw is None:
        return base
    key = family_raw.strip().lower()
    if key in {"google", "gemini"}:
        return ModelFamily.GOOGLE
    if key in {"openai_compatible", "openai-compatible", "openai"}:
        return ModelFamily.OPENAI_COMPATIBLE
    if key == "anthropic":
        return ModelFamily.ANTHROPIC
    if key == "test":
        return ModelFamily.TEST
    raise ValueError(
        f"Unsupported V3 model family '{family_raw}'. "
        "Expected one of: anthropic, google, openai_compatible, test."
    )


def _env_override_slot(slot: ModelSlot, *, base: ModelSpec) -> ModelSpec | None:
    prefix = f"V3_{slot.name}"
    family_raw = _first_env(f"{prefix}_PROVIDER")
    model_name = _first_env(f"{prefix}_MODEL_NAME")
    base_url = _first_env(f"{prefix}_BASE_URL")
    api_key_env = _first_env(f"{prefix}_API_KEY_ENV")

    if not any((family_raw, model_name, base_url, api_key_env)):
        return None

    family = _parse_family(family_raw, base=base.family) if family_raw else base.family
    return ModelSpec(
        family=family,
        model_name=model_name or base.model_name,
        base_url=base_url if base_url is not None else base.base_url,
        api_key_env=api_key_env if api_key_env is not None else base.api_key_env,
    )


def _load_slot_spec(slot: ModelSlot) -> ModelSpec:
    base = V3_DEFAULT_SPECS[slot]
    override = _env_override_slot(slot, base=base)
    return override if override is not None else base


def get_v3_slot(node_name: str) -> ModelSlot:
    if node_name not in V3_NODE_SLOTS:
        raise ValueError(
            f"Unknown v3 node '{node_name}'. "
            f"Expected one of: {', '.join(sorted(V3_NODE_SLOTS))}"
        )
    return V3_NODE_SLOTS[node_name]


def get_v3_spec(node_name: str) -> ModelSpec:
    return _load_slot_spec(get_v3_slot(node_name))


def get_v3_model(node_name: str, *, model_overrides: dict | None = None):
    slot = get_v3_slot(node_name)
    spec = _load_slot_spec(slot)
    if model_overrides:
        if slot in model_overrides:
            return model_overrides[slot]
        if slot.value in model_overrides:
            return model_overrides[slot.value]
    return build_model(spec)


__all__ = [
    "V3_ANSWER_KEY_GENERATOR",
    "V3_ANSWER_KEY_GENERATOR_HEAVY",
    "V3_BLUEPRINT_ADJUST",
    "V3_DEFAULT_SPECS",
    "V3_NARROW",
    "V3_NODE_SLOTS",
    "V3_QUESTION_WRITER",
    "V3_SECTION_WRITER",
    "V3_SIGNAL_EXTRACTOR",
    "V3_STAGE1_PLANNER",
    "V3_STAGE2_EXPANDER",
    "get_v3_model",
    "get_v3_slot",
    "get_v3_spec",
]
