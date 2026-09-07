"""Compatibility shim - use `print.generation.catalogue_projections`.

Temporary (R4). Remove when all call sites import the domain path (R7).
"""

from __future__ import annotations

from print.generation.catalogue_projections import *  # noqa: F401,F403
