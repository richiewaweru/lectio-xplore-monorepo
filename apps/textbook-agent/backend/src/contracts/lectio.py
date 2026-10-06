"""Compatibility shim - use ``learn.contracts.lectio``.

Temporary (R4). Remove when all call sites import the learn path (R7).
"""

from __future__ import annotations

from learn.contracts.lectio import *  # noqa: F403 - compatibility re-export shim
from learn.contracts.lectio import _EXTERNAL_FIELDS  # noqa: F401
