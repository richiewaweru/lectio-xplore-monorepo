"""Advisory Teaching Plan flags live beside the plan, never inside its hash."""

from __future__ import annotations

import pytest

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.revisions import TeachingRevisionStore
from document.shared_lesson.approved_source import load_current_approved_teaching_plan_source
from tests.document.test_shared_lesson_approved_source import _plan, _prepared

FLAGS = [
    {
        "code": "assessment_item_reused",
        "severity": "warning",
        "source": "reviewer",
        "message": "Worked example reuses the approved check scenario.",
        "section_ids": ["orient"],
        "block_ids": ["orient-b1"],
        "repair_instruction": "Use a different scenario.",
    }
]


def test_flags_are_recorded_on_the_revision_without_changing_the_hash() -> None:
    plan = _plan()
    flagged: dict = {}
    plain: dict = {}
    flagged_record = TeachingRevisionStore(flagged).record_draft(
        plan, preparation_hash="preparation-hash", revision=1, flags=FLAGS
    )
    plain_record = TeachingRevisionStore(plain).record_draft(
        plan, preparation_hash="preparation-hash", revision=1
    )

    assert flagged_record.flags == FLAGS
    assert plain_record.flags == []
    assert flagged_record.content_hash == plain_record.content_hash
    assert flagged_record.content_hash == teaching_plan_content_hash(flagged_record.plan)
    assert "flags" not in flagged_record.plan
    approved = TeachingRevisionStore(flagged).approve(
        expected_revision=1, expected_content_hash=flagged_record.content_hash
    )
    assert approved.flags == FLAGS


@pytest.mark.asyncio
async def test_flagged_plan_still_loads_as_current_approved_source(
    db_session, monkeypatch
) -> None:
    original = TeachingRevisionStore.record_draft

    def _with_flags(self, plan, **kwargs):
        return original(self, plan, flags=FLAGS, **kwargs)

    monkeypatch.setattr(TeachingRevisionStore, "record_draft", _with_flags)
    generation, lesson, _provenance, expected = await _prepared(db_session)

    loaded = await load_current_approved_teaching_plan_source(
        session=db_session,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
    )

    assert loaded.content_hash == expected.content_hash
    assert loaded.revision_record.flags == FLAGS
