"""
pipeline.contracts

Deterministic boundary between pipeline code and exported Lectio contracts.
"""

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from pipeline.types.generation_manifest import (
    GenerationFieldContract,
    SectionGenerationManifest,
)
from pipeline.types.template_contract import TemplateContractSummary, TemplatePresetSummary

_META_FILES = {
    "component-field-map",
    "component-registry",
    "preset-registry",
    "section-content-schema",
}

_EXTERNAL_FIELDS = {
    "diagram",
    "diagram_compare",
    "diagram_series",
    "simulation",
    "image_block",
    "video_embed",
}


def diag(tag: str, **fields) -> None:
    sys.stderr.write(f"DIAG::{tag}::{json.dumps(fields, default=str)}\n")
    sys.stderr.flush()


def _contracts_dir() -> Path:
    from_env = os.environ.get("LECTIO_CONTRACTS_DIR")
    if from_env:
        path = Path(from_env)
        if not path.exists():
            raise FileNotFoundError(
                f"LECTIO_CONTRACTS_DIR is set to '{from_env}' "
                "but the directory does not exist. "
                "Run: uv run python tools/update_lectio_contracts.py"
            )
        return path

    default = Path(__file__).resolve().parent.parent.parent / "contracts"
    if not default.exists():
        raise FileNotFoundError(
            f"Contracts directory not found at '{default}'. "
            "Run: uv run python tools/update_lectio_contracts.py"
        )
    return default


