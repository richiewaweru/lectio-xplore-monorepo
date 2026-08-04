"""Prompt overlay loader.

Resolves the "effective" text of a named system prompt for a given teacher:
either their saved overlay (`prompt_overrides` table) or the default prompt
body shipped under `backend/resources/prompts/`.

See `handoff/RESTRUCTURE_HANDOFF.md` §4 (Workstream C) for the design this
implements. The manifest and default prompt files may be authored by a
parallel workstream; this module only assumes the documented shape:

    backend/resources/prompts/manifest.yaml
    backend/resources/prompts/<file>   # one per manifest entry

manifest.yaml shape:

    prompts:
      - id: section-writer       # stable prompt id, e.g. used in URLs
        file: section-writer.md  # filename under this directory
        stage_label: "Writes the lesson content"
        editable: true           # false => overlay is never read/written
        version: 1               # bumped by hand when the default changes
"""

from __future__ import annotations

import hashlib
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import PromptOverrideModel

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "resources" / "prompts"
_MANIFEST_PATH = _PROMPTS_DIR / "manifest.yaml"

# Per-request/task cache of resolved prompt bodies (id -> text). Set via
# `bind_prompt_cache` so sync prompt builders can honour teacher overlays.
_prompt_cache: ContextVar[dict[str, str] | None] = ContextVar(
    "prompt_overlay_cache", default=None
)


class PromptNotFoundError(KeyError):
    """Raised when a prompt id is not present in the manifest."""


class PromptLockedError(PermissionError):
    """Raised when attempting to read/write an overlay for a locked prompt."""


@dataclass(frozen=True)
class PromptManifestEntry:
    id: str
    file: str
    stage_label: str
    editable: bool
    version: int = 1

    @property
    def path(self) -> Path:
        return _PROMPTS_DIR / self.file


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_prompt(text: str) -> str:
    """SHA-256 hex digest of a prompt's effective text.

    Used both as a change-detection signal (tests assert it changes when an
    overlay changes) and, per the restructure handoff, to be stamped onto
    `GenerationModel.report_json["prompt_hashes"]` so a generation can be
    traced back to the exact prompt text that produced it.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_manifest_entries(raw: Any) -> list[PromptManifestEntry]:
    entries_raw = raw.get("prompts") if isinstance(raw, dict) else None
    if not isinstance(entries_raw, list):
        return []
    entries: list[PromptManifestEntry] = []
    for item in entries_raw:
        if not isinstance(item, dict):
            continue
        prompt_id = item.get("id")
        file_name = item.get("file")
        if not prompt_id or not file_name:
            continue
        try:
            version = int(item.get("version", 1))
        except (TypeError, ValueError):
            version = 1
        entries.append(
            PromptManifestEntry(
                id=str(prompt_id),
                file=str(file_name),
                stage_label=str(item.get("stage_label") or prompt_id),
                editable=bool(item.get("editable", True)),
                version=version,
            )
        )
    return entries


def _load_manifest_raw() -> dict:
    if not _MANIFEST_PATH.exists():
        return {"prompts": []}
    with _MANIFEST_PATH.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    return loaded if isinstance(loaded, dict) else {"prompts": []}


def load_manifest() -> list[PromptManifestEntry]:
    """Parse `manifest.yaml`. Returns an empty list if the file is missing.

    Missing manifest/files can legitimately happen while the prompt
    packaging workstream is still landing its files; callers that need a
    populated manifest should treat an empty list as "not ready yet" rather
    than crash the process.
    """
    return _parse_manifest_entries(_load_manifest_raw())


def list_manifest() -> list[PromptManifestEntry]:
    """Public accessor for the prompts API layer."""
    return load_manifest()


def get_manifest_entry(prompt_id: str) -> PromptManifestEntry:
    for entry in load_manifest():
        if entry.id == prompt_id:
            return entry
    raise PromptNotFoundError(prompt_id)


def get_default_prompt(prompt_id: str) -> str:
    """Read the default (file-backed) prompt text for `prompt_id`.

    Raises `PromptNotFoundError` if the id isn't in the manifest, or
    `FileNotFoundError` with a clear message if the manifest references a
    file that hasn't been added yet (expected while extraction work under
    Workstream C is still in flight).
    """
    entry = get_manifest_entry(prompt_id)
    if not entry.path.exists():
        raise FileNotFoundError(
            f"Prompt file missing for '{prompt_id}': expected at {entry.path}. "
            "manifest.yaml declares this prompt but its default text file has "
            "not been added yet under backend/resources/prompts/."
        )
    return entry.path.read_text(encoding="utf-8")


def effective_prompt_text(prompt_id: str) -> str:
    """Sync access to the effective prompt body for builders.

    Prefers the bound per-user cache (overlays already resolved). Falls back
    to the default file text when no cache is bound.
    """
    cache = _prompt_cache.get()
    if cache is not None and prompt_id in cache:
        return cache[prompt_id]
    return get_default_prompt(prompt_id)


def bind_prompt_cache(cache: dict[str, str] | None):
    """Bind (or clear) the process ContextVar cache. Returns a reset token."""
    return _prompt_cache.set(cache)


def reset_prompt_cache(token) -> None:  # noqa: ANN001
    _prompt_cache.reset(token)


async def resolve_all_prompts(
    user_id: str, session: AsyncSession
) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve every manifest prompt for `user_id`.

    Returns `(texts_by_id, hashes_by_id)`.
    """
    texts: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for entry in list_manifest():
        text, digest = await resolve_prompt(entry.id, user_id, session)
        texts[entry.id] = text
        hashes[entry.id] = digest
    return texts, hashes


