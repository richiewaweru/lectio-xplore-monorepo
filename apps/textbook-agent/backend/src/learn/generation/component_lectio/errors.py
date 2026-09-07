"""Shared Component Lectio errors."""

from __future__ import annotations


class WorkOrderIdentityError(ValueError):
    """Generated output claimed an identity that does not match the ExactWorkOrder."""


class AnswerKeyMappingError(TypeError):
    """Deterministic answer-key assembly failed — programming/adapter defect."""


class UnsupportedProductionComponent(RuntimeError):
    """A production-selectable component has no payload strategy."""


__all__ = [
    "AnswerKeyMappingError",
    "UnsupportedProductionComponent",
    "WorkOrderIdentityError",
]
