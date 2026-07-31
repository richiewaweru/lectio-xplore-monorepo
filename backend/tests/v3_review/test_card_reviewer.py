from __future__ import annotations

import pytest

from v3_blueprint.models import CardMisconceptionPlan, CardRubricPlan
from v3_review.card_reviewer import (
    CardQCCheck,
    CardQCResult,
    validate_card_qc_result,
)


def _card() -> CardRubricPlan:
    return CardRubricPlan(
        card_id="biology.photosynthesis.inputs",
        objective="Identify the inputs to photosynthesis.",
        misconceptions=[
            CardMisconceptionPlan(
                id="M1",
                description="Plants obtain food directly from soil.",
            )
        ],
    )


def test_card_qc_accepts_complete_card_variant_rubric() -> None:
    result = CardQCResult(
        card_id="biology.photosynthesis.inputs",
        variant_label="Support",
        checks=[
            CardQCCheck(check="objective", result="PASS", reason="Covered."),
            CardQCCheck(check="M1", result="PASS", reason="Confronted."),
            CardQCCheck(check="scope", result="PASS", reason="In scope."),
            CardQCCheck(check="notation", result="PASS", reason="Consistent."),
        ],
        verdict="pass",
    )

    assert validate_card_qc_result(
        result,
        card=_card(),
        variant_label="Support",
    ) is result


def test_card_qc_rejects_omitted_misconception_check() -> None:
    result = CardQCResult(
        card_id="biology.photosynthesis.inputs",
        variant_label="Support",
        checks=[
            CardQCCheck(check="objective", result="PASS", reason="Covered."),
            CardQCCheck(check="scope", result="PASS", reason="In scope."),
            CardQCCheck(check="notation", result="PASS", reason="Consistent."),
        ],
        verdict="pass",
    )

    with pytest.raises(ValueError, match="omitted checks: M1"):
        validate_card_qc_result(
            result,
            card=_card(),
            variant_label="Support",
        )


def test_card_qc_requires_repair_verdict_for_failed_check() -> None:
    result = CardQCResult(
        card_id="biology.photosynthesis.inputs",
        variant_label="Support",
        checks=[
            CardQCCheck(
                check="objective",
                result="FAIL",
                reason="The input list is missing.",
                correction_hint="Add carbon dioxide and water.",
            ),
            CardQCCheck(check="M1", result="PASS", reason="Confronted."),
            CardQCCheck(check="scope", result="PASS", reason="In scope."),
            CardQCCheck(check="notation", result="PASS", reason="Consistent."),
        ],
        verdict="pass",
    )

    with pytest.raises(ValueError, match="must be 'repair'"):
        validate_card_qc_result(
            result,
            card=_card(),
            variant_label="Support",
        )
