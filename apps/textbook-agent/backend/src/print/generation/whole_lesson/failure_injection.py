"""Test-only failure injection for native resilience proofs.

Writer-block injection is unchanged. A separate exact-generation node hook can
trip ``planning_forms`` once. Both require the master switch and are refused in
production-like environments. There is no HTTP/API configuration surface.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_TRUTHY = {"1", "true", "yes", "on"}
_PRODUCTION_LIKE = {"production", "prod", "staging"}
_ALLOWED_NODES = frozenset({"planning_forms"})


def _env_flag(name: str, default: str = "") -> bool:
    return os.getenv(name, default).strip().lower() in _TRUTHY


def _app_env() -> str:
    return (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development").strip().lower()


@dataclass
class FailureInjectionConfig:
    enabled: bool = False
    generation_id: str | None = None
    fail_block_index: int | None = None
    node: str | None = None
    fail_once: bool = True
    refused_reason: str | None = None
    _tripped: bool = False

    def should_fail(self, *, generation_id: str, block_index: int) -> bool:
        if not self.enabled:
            return False
        if self.node and self.node != "writer_block":
            return False
        if self.generation_id and generation_id != self.generation_id:
            return False
        if self.fail_block_index is None or block_index != self.fail_block_index:
            return False
        if self.fail_once and self._tripped:
            return False
        self._tripped = True
        return True

    def should_fail_node(self, *, generation_id: str, node: str) -> bool:
        if not self.enabled:
            return False
        if not self.node or self.node != node:
            return False
        if not self.generation_id or generation_id != self.generation_id:
            return False
        if self.fail_once and self._tripped:
            return False
        self._tripped = True
        return True


def load_failure_injection_from_env() -> FailureInjectionConfig:
    """Parse env. Default disabled; fail closed on incomplete or production-like config."""
    if _app_env() in _PRODUCTION_LIKE:
        logger.warning("native failure injection refused: production-like APP_ENV")
        return FailureInjectionConfig(
            enabled=False,
            refused_reason="production-like APP_ENV",
        )
    enabled = _env_flag("XPLORE_NATIVE_FAILURE_INJECTION")
    generation_id = os.getenv("XPLORE_NATIVE_FAILURE_GENERATION_ID", "").strip() or None
    node = os.getenv("XPLORE_NATIVE_FAILURE_NODE", "").strip() or None
    once_raw = os.getenv("XPLORE_NATIVE_FAILURE_ONCE", "true").strip().lower()
    fail_once = once_raw in _TRUTHY or once_raw == ""
    if not enabled:
        logger.info("native failure injection disabled")
        return FailureInjectionConfig(enabled=False)
    if node and node not in _ALLOWED_NODES:
        logger.warning("native failure injection refused: unknown node %s", node)
        return FailureInjectionConfig(
            enabled=False,
            refused_reason=f"unknown node {node!r}",
        )
    if node == "planning_forms" and not generation_id:
        logger.warning("native failure injection refused: planning_forms requires exact generation id")
        return FailureInjectionConfig(
            enabled=False,
            refused_reason="planning_forms requires XPLORE_NATIVE_FAILURE_GENERATION_ID",
        )
    return FailureInjectionConfig(
        enabled=True,
        generation_id=generation_id,
        node=node,
        fail_once=fail_once,
    )


_CONFIG = load_failure_injection_from_env()


def get_failure_injection() -> FailureInjectionConfig:
    return _CONFIG


def configure_failure_injection(
    *,
    enabled: bool,
    generation_id: str | None = None,
    fail_block_index: int | None = None,
    fail_once: bool = True,
    node: str | None = None,
) -> FailureInjectionConfig:
    global _CONFIG
    _CONFIG = FailureInjectionConfig(
        enabled=enabled,
        generation_id=generation_id,
        fail_block_index=fail_block_index,
        fail_once=fail_once,
        node=node,
    )
    return _CONFIG


def reload_failure_injection_from_env() -> FailureInjectionConfig:
    global _CONFIG
    _CONFIG = load_failure_injection_from_env()
    return _CONFIG


def reset_failure_injection() -> None:
    configure_failure_injection(enabled=False)
