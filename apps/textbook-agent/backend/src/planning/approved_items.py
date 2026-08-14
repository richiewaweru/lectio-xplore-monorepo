"""Typed approved-item loading from PackItemModel for whole-lesson planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import ConceptCardModel, PackItemModel


class ItemPoolEmptyError(ValueError):
    """Raised when a proof lesson has no approved non-stale items."""

    code = "ITEM_POOL_EMPTY"

    def __init__(self, *, card_id: str, pack_id: str | None = None) -> None:
        self.card_id = card_id
        self.pack_id = pack_id
        detail = f"card_id={card_id!r}"
        if pack_id:
            detail += f", pack_id={pack_id!r}"
        super().__init__(f"ITEM_POOL_EMPTY: no approved items for {detail}")


@dataclass(frozen=True)
class ApprovedItemRecord:
    id: str
    card_id: str
    stem: str
    options: tuple[dict[str, object], ...]
    correct_key: str
    diagnoses: dict[str, object]

    @property
    def item_kind(self) -> Literal["multiple_choice", "open_response"]:
        """Derive the assessment form from the canonical stored metadata."""
        return approved_item_kind(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "card_id": self.card_id,
            "stem": self.stem,
            "prompt": self.stem,
            "options": [dict(option) for option in self.options],
            "correct_key": self.correct_key,
            "diagnoses": dict(self.diagnoses),
        }


def approved_item_kind(
    item: Any,
) -> Literal["multiple_choice", "open_response"]:
    """Classify an approved item without inventing a second ownership field.

    ``PackItemModel.options`` is the available canonical discriminator: a
    non-empty option set is multiple choice; an empty set is open response.
    The helper also accepts ``ApprovedItemRef`` so persisted lesson packets can
    enforce the same rule during teaching/form validation.
    """
    options = getattr(item, "options", None)
    if options is None and isinstance(item, dict):
        options = item.get("options")
    return "multiple_choice" if options else "open_response"


async def load_approved_item_records(
    *,
    session: AsyncSession,
    path_lesson: Any | None = None,
    concept_card: ConceptCardModel,
    require_nonempty: bool = False,
) -> tuple[ApprovedItemRecord, ...]:
    """Load non-stale PackItemModel rows for the concept card (and pack when set).

    ``path_lesson`` is accepted for call-site compatibility with the proposal
    signature; filtering uses ``concept_card.pack_id`` and ``concept_card.id``.
    """
    del path_lesson  # reserved; card/pack identity comes from concept_card
    pack_id = concept_card.pack_id
    card_id = concept_card.id

    stmt = select(PackItemModel).where(
        PackItemModel.card_id == card_id,
        PackItemModel.stale.is_(False),
    )
    if pack_id:
        stmt = stmt.where(PackItemModel.pack_id == pack_id)
    stmt = stmt.order_by(PackItemModel.id.asc())

    rows = (await session.execute(stmt)).scalars().all()
    records: list[ApprovedItemRecord] = []
    for row in rows:
        options_raw = row.options if isinstance(row.options, list) else []
        options: list[dict[str, object]] = []
        for option in options_raw:
            if isinstance(option, dict):
                options.append(dict(option))
        diagnoses = row.diagnoses if isinstance(row.diagnoses, dict) else {}
        records.append(
            ApprovedItemRecord(
                id=str(row.id),
                card_id=str(row.card_id),
                stem=str(row.stem),
                options=tuple(options),
                correct_key=str(row.correct_key),
                diagnoses=dict(diagnoses),
            )
        )

    if require_nonempty and not records:
        raise ItemPoolEmptyError(card_id=card_id, pack_id=pack_id)

    return tuple(records)


def approved_item_ids(records: tuple[ApprovedItemRecord, ...]) -> tuple[str, ...]:
    return tuple(record.id for record in records)


def approved_items_as_writer_records(
    records: tuple[ApprovedItemRecord, ...],
) -> tuple[dict[str, Any], ...]:
    return tuple(record.to_dict() for record in records)


def approved_items_payload(records: tuple[ApprovedItemRecord, ...]) -> list[dict[str, Any]]:
    return [record.to_dict() for record in records]
