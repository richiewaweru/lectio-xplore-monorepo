from __future__ import annotations

import logging
from pathlib import Path

import yaml

from resource_specs.schema import ResourceSpec

logger = logging.getLogger(__name__)
_SPECS_DIR = Path(__file__).parents[2] / "resources" / "specs"
_REGISTRY: dict[str, ResourceSpec] = {}


def load_all_specs(specs_dir: Path = _SPECS_DIR) -> dict[str, ResourceSpec]:
    registry: dict[str, ResourceSpec] = {}
    paths = sorted(specs_dir.glob("*.yaml"))
    if not paths:
        raise RuntimeError(f"No resource specs found in {specs_dir}")
    for path in paths:
        try:
            with path.open(encoding="utf-8") as handle:
                raw = yaml.safe_load(handle)
            spec = ResourceSpec.model_validate(raw)
        except Exception as exc:
            raise RuntimeError(f"Invalid resource spec {path.name}: {exc}") from exc
        registry[spec.id] = spec
        logger.info("Loaded resource spec: %s v%s", spec.id, spec.version)
    return registry


def get_spec(resource_type: str) -> ResourceSpec:
    if not _REGISTRY:
        _REGISTRY.update(load_all_specs())
    if resource_type not in _REGISTRY:
        raise KeyError(f"No resource spec found for type: {resource_type}")
    return _REGISTRY[resource_type]


def list_spec_ids() -> list[str]:
    if not _REGISTRY:
        _REGISTRY.update(load_all_specs())
    return list(_REGISTRY)


def initialize_registry() -> None:
    _REGISTRY.clear()
    _REGISTRY.update(load_all_specs())
    logger.info("Resource spec registry ready: %s", list(_REGISTRY))
