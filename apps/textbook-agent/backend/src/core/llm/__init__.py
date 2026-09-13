"""Compatibility shim - use `infra.llm`.

Temporary (R3). Remove when all call sites import the infra/curriculum path (R7).
"""

from __future__ import annotations

import sys
from importlib import import_module

_mod = import_module("infra.llm")
sys.modules[__name__] = _mod

for _sub in (
    "transport",
    "runner",
    "cost",
    "types",
    "schema",
    "deepseek_schema",
    "logging",
):
    _loaded = import_module(f"infra.llm.{_sub}")
    sys.modules[f"{__name__}.{_sub}"] = _loaded
