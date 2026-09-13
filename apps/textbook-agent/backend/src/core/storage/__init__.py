"""Compatibility shim - use `infra.storage`.

Temporary (R3). Remove when all call sites import the infra/curriculum path (R7).
"""

from __future__ import annotations

import sys
from importlib import import_module

_mod = import_module("infra.storage")
sys.modules[__name__] = _mod

# Ensure submodule imports share the infra module object (avoid dual loads that
# break monkeypatch targets like core.storage.gcs_image_store).
_gcs = import_module("infra.storage.gcs_image_store")
sys.modules[f"{__name__}.gcs_image_store"] = _gcs
