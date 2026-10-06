"""Development fixtures for exercising the shared lesson contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document.shared_lesson.models import SharedLessonDocument, build_shared_lesson_document


_FIXTURE_DIR = Path("fixtures/shared_lesson")
_LEGACY_SOURCE = Path("docs/doc36-presentation/evidence/legacy-shared-source.json")


def _find_upwards(relative: Path) -> Path:
    """Resolve a development fixture path lazily, at any checkout depth.

    Fixtures are not packaged into deployed images, so this must never run at
    import time: a missing fixture only fails the call that asked for it.
    """

    for ancestor in Path(__file__).resolve().parents:
        candidate = ancestor / relative
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"{relative.as_posix()} not found: shared lesson fixtures are "
        "development-only and not packaged in this build"
    )


_STRUCTURAL_KEYS = {
    "schema_version",
    "content_hash",
    "id",
    "kind",
    "type",
    "teaching_block_id",
    "task_spec_id",
    "teaching_plan_id",
    "teaching_plan_revision",
    "teaching_plan_hash",
    "revision",
    "position",
    "mode",
    "action",
    "role",
    "difficulty",
    "tone",
    "variant",
    "asset_id",
    "source_ids",
    "source_hashes",
    "approved_source_ids",
    "correct_option_id",
    "correct_option_ids",
    "correct_key",
    "correct_keys",
    "created_at",
}


def _double_learner_text(value: Any, key: str | None = None) -> Any:
    if isinstance(value, str):
        return value if key in _STRUCTURAL_KEYS else f"{value} {value}"
    if isinstance(value, list):
        return [_double_learner_text(item, key) for item in value]
    if isinstance(value, dict):
        return {item_key: _double_learner_text(item, item_key) for item_key, item in value.items()}
    return value


def load_shared_lesson_fixture(name: str = "golden") -> SharedLessonDocument:
    """Load and hash a checked-in fixture; only development data is supported."""

    if name == "legacy":
        # The legacy artifact is loaded with its stored hash intact. It is
        # deliberately never rebuilt through build_shared_lesson_document.
        return SharedLessonDocument.model_validate(
            json.loads(_find_upwards(_LEGACY_SOURCE).read_text(encoding="utf-8"))
        )
    if name == "overlong":
        payload = _double_learner_text(
            json.loads(_find_upwards(_FIXTURE_DIR / "golden.json").read_text(encoding="utf-8"))
        )
    else:
        path = _find_upwards(_FIXTURE_DIR / f"{name}.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
    return build_shared_lesson_document(payload)


__all__ = ["load_shared_lesson_fixture"]
