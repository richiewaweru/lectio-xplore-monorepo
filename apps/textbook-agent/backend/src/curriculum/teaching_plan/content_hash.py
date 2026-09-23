"""Canonical identity for teacher-visible Teaching Plan content."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from curriculum.teaching_plan.models import TeachingPlan

_NON_PEDAGOGICAL_FIELDS = {
    "teaching_plan_id",
    "revision",
    "preparation_hash",
    "approval_status",
}


def teaching_plan_content_hash(plan: TeachingPlan | Mapping[str, Any]) -> str:
    """Hash validated pedagogical content, excluding code-owned identity metadata.

    Serializing every current model field by default makes future teacher-visible
    TeachingPlan fields part of identity automatically. Ordered pedagogical
    arrays retain their order; object keys are serialized deterministically.
    """
    validated = plan if isinstance(plan, TeachingPlan) else TeachingPlan.model_validate(dict(plan))
    payload = validated.model_dump(mode="json", exclude=_NON_PEDAGOGICAL_FIELDS)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["teaching_plan_content_hash"]
