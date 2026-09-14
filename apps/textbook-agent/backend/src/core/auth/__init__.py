"""Compatibility shim - use `infra.auth`.

Temporary (R3). Remove when all call sites import the infra/curriculum path (R7).
"""

from __future__ import annotations

import sys
from importlib import import_module

_mod = import_module("infra.auth")
sys.modules[__name__] = _mod

# Alias submodules so `core.auth.middleware` is the same module object as
# `infra.auth.middleware` (avoids dual dependency overrides in tests).
for _sub in ("middleware", "jwt_handler", "google_auth"):
    _full = f"infra.auth.{_sub}"
    _alias = f"{__name__}.{_sub}"
    try:
        _submod = import_module(_full)
    except ModuleNotFoundError:
        continue
    sys.modules[_alias] = _submod
    setattr(_mod, _sub, _submod)
