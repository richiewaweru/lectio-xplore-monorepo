from __future__ import annotations

from collections.abc import Iterable

from .models import LessonSourcebook, TeachingContentBinding


def build_content_bindings(
    plan: object,
    sourcebook: LessonSourcebook,
    *,
    tasks: Iterable[object] = (),
) -> list[TeachingContentBinding]:
    """Create immutable post-plan bindings without mutating the Teaching Plan."""
    plan_id = str(getattr(plan, "teaching_plan_id", None) or "teaching-plan")
    revision = int(getattr(plan, "revision", None) or 1)
    plan_hash = str(getattr(plan, "preparation_hash", None) or sourcebook.teaching_plan_hash)
    task_by_block = {
        str(getattr(task, "teaching_block_id", "")): str(getattr(task, "id", ""))
        for task in tasks
    }
    bindings: list[TeachingContentBinding] = []
    for section in getattr(plan, "sections", ()):
        for block in getattr(section, "blocks", ()):
            bindings.append(
                TeachingContentBinding(
                    teaching_plan_id=plan_id,
                    teaching_plan_revision=revision,
                    teaching_plan_hash=plan_hash,
                    teaching_block_id=block.id,
                    sourcebook_refs=list(getattr(block, "sourcebook_refs", ()) or ()),
                    shared_task_id=task_by_block.get(block.id),
                )
            )
    return bindings


def validate_sourcebook(
    sourcebook: LessonSourcebook,
    *,
    bindings: Iterable[TeachingContentBinding] = (),
) -> list[str]:
    errors: list[str] = []
    ids = [entry.id for entry in sourcebook.entries]
    if len(ids) != len(set(ids)):
        errors.append("sourcebook entry ids must be unique")
    entry_ids = set(ids)
    seen_blocks: set[str] = set()
    for binding in bindings:
        if binding.teaching_plan_id != sourcebook.teaching_plan_id:
            errors.append(f"binding {binding.teaching_block_id!r} has the wrong teaching_plan_id")
        if binding.teaching_plan_revision != sourcebook.teaching_plan_revision:
            errors.append(f"binding {binding.teaching_block_id!r} has the wrong teaching_plan_revision")
        if binding.teaching_plan_hash != sourcebook.teaching_plan_hash:
            errors.append(f"binding {binding.teaching_block_id!r} has the wrong teaching_plan_hash")
        if binding.teaching_block_id in seen_blocks:
            errors.append(f"duplicate binding for teaching block {binding.teaching_block_id!r}")
        seen_blocks.add(binding.teaching_block_id)
        missing = sorted(set(binding.sourcebook_refs) - entry_ids)
        if missing:
            errors.append(f"binding {binding.teaching_block_id!r} references unknown entries {missing}")
    for entry in sourcebook.entries:
        if not entry.provenance_refs:
            errors.append(f"sourcebook entry {entry.id!r} must have provenance_refs")
    return errors


__all__ = ["build_content_bindings", "validate_sourcebook"]
