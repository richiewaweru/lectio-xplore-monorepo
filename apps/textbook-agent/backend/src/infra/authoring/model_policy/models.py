from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Literal

from core.config import settings as app_settings
from core.llm import ModelFamily, ModelSlot, ModelSpec, build_model

# Canonical v3 node names (must match call sites).
V3_SIGNAL_EXTRACTOR = "v3_signal_extractor"
V3_NARROW = "v3_narrow"
V3_PROPOSE_INTENT = "v3_propose_intent"
V3_STAGE1_PLANNER = "v3_stage1_planner"
V3_STAGE2_EXPANDER = "v3_stage2_expander"
V3_ITEM_EXECUTOR = "v3_item_executor"
V3_BLUEPRINT_ADJUST = "v3_blueprint_adjust"
V3_SECTION_WRITER = "v3_section_writer"
V3_QUESTION_WRITER = "v3_question_writer"
V3_ANSWER_KEY_GENERATOR = "v3_answer_key_generator"
"""Sonnet-tier answer key when FAST is insufficient (missing expected/working for full_working)."""
V3_ANSWER_KEY_GENERATOR_HEAVY = "v3_answer_key_generator_heavy"
V3_VISUAL_QC = "v3_visual_qc"
V3_CARD_QC = "v3_card_qc"
V3_KNOWLEDGE_TYPE_CLASSIFIER = "v3_knowledge_type_classifier"
V3_BLOCK_WRITER_FAST = "v3_block_writer_fast"
V3_BLOCK_WRITER_STANDARD = "v3_block_writer_standard"
V2_PATH_PLANNER = "v2_path_planner"
V2_MERGE_CRITIC = "v2_merge_critic"
V2_COMPONENT_SELECTOR = "v2_component_selector"
V2_PATH_STRUCTURAL_PLANNER = "v2_path_structural_planner"
V2_PATH_CHAT_EDITOR = "v2_path_chat_editor"
V2_LESSON_APPROACH_PLANNER = "v2_lesson_approach_planner"
V3_CONSTRUCTOR = "v3_constructor"
V3_VISUAL_TOPOLOGY_PLANNER = "v3_visual_topology_planner"
V3_LESSON_SOURCEBOOK_WRITER = "v3_lesson_sourcebook_writer"
V3_SHARED_TASK_WRITER = "v3_shared_task_writer"
V3_WHOLE_LESSON_COHERENCE_REVIEWER = "v3_whole_lesson_coherence_reviewer"
TEACHING_PLAN_SEMANTIC_REVIEWER = "teaching_plan_semantic_reviewer"
SECTION_COMPOSER = "section_composer"
SHARED_SECTION_WRITER = "shared_section_writer"
BOUNDARY_CONTINUITY_VALIDATOR = "boundary_continuity_validator"
DOCUMENT_SEMANTIC_QA = "document_semantic_qa"
V3_TARGETED_LESSON_REPAIR = "v3_targeted_lesson_repair"
SHARED_SOURCEBOOK_AUTHORING = "shared_sourcebook_authoring"
SHARED_TASK_AUTHORING = "shared_task_authoring"

