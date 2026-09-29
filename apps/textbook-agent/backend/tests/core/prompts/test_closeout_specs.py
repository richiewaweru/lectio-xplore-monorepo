from __future__ import annotations

from core.prompts import loader

CLOSEOUT_IDS = (
    "learner-action-policy",
    "figure-authoring",
    "print-realization",
)


def test_closeout_prompts_are_manifest_backed_and_locked() -> None:
    entries = {entry.id: entry for entry in loader.load_manifest()}
    for prompt_id in CLOSEOUT_IDS:
        assert prompt_id in entries, prompt_id
        assert entries[prompt_id].editable is False
        text = loader.get_default_prompt(prompt_id)
        assert text.strip()
        assert loader.hash_prompt(text) == loader.closeout_prompt_hashes()[prompt_id]


def test_markdown_default_change_alters_effective_hash_without_python_logic() -> None:
    original = loader.get_default_prompt("figure-authoring")
    original_hash = loader.hash_prompt(original)
    mutated = original + "\n\nHash-proof mutation for closeout Phase A.\n"
    assert loader.hash_prompt(mutated) != original_hash
    assert loader.hash_prompt(original) == original_hash


async def test_closeout_prompts_reject_teacher_overlays(db_session_factory) -> None:
    async with db_session_factory() as session:
        with __import__("pytest").raises(loader.PromptLockedError):
            await loader.save_override("figure-authoring", "closeout-user", "nope", session)
