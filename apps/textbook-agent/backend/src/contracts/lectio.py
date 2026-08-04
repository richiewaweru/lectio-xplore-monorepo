"""
contracts.lectio

Deterministic boundary between pipeline code and exported Lectio contracts.
"""

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from contracts.generation_manifest import (
    GenerationFieldContract,
    SectionGenerationManifest,
)
from contracts.template_contract import TemplateContractSummary, TemplatePresetSummary

_META_FILES = {
    "classification",
    "component-examples",
    "component-field-map",
    "component-registry",
    "component-schemas",
    "lectio-content-contract",
    "manifest",
    "preset-registry",
    "print-rules",
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

# Components that exist in the Builder palette but require teacher-provided media.
# AI generation must not plan or fill these until Lectio exposes a generatable
# media contract for them.
MANUAL_ONLY_COMPONENT_IDS = {"image-block", "video-embed"}


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


@lru_cache(maxsize=None)
def _load_manifest() -> dict:
    path = _contracts_dir() / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(
            "manifest.json not found. "
            "Run: uv run python tools/update_lectio_contracts.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _load_lectio_content_contract() -> dict:
    """Load the unified Lectio content contract (lectio-content-contract.json)."""
    path = _contracts_dir() / "lectio-content-contract.json"
    if not path.exists():
        raise FileNotFoundError(
            "lectio-content-contract.json not found in backend/contracts/. "
            "Run: uv run python tools/update_lectio_contracts.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def get_component_card(component_id: str) -> dict | None:
    """
    Return the full component card for the given component_id from
    lectio-content-contract.json, or None if the component is unknown.

    A card contains: component_id, section_field, role, cognitive_job,
    capacity, capabilities, field_contracts, component_constraints, examples,
    print, print_behavior.

    Use this instead of get_component_registry_entry() in V3 code paths.
    """
    return _load_lectio_content_contract().get("component_cards", {}).get(component_id)


def get_component_schema_shape(component_id: str) -> dict | None:
    """
    Resolve the schema shape for a component from section-content-schema.json.

    Returns a dict with ``definition`` (definition name) and ``properties`` (list of
    property descriptors) for writer prompts. Does not replace runtime validation.

    Returns None if the card is missing, ``schema_summary.$ref`` is absent, or
    resolution fails. Never raises.
    """
    try:
        card = get_component_card(component_id)
        if not card:
            return None
        ref = card.get("schema_summary", {}).get("$ref")
        if not isinstance(ref, str) or not ref:
            return None
        def_name = ref.split("/")[-1]
        schema = get_section_content_schema()
        defn = schema.get("definitions", {}).get(def_name)
        if not isinstance(defn, dict):
            return None
        props_raw = defn.get("properties")
        if not isinstance(props_raw, dict):
            return None
        required_fields = set(defn.get("required", []))
        properties: list[dict] = []
        for prop_name, prop_schema in props_raw.items():
            if not isinstance(prop_schema, dict):
                continue
            properties.append(
                _schema_shape_property(
                    schema,
                    prop_name,
                    prop_schema,
                    prop_name in required_fields,
                    expand_array_items=True,
                )
            )
        return {"definition": def_name, "properties": properties}
    except Exception:
        return None


def _schema_shape_property(
    schema: dict,
    name: str,
    prop_schema: dict,
    required: bool,
    *,
    expand_array_items: bool,
) -> dict:
    typ, enum_vals, nested = _describe_schema_property_shape(
        schema, prop_schema, expand_array_items=expand_array_items
    )
    return {
        "name": name,
        "type": typ,
        "required": required,
        "enum": enum_vals,
        "nested": nested,
    }


def _describe_schema_property_shape(
    schema: dict,
    prop_schema: dict,
    *,
    expand_array_items: bool,
) -> tuple[str, list[str] | None, list[dict] | None]:
    """Return (display_type, enum_or_none, nested_property_dicts_or_none)."""
    ref = prop_schema.get("$ref")
    if isinstance(ref, str):
        resolved = _resolve_json_pointer(schema, ref)
        if not isinstance(resolved, dict):
            return ("object", None, None)
        rt = resolved.get("type")
        if rt == "string":
            ev = list(resolved["enum"]) if isinstance(resolved.get("enum"), list) else None
            return ("string", ev, None)
        if rt in ("integer", "number", "boolean"):
            return (str(rt), None, None)
        if rt == "array":
            return ("array", None, None)
        if rt == "object":
            return ("object", None, None)
        return (str(rt), None, None) if isinstance(rt, str) else ("object", None, None)

    ptype = prop_schema.get("type")
    if ptype == "string":
        ev = list(prop_schema["enum"]) if isinstance(prop_schema.get("enum"), list) else None
        return ("string", ev, None)
    if ptype in ("number", "integer", "boolean"):
        return (str(ptype), None, None)
    if ptype == "array":
        items = prop_schema.get("items")
        if not isinstance(items, dict):
            return ("array", None, None)
        if items.get("type") == "string":
            return ("string[]", None, None)
        it = items.get("type")
        if it in ("number", "integer", "boolean"):
            return (f"{it}[]", None, None)
        iref = items.get("$ref")
        if isinstance(iref, str) and expand_array_items:
            item_def = _resolve_json_pointer(schema, iref)
            nested: list[dict] | None = None
            if isinstance(item_def, dict) and item_def.get("type") == "object":
                nested_req = set(item_def.get("required", []))
                nested_list: list[dict] = []
                nprops = item_def.get("properties")
                if isinstance(nprops, dict):
                    for n_name, n_sch in nprops.items():
                        if not isinstance(n_sch, dict):
                            continue
                        nested_list.append(
                            _schema_shape_property(
                                schema,
                                n_name,
                                n_sch,
                                n_name in nested_req,
                                expand_array_items=False,
                            )
                        )
                nested = nested_list
            return ("array", None, nested)
        return ("array", None, None)
    if ptype == "object":
        return ("object", None, None)

    if "items" in prop_schema and isinstance(prop_schema.get("items"), dict):
        merged = dict(prop_schema)
        merged["type"] = "array"
        return _describe_schema_property_shape(schema, merged, expand_array_items=expand_array_items)

    return ("object", None, None)


def get_planner_index() -> dict:
    """
    Return the planner_index from lectio-content-contract.json.

    Shape:
      {
        "component_ids": [...],
        "phase_map": {
          "1": { "name": "Orient", "description": "...", "components": [...] },
          ...
        }
      }

    Use this in the architect prompt instead of reading manifest.json phases.
    """
    return _load_lectio_content_contract().get("planner_index", {})


def get_template_contract(template_id: str) -> dict | None:
    """
    Return template metadata from lectio-content-contract.json for the given
    template_id, or None if the template is unknown.

    Shape:
      {
        "always_present": [...],
        "available_components": [...],
        "component_budget": { "diagram-block": 2, ... },
        "max_per_section": { "worked-example-card": 1, ... }
      }

    Use this instead of reading guided-concept-path.json directly.
    """
    return _load_lectio_content_contract().get("templates", {}).get(template_id)


def get_formatting_policy() -> dict:
    """
    Return the format type legend from lectio-content-contract.json.

    Keys are format type names (e.g. "block_markdown", "plain_phrase_list").
    Values are human-readable descriptions of what each format means.

    Emit this once at the top of the section writer prompt as a legend,
    not per-component.
    """
    return _load_lectio_content_contract().get("formatting_policy", {})


def get_lectio_print_surface() -> dict[str, Any]:
    """Root ``print_surface`` from lectio-content-contract.json (A4 sizing, usable_height_px)."""
    raw = _load_lectio_content_contract().get("print_surface")
    return raw if isinstance(raw, dict) else {}


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


def get_contract(template_id: str) -> TemplateContractSummary:
    return TemplateContractSummary.model_validate(_load_contract_raw(template_id))


def get_preset(preset_id: str) -> TemplatePresetSummary:
    registry = _load_preset_registry()
    if preset_id not in registry:
        raise ValueError(f"Unknown preset '{preset_id}'. Available: {sorted(registry.keys())}")
    return TemplatePresetSummary.model_validate(registry[preset_id])


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
    return _load_contract_raw(template_id).get("generation_guidance", {})


def get_lesson_flow(template_id: str) -> list[str]:
    return _load_contract_raw(template_id).get("lesson_flow", [])


def get_section_content_schema() -> dict:
    return _load_section_content_schema()


def get_manifest() -> dict:
    """Lectio v3 component manifest (phases, roles, cognitive jobs)."""
    return _load_manifest()


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
    required_components = _section_plan_list(section_plan, "required_components")
    optional_components = _section_plan_list(section_plan, "optional_components")

    if not required_components:
        raise ValueError(
            f"Section {_section_plan_id(section_plan) or '<unknown>'} has no required_components. "
            "This is a planning failure."
        )

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
            raise ValueError(f"Unknown required component '{component_id}' in section manifest build.")
        if field_contract.external:
            external_fields.append(field_contract)
        else:
            required_fields.append(field_contract)

    for component_id in optional_components:
        field_contract = _field_contract(component_id, required=False)
        if field_contract is None:
            raise ValueError(f"Unknown optional component '{component_id}' in section manifest build.")
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
    return _load_contract_raw(template_id).get("allowed_presets", [])


def validate_preset_for_template(template_id: str, preset_id: str) -> bool:
    return preset_id in get_allowed_presets(template_id)


def clear_cache() -> None:
    _load_contract_raw.cache_clear()
    _load_field_map.cache_clear()
    _load_component_registry.cache_clear()
    _load_preset_registry.cache_clear()
    _load_section_content_schema.cache_clear()
    _load_manifest.cache_clear()
    _load_lectio_content_contract.cache_clear()