V3_NODE_SLOTS: dict[str, ModelSlot] = {
    V3_SIGNAL_EXTRACTOR: ModelSlot.FAST,
    V3_NARROW: ModelSlot.FAST,
    V3_PROPOSE_INTENT: ModelSlot.STANDARD,
    V3_STAGE1_PLANNER: ModelSlot.STANDARD,
    V3_STAGE2_EXPANDER: ModelSlot.STANDARD,
    V3_ITEM_EXECUTOR: ModelSlot.PREMIUM,
    V3_BLUEPRINT_ADJUST: ModelSlot.FAST,
    V3_SECTION_WRITER: ModelSlot.STANDARD,
    V3_QUESTION_WRITER: ModelSlot.FAST,
    V3_ANSWER_KEY_GENERATOR: ModelSlot.FAST,
    V3_ANSWER_KEY_GENERATOR_HEAVY: ModelSlot.STANDARD,
    V3_VISUAL_QC: ModelSlot.FAST,
    V3_CARD_QC: ModelSlot.FAST,
    V3_KNOWLEDGE_TYPE_CLASSIFIER: ModelSlot.FAST,
    V3_BLOCK_WRITER_FAST: ModelSlot.FAST,
    V3_BLOCK_WRITER_STANDARD: ModelSlot.STANDARD,
    V2_PATH_PLANNER: ModelSlot.STANDARD,
    V2_MERGE_CRITIC: ModelSlot.FAST,
    V2_COMPONENT_SELECTOR: ModelSlot.STANDARD,
    V2_PATH_STRUCTURAL_PLANNER: ModelSlot.STANDARD,
    V2_PATH_CHAT_EDITOR: ModelSlot.STANDARD,
    V2_LESSON_APPROACH_PLANNER: ModelSlot.STANDARD,
    V3_CONSTRUCTOR: ModelSlot.FAST,
    V3_VISUAL_TOPOLOGY_PLANNER: ModelSlot.STANDARD,
    V3_LESSON_SOURCEBOOK_WRITER: ModelSlot.STANDARD,
    V3_SHARED_TASK_WRITER: ModelSlot.FAST,
    V3_WHOLE_LESSON_COHERENCE_REVIEWER: ModelSlot.STANDARD,
    TEACHING_PLAN_SEMANTIC_REVIEWER: ModelSlot.STANDARD,
    SECTION_COMPOSER: ModelSlot.STANDARD,
    SHARED_SECTION_WRITER: ModelSlot.STANDARD,
    BOUNDARY_CONTINUITY_VALIDATOR: ModelSlot.STANDARD,
    # STANDARD (not FAST): the expanded semantic checks (misconception
    # resolution, answer leakage, assessment/example duplication, factual
    # accuracy) plus DeepSeek thinking need more budget than the FAST slot's
    # 8k-token ceiling. STANDARD's 16k ceiling already accommodates DeepSeek
    # reasoning output for other STANDARD-slot nodes below.
    DOCUMENT_SEMANTIC_QA: ModelSlot.STANDARD,
    V3_TARGETED_LESSON_REPAIR: ModelSlot.FAST,
    SHARED_SOURCEBOOK_AUTHORING: ModelSlot.STANDARD,
    SHARED_TASK_AUTHORING: ModelSlot.STANDARD,
}

V3ReasoningLevel = Literal["low", "medium", "high"]
V3NodeReasoningPolicy = V3ReasoningLevel | bool

