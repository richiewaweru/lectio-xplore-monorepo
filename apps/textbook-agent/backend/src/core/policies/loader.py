"""File-backed generation policy (legal vocabularies and path mappings).

Markdown specs live in the prompt manifest. YAML here owns stable options:
learner-action vocabulary, Learn interaction candidates, Print treatments.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml

_POLICIES_DIR = Path(__file__).resolve().parents[3] / "resources" / "policies"

_WORKED_EXAMPLE_INTENTS = frozenset(
    {"demonstrate", "model", "worked-example", "walkthrough"}
)


class PolicyNotFoundError(FileNotFoundError):
    """Raised when a required policy YAML is missing."""


def _policy_path(name: str) -> Path:
    return _POLICIES_DIR / name


@lru_cache(maxsize=16)
def load_policy(name: str) -> dict[str, Any]:
    path = _policy_path(name)
    if not path.exists():
        raise PolicyNotFoundError(f"Policy file missing: {path}")
    with path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"Policy {name} must be a mapping")
    return loaded


def load_learner_actions() -> dict[str, Any]:
    return load_policy("learner-actions.yaml")


def load_learn_action_map() -> dict[str, Any]:
    return load_policy("learn-action-map.yaml")


def load_print_action_map() -> dict[str, Any]:
    return load_policy("print-action-map.yaml")


def passive_learner_actions() -> frozenset[str]:
    data = load_learner_actions()
    items = data.get("passive_actions") or []
    return frozenset(str(item) for item in items)


def _resolve_action_key(action: str, actions: Mapping[str, Any]) -> str:
    spec = actions.get(action)
    if isinstance(spec, Mapping) and spec.get("alias_of"):
        return str(spec["alias_of"])
    return action


def learn_interaction_for_action(action: str | None) -> str | None:
    if not action:
        return None
    if action in passive_learner_actions():
        return None
    data = load_learn_action_map()
    mappings = data.get("mappings") or {}
    spec = mappings.get(action)
    if not isinstance(spec, Mapping):
        vocab = load_learner_actions().get("actions") or {}
        canonical = _resolve_action_key(action, vocab)
        spec = mappings.get(canonical)
    if not isinstance(spec, Mapping):
        return None
    default = spec.get("default")
    return str(default) if default else None


def print_treatment_for_action(
    action: str | None,
    *,
    intent: str | None = None,
) -> str | None:
    if not action or action in passive_learner_actions():
        return None
    data = load_print_action_map()
    mappings = data.get("mappings") or {}
    spec = mappings.get(action)
    if not isinstance(spec, Mapping):
        return None
    normalized_intent = (intent or "").strip().lower().replace("_", "-")
    for rule in data.get("contextual_rules") or []:
        if not isinstance(rule, Mapping):
            continue
        when = rule.get("when") or {}
        intents = {str(item) for item in (when.get("intents") or [])}
        actions = {str(item) for item in (when.get("actions") or [])}
        if normalized_intent in intents and action in actions:
            prefer = rule.get("prefer")
            if prefer:
                return str(prefer)
    default = spec.get("default")
    return str(default) if default else None


def learn_defaults() -> dict[str, str]:
    mappings = load_learn_action_map().get("mappings") or {}
    out: dict[str, str] = {}
    for key, spec in mappings.items():
        if isinstance(spec, Mapping) and spec.get("default"):
            out[str(key)] = str(spec["default"])
    return out


def print_defaults() -> dict[str, str]:
    mappings = load_print_action_map().get("mappings") or {}
    out: dict[str, str] = {}
    for key, spec in mappings.items():
        if isinstance(spec, Mapping) and spec.get("default"):
            out[str(key)] = str(spec["default"])
    return out


__all__ = [
    "PolicyNotFoundError",
    "learn_defaults",
    "learn_interaction_for_action",
    "load_learn_action_map",
    "load_learner_actions",
    "load_policy",
    "load_print_action_map",
    "passive_learner_actions",
    "print_defaults",
    "print_treatment_for_action",
]
