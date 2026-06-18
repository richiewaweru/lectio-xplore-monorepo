"""
Pipeline-specific model selection.

Shared model transport, pricing, and runtime inspection live in ``core.llm``.
This module keeps only the pipeline node-to-slot mapping and PIPELINE_* env
overrides so the node call sites stay unchanged.
"""

from __future__ import annotations

import os

from core.llm import ModelFamily, ModelSlot, ModelSpec, build_model
from core.llm.transport import describe_text_model, effective_text_spec, endpoint_host
from pipeline.media.providers.registry import get_image_client as resolve_image_client
from pipeline.types.requests import GenerationMode

NODE_MODEL_SLOTS: dict[str, ModelSlot] = {
    "curriculum_planner": ModelSlot.FAST,
    "brief_planner": ModelSlot.FAST,
    "block_generator": ModelSlot.FAST,
    "content_generator": ModelSlot.STANDARD,
    "content_generator_repair": ModelSlot.STANDARD,
    "content_generator_core": ModelSlot.STANDARD,
    "content_generator_practice": ModelSlot.STANDARD,
    "content_generator_enrichment": ModelSlot.STANDARD,
    "diagram_generator": ModelSlot.FAST,
    "intelligent_image_prompt": ModelSlot.FAST,
    "interaction_generator": ModelSlot.STANDARD,
    "qc_agent": ModelSlot.FAST,
    "field_regenerator": ModelSlot.FAST,
}

DEFAULT_PROFILES_BY_MODE: dict[GenerationMode, dict[ModelSlot, ModelSpec]] = {
    GenerationMode.DRAFT: {
        ModelSlot.FAST: ModelSpec(
            family=ModelFamily.ANTHROPIC,
            model_name="claude-haiku-4-5-20251001",
        ),
        ModelSlot.STANDARD: ModelSpec(
            family=ModelFamily.ANTHROPIC,
            model_name="claude-haiku-4-5-20251001",
        ),
    },
    GenerationMode.BALANCED: {
        ModelSlot.FAST: ModelSpec(
            family=ModelFamily.ANTHROPIC,
            model_name="claude-haiku-4-5-20251001",
        ),
        ModelSlot.STANDARD: ModelSpec(
            family=ModelFamily.ANTHROPIC,
            model_name="claude-sonnet-4-6",
        ),
    },
    GenerationMode.STRICT: {
        ModelSlot.FAST: ModelSpec(
            family=ModelFamily.ANTHROPIC,
            model_name="claude-sonnet-4-6",
        ),
        ModelSlot.STANDARD: ModelSpec(
            family=ModelFamily.ANTHROPIC,
            model_name="claude-sonnet-4-6",
        ),
    },
}


def _slot_prefix(slot: ModelSlot) -> str:
    return f"PIPELINE_{slot.name}"


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
    return None


def _env_override(slot: ModelSlot, *, base: ModelSpec) -> ModelSpec | None:
    prefix = _slot_prefix(slot)
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


def load_profiles(
    generation_mode: GenerationMode = GenerationMode.BALANCED,
) -> dict[ModelSlot, ModelSpec]:
    base_profiles = DEFAULT_PROFILES_BY_MODE[generation_mode]
    profiles = dict(base_profiles)
    for slot, spec in base_profiles.items():
        override = _env_override(slot, base=spec)
        if override is not None:
            profiles[slot] = override
    return profiles


def get_node_text_slot(node_name: str) -> ModelSlot:
    if node_name not in NODE_MODEL_SLOTS:
        raise ValueError(
            f"Node '{node_name}' is not registered in NODE_MODEL_SLOTS. "
            f"Add it to pipeline.providers.registry."
        )
    return NODE_MODEL_SLOTS[node_name]


def resolve_text_model(
    *,
    slot: ModelSlot,
    spec: ModelSpec,
    model_overrides: dict | None = None,
):
    if model_overrides:
        if slot in model_overrides:
            return model_overrides[slot]
        if slot.value in model_overrides:
            return model_overrides[slot.value]
    return build_model(spec)


def get_node_text_model(
    node_name: str,
    model_overrides: dict | None = None,
    generation_mode: GenerationMode = GenerationMode.BALANCED,
):
    slot = get_node_text_slot(node_name)
    spec = load_profiles(generation_mode)[slot]
    return resolve_text_model(
        slot=slot,
        spec=spec,
        model_overrides=model_overrides,
    )


def get_node_text_spec(
    node_name: str,
    generation_mode: GenerationMode = GenerationMode.BALANCED,
) -> ModelSpec:
    slot = get_node_text_slot(node_name)
    return load_profiles(generation_mode)[slot]


def get_image_client():
    return resolve_image_client()


__all__ = [
    "ModelSpec",
    "ModelFamily",
    "ModelSlot",
    "NODE_MODEL_SLOTS",
    "DEFAULT_PROFILES_BY_MODE",
    "load_profiles",
    "get_node_text_slot",
    "get_node_text_model",
    "get_node_text_spec",
    "resolve_text_model",
    "get_image_client",
    "describe_text_model",
    "effective_text_spec",
    "endpoint_host",
]
