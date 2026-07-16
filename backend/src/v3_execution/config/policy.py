from __future__ import annotations

import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def coherence_repair_enabled() -> bool:
    """Compatibility flag; no automatic coherence rewrite executor currently exists."""
    return _env_bool("V3_COHERENCE_REPAIR_ENABLED", False)


def ship_with_holes_enabled() -> bool:
    return _env_bool("V3_SHIP_WITH_HOLES", True)


__all__ = ["coherence_repair_enabled", "ship_with_holes_enabled"]
