"""Compatibility shim - use `print.generation.page_blocks`.

Temporary (R4). Remove when all call sites import the domain path (R7).
"""

from __future__ import annotations

from print.generation.page_blocks import *  # noqa: F401,F403
