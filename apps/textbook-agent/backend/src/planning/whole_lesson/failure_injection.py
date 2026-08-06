"""Test-only failure injection for Phase 02 resilience proofs."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class FailureInjectionConfig:
    enabled: bool = False
    generation_id: str | None = None
    fail_block_index: int | None = None
    fail_once: bool = True
    _tripped: bool = False

    def should_fail(self, *, generation_id: str, block_index: int) -> bool:
        if not self.enabled:
            return False
        if self.generation_id and generation_id != self.generation_id:
            return False
        if self.fail_block_index is None or block_index != self.fail_block_index:
            return False
        if self.fail_once and self._tripped:
            return False
        self._tripped = True
        return True


_CONFIG = FailureInjectionConfig(
    enabled=os.getenv("XPLORE_NATIVE_FAILURE_INJECTION", "").strip().lower()
    in {"1", "true", "yes"},
)


def get_failure_injection() -> FailureInjectionConfig:
    return _CONFIG


def configure_failure_injection(
    *,
    enabled: bool,
    generation_id: str | None = None,
    fail_block_index: int | None = None,
    fail_once: bool = True,
) -> FailureInjectionConfig:
    global _CONFIG
    _CONFIG = FailureInjectionConfig(
        enabled=enabled,
        generation_id=generation_id,
        fail_block_index=fail_block_index,
        fail_once=fail_once,
    )
    return _CONFIG


def reset_failure_injection() -> None:
    configure_failure_injection(enabled=False)
