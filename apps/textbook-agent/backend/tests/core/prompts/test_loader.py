from __future__ import annotations

import pytest

from core.prompts import loader


EDITABLE_PROMPT_ID = "section-writer"
LOCKED_PROMPT_ID = "quiz-items"
USER_ID = "prompt-loader-user"


def test_manifest_has_expected_editable_and_locked_entries() -> None:
    entries = {entry.id: entry for entry in loader.load_manifest()}

    assert entries[EDITABLE_PROMPT_ID].editable is True
    assert entries[LOCKED_PROMPT_ID].editable is False


async def test_overlay_round_trip_save_resolve_delete_default(db_session_factory) -> None:
    async with db_session_factory() as session:
        default_text, default_hash = await loader.resolve_prompt(
            EDITABLE_PROMPT_ID, USER_ID, session
        )
        assert default_hash == loader.hash_prompt(default_text)
        assert await loader.is_modified(EDITABLE_PROMPT_ID, USER_ID, session) is False

        overlay_text = "Custom section writer instructions for this teacher."
        await loader.save_override(EDITABLE_PROMPT_ID, USER_ID, overlay_text, session)

        resolved_text, resolved_hash = await loader.resolve_prompt(
            EDITABLE_PROMPT_ID, USER_ID, session
        )
        assert resolved_text == overlay_text
        assert resolved_hash == loader.hash_prompt(overlay_text)
        assert resolved_hash != default_hash
        assert await loader.is_modified(EDITABLE_PROMPT_ID, USER_ID, session) is True

        deleted = await loader.delete_override(EDITABLE_PROMPT_ID, USER_ID, session)
        assert deleted is True

        restored_text, restored_hash = await loader.resolve_prompt(
            EDITABLE_PROMPT_ID, USER_ID, session
        )
        assert restored_text == default_text
        assert restored_hash == default_hash
        assert await loader.is_modified(EDITABLE_PROMPT_ID, USER_ID, session) is False

        # Deleting again (no overlay left) is a no-op, not an error.
        assert await loader.delete_override(EDITABLE_PROMPT_ID, USER_ID, session) is False


async def test_locked_prompt_rejects_override(db_session_factory) -> None:
    async with db_session_factory() as session:
        with pytest.raises(loader.PromptLockedError):
            await loader.save_override(LOCKED_PROMPT_ID, USER_ID, "nope", session)

        # Confirm no row was left behind and resolution still serves the default.
        assert await loader.is_modified(LOCKED_PROMPT_ID, USER_ID, session) is False
        text, prompt_hash = await loader.resolve_prompt(LOCKED_PROMPT_ID, USER_ID, session)
        assert prompt_hash == loader.hash_prompt(text)


async def test_locked_prompt_ignores_stale_overlay_row(db_session_factory) -> None:
    """A locked prompt must never read an overlay, even if one exists in the DB."""
    from core.database.models import PromptOverrideModel

    async with db_session_factory() as session:
        session.add(
            PromptOverrideModel(
                id="stale-locked-override",
                user_id=USER_ID,
                prompt_id=LOCKED_PROMPT_ID,
                text="this should never be served",
                updated_at=loader._utcnow(),
            )
        )
        await session.commit()

        text, prompt_hash = await loader.resolve_prompt(LOCKED_PROMPT_ID, USER_ID, session)
        default_text = loader.get_default_prompt(LOCKED_PROMPT_ID)
        assert text == default_text
        assert prompt_hash == loader.hash_prompt(default_text)
        assert await loader.is_modified(LOCKED_PROMPT_ID, USER_ID, session) is False


async def test_hash_changes_when_overlay_changes(db_session_factory) -> None:
    async with db_session_factory() as session:
        await loader.save_override(EDITABLE_PROMPT_ID, USER_ID, "version one", session)
        _, hash_one = await loader.resolve_prompt(EDITABLE_PROMPT_ID, USER_ID, session)

        await loader.save_override(EDITABLE_PROMPT_ID, USER_ID, "version two", session)
        _, hash_two = await loader.resolve_prompt(EDITABLE_PROMPT_ID, USER_ID, session)

        assert hash_one != hash_two
        assert hash_one == loader.hash_prompt("version one")
        assert hash_two == loader.hash_prompt("version two")


def test_unknown_prompt_id_raises_not_found() -> None:
    with pytest.raises(loader.PromptNotFoundError):
        loader.get_manifest_entry("does-not-exist")
