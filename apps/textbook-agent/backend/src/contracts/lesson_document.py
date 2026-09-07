"""Compatibility shim - use `learn.contracts.lesson_document`.

Temporary (R4). Remove when all call sites import the domain path (R7).
"""

from __future__ import annotations

from learn.contracts.lesson_document import *  # noqa: F401,F403