V3_NODE_REASONING: dict[str, V3NodeReasoningPolicy] = {
    V3_SIGNAL_EXTRACTOR: False,
    V3_NARROW: "medium",
    V3_PROPOSE_INTENT: "medium",
    V3_STAGE1_PLANNER: "high",
    V3_STAGE2_EXPANDER: False,
    V3_ITEM_EXECUTOR: False,
    V3_BLUEPRINT_ADJUST: False,
    V3_SECTION_WRITER: False,
    V3_QUESTION_WRITER: False,
    V3_ANSWER_KEY_GENERATOR: False,
    V3_ANSWER_KEY_GENERATOR_HEAVY: False,
    V3_VISUAL_QC: False,
    V3_CARD_QC: False,
    V3_KNOWLEDGE_TYPE_CLASSIFIER: False,
    V3_BLOCK_WRITER_FAST: False,
    V3_BLOCK_WRITER_STANDARD: False,
    # Path planning is a constrained JSON route, not an open-ended reasoning
    # task. DeepSeek thinking made this request hold the UI in planning for
    # minutes and allowed overlapping retries before the first request settled.
    V2_PATH_PLANNER: False,
    V2_MERGE_CRITIC: False,
    V2_COMPONENT_SELECTOR: "medium",
    # Constrained-output nodes run without provider reasoning. On DeepSeek,
    # thinking mode returns reasoning-only assistant messages with empty
    # ``content``; replaying one produces HTTP 400 "Invalid assistant message:
    # content or tool_calls must be set". Correctness for these two nodes comes
    # from the typed output schema plus their own outer repair attempt, not from
    # provider reasoning.
    V2_PATH_STRUCTURAL_PLANNER: False,
    V2_PATH_CHAT_EDITOR: False,
    # Whole-lesson Teaching Plan authoring (the shared/V2 path). Unlike the
    # constrained JSON planners above, this node's output quality is the
    # persisted Teaching Plan's continuity contract itself (must_establish,
    # bridges, exit states); DeepSeek thinking is enabled here for quality,
    # not latency. It runs through the same single-call, no-output-retry
    # path (``NO_OUTPUT_RETRY``) as ``V3_STAGE1_PLANNER``, which already
    # runs DeepSeek thinking successfully in production, so the message-
    # replay failure mode documented for V2_PATH_STRUCTURAL_PLANNER/
    # V2_PATH_CHAT_EDITOR does not apply.
    # "low", not "medium": a 2026-09-30 A/B on one lesson (3-5 runs each)
    # passed 3/5 at low, 1/3 at medium (36k+ thinking tokens, truncated JSON,
    # 3-10 min calls), and 0/3 with thinking off (structural rule failures).
    V2_LESSON_APPROACH_PLANNER: "low",
    V3_CONSTRUCTOR: False,
    V3_VISUAL_TOPOLOGY_PLANNER: False,
    V3_LESSON_SOURCEBOOK_WRITER: False,
    V3_SHARED_TASK_WRITER: False,
    V3_WHOLE_LESSON_COHERENCE_REVIEWER: False,
    # Semantic review, prose writing, and whole-document QA benefit from
    # DeepSeek thinking: each is a single-call, no-output-retry structured
    # node (``NO_OUTPUT_RETRY`` / ``repair_attempts=0``) that never replays
    # a prior assistant turn, so the reasoning-only empty-content replay
    # failure documented for V2_PATH_STRUCTURAL_PLANNER/V2_PATH_CHAT_EDITOR
    # does not apply here.
    TEACHING_PLAN_SEMANTIC_REVIEWER: "medium",
    SECTION_COMPOSER: False,
    SHARED_SECTION_WRITER: "medium",
    BOUNDARY_CONTINUITY_VALIDATOR: False,
    # "low", not "medium": its findings are advisory notes for the teacher, and
    # at medium a live run spent ~6 min (one timeout + retry) on this one call
    # while the whole document was written in under a minute (2026-10-01).
    DOCUMENT_SEMANTIC_QA: "low",
    V3_TARGETED_LESSON_REPAIR: False,
    SHARED_SOURCEBOOK_AUTHORING: False,
    SHARED_TASK_AUTHORING: False,
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

V3_NODE_DEFAULT_SPECS: dict[str, ModelSpec] = {
    V3_VISUAL_QC: ModelSpec(
        family=ModelFamily.ANTHROPIC,
        model_name="claude-haiku-4-5-20251001",
        api_key_env="ANTHROPIC_API_KEY",
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


def _env_override_node(node_name: str, *, base: ModelSpec) -> ModelSpec | None:
    prefix = node_name.upper()
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


def get_v3_slot(node_name: str) -> ModelSlot:
    if node_name not in V3_NODE_SLOTS:
        raise ValueError(
            f"Unknown v3 node '{node_name}'. Expected one of: {', '.join(sorted(V3_NODE_SLOTS))}"
        )
    return V3_NODE_SLOTS[node_name]


def get_v3_spec(node_name: str) -> ModelSpec:
    if node_name in V3_NODE_DEFAULT_SPECS:
        base = V3_NODE_DEFAULT_SPECS[node_name]
        return _env_override_node(node_name, base=base) or base
    slot_spec = _load_slot_spec(get_v3_slot(node_name))
    return _env_override_node(node_name, base=slot_spec) or slot_spec


def get_v3_model_settings(
    node_name: str,
    *,
    base_settings: dict | None = None,
) -> dict | None:
    settings: dict = {}
    spec = get_v3_spec(node_name)
    reasoning = _reasoning_from_env(
        node_name,
        V3_NODE_REASONING.get(node_name, False),
    )

    if spec.family == ModelFamily.OPENAI_COMPATIBLE and spec.model_name.startswith("deepseek-"):
        if isinstance(reasoning, str):
            settings["openai_reasoning_effort"] = reasoning
            settings["extra_body"] = {"thinking": {"type": "enabled"}}
        else:
            # DeepSeek V4 enables thinking by default when the field is
            # omitted.  Explicitly disable it for constrained JSON nodes;
            # omission is not equivalent to ``False`` at the transport layer.
            settings["extra_body"] = {"thinking": {"type": "disabled"}}

    if base_settings:
        settings = _merge_model_settings(settings, base_settings)

    slot_limits = {
        ModelSlot.FAST: app_settings.v3_max_tokens_fast,
        ModelSlot.STANDARD: app_settings.v3_max_tokens_standard,
        ModelSlot.PREMIUM: app_settings.v3_max_tokens_premium,
    }
    settings.setdefault(
        "max_tokens",
        min(slot_limits[get_v3_slot(node_name)], app_settings.v3_max_tokens_safety),
    )

    return settings or None


def _reasoning_from_env(
    node_name: str,
    default: V3NodeReasoningPolicy,
) -> V3NodeReasoningPolicy:
    raw = os.getenv(f"{node_name.upper()}_REASONING")
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in {"false", "off", "none", "0"}:
        return False
    if value in {"low", "medium", "high"}:
        return value  # type: ignore[return-value]
    raise ValueError(
        f"Invalid reasoning policy '{raw}' for {node_name}; expected false, low, medium, or high"
    )


def _merge_model_settings(defaults: dict, overrides: dict) -> dict:
    merged = dict(defaults)
    for key, value in overrides.items():
        if (
            key == "extra_body"
            and isinstance(merged.get(key), Mapping)
            and isinstance(value, Mapping)
        ):
            merged[key] = _deep_merge_dicts(dict(merged[key]), value)
            continue
        merged[key] = value
    return merged


def _deep_merge_dicts(left: dict, right: Mapping) -> dict:
    merged = dict(left)
    for key, value in right.items():
        if isinstance(merged.get(key), Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge_dicts(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def get_v3_model(node_name: str, *, model_overrides: dict | None = None):
    slot = get_v3_slot(node_name)
    spec = get_v3_spec(node_name)
    if model_overrides:
        if slot in model_overrides:
            return model_overrides[slot]
        if slot.value in model_overrides:
            return model_overrides[slot.value]
    return build_model(spec)


__all__ = [
    "BOUNDARY_CONTINUITY_VALIDATOR",
    "DOCUMENT_SEMANTIC_QA",
    "SECTION_COMPOSER",
    "SHARED_SECTION_WRITER",
    "SHARED_SOURCEBOOK_AUTHORING",
    "SHARED_TASK_AUTHORING",
    "TEACHING_PLAN_SEMANTIC_REVIEWER",
    "V2_COMPONENT_SELECTOR",
    "V2_LESSON_APPROACH_PLANNER",
    "V2_MERGE_CRITIC",
    "V2_PATH_CHAT_EDITOR",
    "V2_PATH_PLANNER",
    "V2_PATH_STRUCTURAL_PLANNER",
    "V3_ANSWER_KEY_GENERATOR",
    "V3_ANSWER_KEY_GENERATOR_HEAVY",
    "V3_BLOCK_WRITER_FAST",
    "V3_BLOCK_WRITER_STANDARD",
    "V3_BLUEPRINT_ADJUST",
    "V3_CARD_QC",
    "V3_CONSTRUCTOR",
    "V3_DEFAULT_SPECS",
    "V3_ITEM_EXECUTOR",
    "V3_KNOWLEDGE_TYPE_CLASSIFIER",
    "V3_LESSON_SOURCEBOOK_WRITER",
    "V3_NARROW",
    "V3_NODE_REASONING",
    "V3_NODE_SLOTS",
    "V3_PROPOSE_INTENT",
    "V3_QUESTION_WRITER",
    "V3_SECTION_WRITER",
    "V3_SHARED_TASK_WRITER",
    "V3_SIGNAL_EXTRACTOR",
    "V3_STAGE1_PLANNER",
    "V3_STAGE2_EXPANDER",
    "V3_TARGETED_LESSON_REPAIR",
    "V3_VISUAL_QC",
    "V3_VISUAL_TOPOLOGY_PLANNER",
    "V3_WHOLE_LESSON_COHERENCE_REVIEWER",
    "get_v3_model",
    "get_v3_model_settings",
    "get_v3_slot",
    "get_v3_spec",
]