async def _get_override_row(
    session: AsyncSession, *, user_id: str, prompt_id: str
) -> PromptOverrideModel | None:
    result = await session.execute(
        select(PromptOverrideModel).where(
            PromptOverrideModel.user_id == user_id,
            PromptOverrideModel.prompt_id == prompt_id,
        )
    )
    return result.scalar_one_or_none()


async def resolve_prompt(
    prompt_id: str, user_id: str, session: AsyncSession
) -> tuple[str, str]:
    """Return `(effective_text, sha256_hex)` for `prompt_id` and `user_id`.

    Locked prompts (`editable: false`) never consult overlays, even if a
    stale overlay row exists for that user/prompt pair.
    """
    entry = get_manifest_entry(prompt_id)
    if entry.editable:
        override = await _get_override_row(session, user_id=user_id, prompt_id=prompt_id)
        if override is not None:
            text = override.text
            return text, hash_prompt(text)
    text = get_default_prompt(prompt_id)
    return text, hash_prompt(text)


async def is_modified(prompt_id: str, user_id: str, session: AsyncSession) -> bool:
    """Whether `user_id` has an active overlay for `prompt_id`.

    Always `False` for locked prompts, regardless of any stale overlay row.
    """
    entry = get_manifest_entry(prompt_id)
    if not entry.editable:
        return False
    override = await _get_override_row(session, user_id=user_id, prompt_id=prompt_id)
    return override is not None


async def save_override(
    prompt_id: str, user_id: str, text: str, session: AsyncSession
) -> PromptOverrideModel:
    """Upsert the overlay row for `user_id`/`prompt_id`.

    Raises `PromptLockedError` for locked prompts.
    """
    entry = get_manifest_entry(prompt_id)
    if not entry.editable:
        raise PromptLockedError(prompt_id)
    override = await _get_override_row(session, user_id=user_id, prompt_id=prompt_id)
    now = _utcnow()
    if override is None:
        override = PromptOverrideModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            prompt_id=prompt_id,
            text=text,
            updated_at=now,
        )
        session.add(override)
    else:
        override.text = text
        override.updated_at = now
    await session.commit()
    return override


async def delete_override(prompt_id: str, user_id: str, session: AsyncSession) -> bool:
    """Delete the overlay row for `user_id`/`prompt_id`, if any.

    Returns whether a row was deleted. No-ops (and does not raise) for
    locked prompts, since they cannot have an overlay in the first place.
    """
    override = await _get_override_row(session, user_id=user_id, prompt_id=prompt_id)
    if override is None:
        return False
    await session.delete(override)
    await session.commit()
    return True


__all__ = [
    "PromptLockedError",
    "PromptManifestEntry",
    "PromptNotFoundError",
    "delete_override",
    "get_default_prompt",
    "get_manifest_entry",
    "hash_prompt",
    "is_modified",
    "list_manifest",
    "load_manifest",
    "resolve_prompt",
    "save_override",
]