@lru_cache(maxsize=None)
def _load_contract_raw(template_id: str) -> dict:
    path = _contracts_dir() / f"{template_id}.json"
    if not path.exists():
        available = [
            p.stem for p in _contracts_dir().glob("*.json") if p.stem not in _META_FILES
        ]
        raise ValueError(
            f"No contract found for template '{template_id}'. "
            f"Available templates: {sorted(available)}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _load_field_map() -> dict[str, str]:
    path = _contracts_dir() / "component-field-map.json"
    if not path.exists():
        raise FileNotFoundError(
            "component-field-map.json not found. "
            "Run: uv run python tools/update_lectio_contracts.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _load_component_registry() -> dict[str, dict]:
    path = _contracts_dir() / "component-registry.json"
    if not path.exists():
        raise FileNotFoundError(
            "component-registry.json not found. "
            "Run: uv run python tools/update_lectio_contracts.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _load_preset_registry() -> dict[str, dict]:
    path = _contracts_dir() / "preset-registry.json"
    if not path.exists():
        raise FileNotFoundError(
            "preset-registry.json not found. "
            "Run: uv run python tools/update_lectio_contracts.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _load_section_content_schema() -> dict:
    path = _contracts_dir() / "section-content-schema.json"
    if not path.exists():
        raise FileNotFoundError(
            "section-content-schema.json not found. "
            "Run: uv run python tools/update_lectio_contracts.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _required_components(contract: dict) -> list[str]:
    template_id = contract.get("id")
    required = contract.get("required_components")
    if isinstance(required, list):
        diag(
            "CONTRACT_RESOLVED_REQUIREMENTS",
            template_id=template_id,
            required_components=required,
            always_present=contract.get("always_present"),
            resolved_required_components=required,
            source="required_components",
        )
        return required

    always_present = contract.get("always_present")
    if isinstance(always_present, list):
        diag(
            "CONTRACT_RESOLVED_REQUIREMENTS",
            template_id=template_id,
            required_components=contract.get("required_components"),
            always_present=always_present,
            resolved_required_components=always_present,
            source="always_present",
        )
        return always_present

    diag(
        "CONTRACT_RESOLVED_REQUIREMENTS",
        template_id=template_id,
        required_components=contract.get("required_components"),
        always_present=contract.get("always_present"),
        resolved_required_components=[],
        source="none",
    )
    return []


def _optional_components(contract: dict) -> list[str]:
    optional = contract.get("optional_components")
    if isinstance(optional, list):
        return optional

    available = contract.get("available_components")
    if not isinstance(available, list):
        return []

    required = set(_required_components(contract))
    return [component_id for component_id in available if component_id not in required]


def _contract_defaults(template_id: str) -> dict[str, Any]:
    raw = _load_contract_raw(template_id)
    available_components = raw.get("available_components")
    if not isinstance(available_components, list):
        available_components = []
    required_components = _required_components(raw)
    optional_components = _optional_components(raw)
    if not required_components and available_components:
        required_components = [
            component_id
            for component_id in (
                "section-header",
                "hook-hero",
                "explanation-block",
                "practice-stack",
                "what-next-bridge",
            )
            if component_id in available_components
        ]
    lesson_flow = raw.get("lesson_flow")
    if not isinstance(lesson_flow, list) or not lesson_flow:
        lesson_flow = ["Hook", "Explain", "Practice"]
    generation_guidance = raw.get("generation_guidance")
    if not isinstance(generation_guidance, dict):
        generation_guidance = {}
    allowed_presets = raw.get("allowed_presets")
    if not isinstance(allowed_presets, list):
        allowed_presets = []
    return {
        "id": raw.get("id") or template_id,
        "name": raw.get("name") or template_id.replace("-", " ").title(),
        "family": raw.get("family") or template_id.rsplit("-", 1)[0],
        "intent": raw.get("intent") or "general",
        "tagline": raw.get("tagline") or "",
        "lesson_flow": lesson_flow,
        "required_components": required_components,
        "optional_components": optional_components,
        "always_present": raw.get("always_present") if isinstance(raw.get("always_present"), list) else [],
        "available_components": available_components,
        "contextually_present": raw.get("contextually_present") if isinstance(raw.get("contextually_present"), list) else [],
        "component_budget": raw.get("component_budget") if isinstance(raw.get("component_budget"), dict) else {},
        "max_per_section": raw.get("max_per_section") if isinstance(raw.get("max_per_section"), dict) else {},
        "default_behaviours": raw.get("default_behaviours") if isinstance(raw.get("default_behaviours"), dict) else {},
        "section_role_defaults": raw.get("section_role_defaults") if isinstance(raw.get("section_role_defaults"), dict) else {},
        "generation_guidance": {
            "tone": generation_guidance.get("tone") or "clear and supportive",
            "pacing": generation_guidance.get("pacing") or "steady",
            "chunking": generation_guidance.get("chunking") or "medium",
            "emphasis": generation_guidance.get("emphasis") or "conceptual clarity",
            "avoid": list(generation_guidance.get("avoid") or []),
        },
        "best_for": raw.get("best_for") if isinstance(raw.get("best_for"), list) else [],
        "not_ideal_for": raw.get("not_ideal_for") if isinstance(raw.get("not_ideal_for"), list) else [],
        "learner_fit": raw.get("learner_fit") if isinstance(raw.get("learner_fit"), list) else ["general"],
        "subjects": raw.get("subjects") if isinstance(raw.get("subjects"), list) else [],
        "interaction_level": raw.get("interaction_level") or "medium",
        "layout_notes": raw.get("layout_notes") if isinstance(raw.get("layout_notes"), list) else [],
        "responsive_rules": raw.get("responsive_rules") if isinstance(raw.get("responsive_rules"), list) else [],
        "print_rules": raw.get("print_rules") if isinstance(raw.get("print_rules"), list) else [],
        "why_this_template_exists": raw.get("why_this_template_exists") or "",
        "allowed_presets": allowed_presets,
    }


def get_contract(template_id: str) -> TemplateContractSummary:
    return TemplateContractSummary.model_validate(_contract_defaults(template_id))


def get_preset(preset_id: str) -> TemplatePresetSummary:
    try:
        registry = _load_preset_registry()
    except FileNotFoundError:
        registry = {}
    if preset_id in registry:
        return TemplatePresetSummary.model_validate(registry[preset_id])
    return TemplatePresetSummary(
        id=preset_id,
        name=preset_id.replace("-", " ").title(),
        palette="default",
        typography="default",
        density="balanced",
        surface_style="standard",
    )


def list_template_ids() -> list[str]:
    return sorted(p.stem for p in _contracts_dir().glob("*.json") if p.stem not in _META_FILES)


def get_required_fields(template_id: str) -> list[str]:
    contract = _load_contract_raw(template_id)
    field_map = _load_field_map()
    return [field_map[cid] for cid in _required_components(contract) if cid in field_map]


def get_optional_fields(template_id: str) -> list[str]:
    contract = _load_contract_raw(template_id)
    field_map = _load_field_map()
    return [field_map[cid] for cid in _optional_components(contract) if cid in field_map]


def get_generation_guidance(template_id: str) -> dict:
    raw = _load_contract_raw(template_id)
    guidance = raw.get("generation_guidance", {})
    if not isinstance(guidance, dict):
        guidance = {}
    return {
        "tone": guidance.get("tone") or "clear and supportive",
        "pacing": guidance.get("pacing") or "steady, progressive",
        "chunking": guidance.get("chunking") or "moderate chunks with clear progression",
        "emphasis": guidance.get("emphasis") or raw.get("intent") or "conceptual clarity",
        "avoid": list(guidance.get("avoid") or []),
    }


def get_lesson_flow(template_id: str) -> list[str]:
    return _load_contract_raw(template_id).get("lesson_flow", [])


def get_section_content_schema() -> dict:
    return _load_section_content_schema()


def get_component_registry_entry(component_id: str) -> dict | None:
    return _load_component_registry().get(component_id)


def get_section_field_for_component(component_id: str) -> str | None:
    return _load_field_map().get(component_id)


def get_component_generation_hint(component_id: str) -> str | None:
    entry = get_component_registry_entry(component_id)
    if not entry:
        return None
    return entry.get("generation_hint") or entry.get("purpose")


def get_component_capacity(component_id: str) -> dict:
    entry = get_component_registry_entry(component_id)
    if not entry:
        return {}
    return entry.get("capacity", {})


def get_capacity_limits(component_id: str) -> dict:
    return get_component_capacity(component_id)


def _resolve_json_pointer(schema: dict, pointer: str) -> Any:
    if not pointer.startswith("#/"):
        return None
    node: Any = schema
    for token in pointer[2:].split("/"):
        key = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _resolve_refs(schema: dict, node: Any, seen: set[str] | None = None) -> Any:
    if seen is None:
        seen = set()

    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref not in seen:
            target = _resolve_json_pointer(schema, ref)
            if target is None:
                return dict(node)
            resolved_target = _resolve_refs(schema, target, seen | {ref})
            if isinstance(resolved_target, dict):
                merged = dict(resolved_target)
                for key, value in node.items():
                    if key == "$ref":
                        continue
                    merged[key] = _resolve_refs(schema, value, seen | {ref})
                return merged
            return resolved_target
        return {key: _resolve_refs(schema, value, seen) for key, value in node.items()}
    if isinstance(node, list):
        return [_resolve_refs(schema, item, seen) for item in node]
    return node


def get_field_schema(field_name: str) -> dict | None:
    schema = _load_section_content_schema()
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        root_ref = schema.get("$ref")
        if isinstance(root_ref, str):
            resolved_root = _resolve_json_pointer(schema, root_ref)
            if isinstance(resolved_root, dict):
                properties = resolved_root.get("properties")
    if not isinstance(properties, dict):
        properties = {}
    field_schema = properties.get(field_name)
    if not isinstance(field_schema, dict):
        return None
    resolved = _resolve_refs(schema, field_schema)
    return resolved if isinstance(resolved, dict) else None


def _section_field_has_content(section: dict, field: str) -> bool:
    return bool(section.get(field))


def validate_section_for_template(
    section: dict,
    template_id: str,
    *,
    mode: str = "final",
    allow_missing_fields: set[str] | None = None,
    additional_required_fields: set[str] | None = None,
    required_components_override: list[str] | set[str] | None = None,
) -> tuple[bool, list[str]]:
    violations = []
    field_map = _load_field_map()
    contract = _load_contract_raw(template_id)
    resolved_required_components = (
        list(required_components_override)
        if required_components_override is not None
        else _required_components(contract)
    )
    allowed_missing_fields = allow_missing_fields or set()
    extra_required_fields = additional_required_fields or set()
    diag(
        "CONTRACT_VALIDATION_START",
        template_id=template_id,
        mode=mode,
        resolved_required_components=resolved_required_components,
        section_keys=sorted(section.keys()),
        allow_missing_fields=sorted(allowed_missing_fields),
        additional_required_fields=sorted(extra_required_fields),
        required_components_override=sorted(required_components_override)
        if required_components_override is not None
        else None,
    )

    for component_id in resolved_required_components:
        field = field_map.get(component_id)
        content_present = _section_field_has_content(section, field) if field is not None else False
        diag(
            "CONTRACT_REQUIRED_CHECK",
            template_id=template_id,
            component_id=component_id,
            field=field,
            content_present=content_present,
        )
        if field is None:
            continue
        if mode == "partial" and field in allowed_missing_fields:
            continue
        if not _section_field_has_content(section, field):
            violations.append(
                f"Required component '{component_id}' has no content "
                f"(missing field: '{field}')"
            )

    for field in sorted(extra_required_fields):
        if mode == "partial" and field in allowed_missing_fields:
            continue
        if not _section_field_has_content(section, field):
            violations.append(f"Required field '{field}' has no content for template '{template_id}'")

    if section.get("template_id") != template_id:
        violations.append(
            f"Section template_id '{section.get('template_id')}' "
            f"does not match expected '{template_id}'"
        )

    diag("CONTRACT_VALIDATION_RESULT", template_id=template_id, violations=violations)
    return len(violations) == 0, violations


def _section_plan_list(section_plan: Any, field: str) -> list[str]:
    value = None
    if isinstance(section_plan, dict):
        value = section_plan.get(field)
    else:
        value = getattr(section_plan, field, None)
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _section_plan_id(section_plan: Any) -> str:
    if isinstance(section_plan, dict):
        return str(section_plan.get("section_id", ""))
    return str(getattr(section_plan, "section_id", "") or "")


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _field_contract(component_id: str, *, required: bool) -> GenerationFieldContract | None:
    field_name = get_section_field_for_component(component_id)
    if not field_name:
        return None
    return GenerationFieldContract(
        component_id=component_id,
        field_name=field_name,
        required=required,
        external=field_name in _EXTERNAL_FIELDS,
        schema=get_field_schema(field_name) or {},
        capacity=get_component_capacity(component_id),
        generation_hint=get_component_generation_hint(component_id),
    )


def build_section_generation_manifest(
    *,
    template_id: str,
    section_plan,
) -> SectionGenerationManifest:
    contract = _load_contract_raw(template_id)
    required_components = _section_plan_list(section_plan, "required_components")
    optional_components = _section_plan_list(section_plan, "optional_components")

    if not required_components:
        required_components = _required_components(contract)

    if not optional_components:
        optional_components = _optional_components(contract)

    required_components = _dedupe(required_components)
    optional_components = [
        component_id
        for component_id in _dedupe(optional_components)
        if component_id not in set(required_components)
    ]

    required_fields: list[GenerationFieldContract] = []
    optional_fields: list[GenerationFieldContract] = []
    external_fields: list[GenerationFieldContract] = []

    for component_id in required_components:
        field_contract = _field_contract(component_id, required=True)
        if field_contract is None:
            continue
        if field_contract.external:
            external_fields.append(field_contract)
        else:
            required_fields.append(field_contract)

    for component_id in optional_components:
        field_contract = _field_contract(component_id, required=False)
        if field_contract is None:
            continue
        if field_contract.external:
            external_fields.append(field_contract)
        else:
            optional_fields.append(field_contract)

    return SectionGenerationManifest(
        template_id=template_id,
        section_id=_section_plan_id(section_plan),
        required_fields=required_fields,
        optional_fields=optional_fields,
        external_fields=external_fields,
    )


def get_allowed_presets(template_id: str) -> list[str]:
    allowed = _load_contract_raw(template_id).get("allowed_presets", [])
    return allowed if isinstance(allowed, list) else []


def validate_preset_for_template(template_id: str, preset_id: str) -> bool:
    allowed = get_allowed_presets(template_id)
    if not allowed:
        return True
    return preset_id in allowed


def clear_cache() -> None:
    _load_contract_raw.cache_clear()
    _load_field_map.cache_clear()
    _load_component_registry.cache_clear()
    _load_preset_registry.cache_clear()
    _load_section_content_schema.cache_clear()
