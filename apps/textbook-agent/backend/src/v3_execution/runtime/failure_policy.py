"""Typed failure classification, budgets, and scoped repair (Phase 05)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FailureClass(str, Enum):
    TRANSPORT_RETRYABLE = "transport_retryable"
    RATE_LIMITED = "rate_limited"
    MODEL_OUTPUT_RETRYABLE = "model_output_retryable"
    COMPONENT_REPAIRABLE = "component_repairable"
    VISUAL_RETRYABLE = "visual_retryable"
    TERMINAL_CODE_ERROR = "terminal_code_error"
    LEASE_LOST = "lease_lost"  # stub for Phase 07
    CANCELLED = "cancelled"  # stub for later


@dataclass(frozen=True)
class FailureBudgets:
    transport: int = 3
    rate_limit: int = 3
    model_output: int = 2
    component_repairs: int = 1
    visual: int = 2


@dataclass
class BudgetLedger:
    budgets: FailureBudgets = field(default_factory=FailureBudgets)
    used: dict[str, int] = field(default_factory=dict)

    def remaining(self, kind: FailureClass) -> int:
        mapping = {
            FailureClass.TRANSPORT_RETRYABLE: self.budgets.transport,
            FailureClass.RATE_LIMITED: self.budgets.rate_limit,
            FailureClass.MODEL_OUTPUT_RETRYABLE: self.budgets.model_output,
            FailureClass.COMPONENT_REPAIRABLE: self.budgets.component_repairs,
            FailureClass.VISUAL_RETRYABLE: self.budgets.visual,
        }
        limit = mapping.get(kind, 0)
        return max(0, limit - self.used.get(kind.value, 0))

    def consume(self, kind: FailureClass) -> bool:
        if self.remaining(kind) <= 0:
            return False
        self.used[kind.value] = self.used.get(kind.value, 0) + 1
        return True


@dataclass(frozen=True)
class ClassifiedFailure:
    failure_class: FailureClass
    message: str
    block_id: str | None = None
    retryable: bool = False
    repairable: bool = False
    terminal: bool = False


@dataclass(frozen=True)
class RecoveryAction:
    action: str  # retry | repair | stop | reclaim
    failure_class: FailureClass
    block_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


def classify_failure(
    exc: BaseException | str,
    *,
    block_id: str | None = None,
    status_code: int | None = None,
    kind_hint: str | None = None,
) -> ClassifiedFailure:
    message = str(exc)
    lowered = message.lower()
    hint = (kind_hint or "").lower()

    if hint == "lease_lost" or "lease lost" in lowered or "ownership" in lowered:
        return ClassifiedFailure(
            FailureClass.LEASE_LOST, message, block_id=block_id, terminal=True
        )
    if hint == "cancelled" or "cancelled" in lowered:
        return ClassifiedFailure(
            FailureClass.CANCELLED, message, block_id=block_id, terminal=True
        )
    if isinstance(exc, (TypeError, AttributeError, KeyError, ImportError)):
        return ClassifiedFailure(
            FailureClass.TERMINAL_CODE_ERROR, message, block_id=block_id, terminal=True
        )
    if status_code == 429 or "rate limit" in lowered or "too many requests" in lowered:
        return ClassifiedFailure(
            FailureClass.RATE_LIMITED, message, block_id=block_id, retryable=True
        )
    if status_code in {408, 500, 502, 503, 504} or any(
        token in lowered for token in ("timeout", "timed out", "connection reset", "temporarily")
    ):
        return ClassifiedFailure(
            FailureClass.TRANSPORT_RETRYABLE, message, block_id=block_id, retryable=True
        )
    if hint == "visual" or "visual" in lowered:
        return ClassifiedFailure(
            FailureClass.VISUAL_RETRYABLE, message, block_id=block_id, retryable=True
        )
    if any(
        token in lowered
        for token in ("validation", "lectio", "schema", "field_contracts", "invalid component")
    ):
        return ClassifiedFailure(
            FailureClass.COMPONENT_REPAIRABLE,
            message,
            block_id=block_id,
            repairable=True,
        )
    if any(token in lowered for token in ("json", "parse", "malformed", "output")):
        return ClassifiedFailure(
            FailureClass.MODEL_OUTPUT_RETRYABLE,
            message,
            block_id=block_id,
            retryable=True,
        )
    return ClassifiedFailure(
        FailureClass.MODEL_OUTPUT_RETRYABLE, message, block_id=block_id, retryable=True
    )


def recovery_for(
    failure: ClassifiedFailure,
    ledger: BudgetLedger,
    *,
    sibling_block_ids: list[str] | None = None,
) -> RecoveryAction:
    siblings = list(sibling_block_ids or [])
    if failure.failure_class in {FailureClass.TERMINAL_CODE_ERROR, FailureClass.CANCELLED}:
        return RecoveryAction("stop", failure.failure_class, failure.block_id)
    if failure.failure_class == FailureClass.LEASE_LOST:
        return RecoveryAction("reclaim", failure.failure_class, failure.block_id)

    if failure.repairable:
        if not ledger.consume(FailureClass.COMPONENT_REPAIRABLE):
            return RecoveryAction("stop", failure.failure_class, failure.block_id)
        return RecoveryAction(
            "repair",
            failure.failure_class,
            failure.block_id,
            payload={
                "scoped_block_id": failure.block_id,
                "preserve_siblings": siblings,
                "message": failure.message,
            },
        )

    if failure.retryable:
        if not ledger.consume(failure.failure_class):
            return RecoveryAction("stop", failure.failure_class, failure.block_id)
        return RecoveryAction(
            "retry",
            failure.failure_class,
            failure.block_id,
            payload={"message": failure.message},
        )

    return RecoveryAction("stop", failure.failure_class, failure.block_id)


def scoped_repair_keeps_siblings_ready(
    *,
    failed_block_id: str,
    ready_block_ids: list[str],
) -> list[str]:
    """Repair one block without regenerating valid siblings."""
    return [block_id for block_id in ready_block_ids if block_id != failed_block_id]
