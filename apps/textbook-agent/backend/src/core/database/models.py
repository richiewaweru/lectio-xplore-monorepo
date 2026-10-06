"""Compatibility shim — ORM ownership is `infra.database.models`.

Temporary until D5 removes core.database wrappers.
"""

from __future__ import annotations

from infra.database.models import *  # noqa: F403 - compatibility re-export shim
