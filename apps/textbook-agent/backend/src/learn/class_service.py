"""Compatibility shim — use `learn.runtime.class_service`.

Temporary (C2). Remove when all call sites import the learn subdomain path (C3).
"""

from __future__ import annotations

from learn.runtime.class_service import *
