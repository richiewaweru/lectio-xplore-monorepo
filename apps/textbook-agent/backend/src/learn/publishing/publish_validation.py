"""Full Learn publish validation (P06).

Supports legacy LessonDocument v1 (sections/blocks) and LearnDocument v2
(ordered nodes). Validates interaction contracts and dangling refs before
snapshotting.
"""

from __future__ import annotations

from typing import Any, Mapping

from learn.contracts.lesson_document import validate_learn_document
from learn.generation.interaction_writer import validate_interaction_contract

INTERACTION_COMPONENT_PREFIX = "learn-interaction:"


class PublishValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init("; ".join(self.errors) if self.errors else "publish validation failed")


def _is_interaction_block(block: Mapping[str, Any]) -> bool:
    if isinstance(block.get("learn_interaction"), dict) or isinstance(block.get("interaction"), dict):
        return True
    component_id = str(block.get("component_id") or "")
    return component_id.startswith(INTERACTION_COMPONENT_PREFIX)


def _collect_v2_publish_errors(document: Mapping[str, Any]) -> list[str]:
    """LearnDocument v2: node schema + light interaction config integrity."""
    errors = validate_learn_document(document)
    nodes = document.get("nodes")
    if not isinstance(nodes, list):
        return errors

    for index, raw in enumerate(nodes):
        if not isinstance(raw, dict) or raw.get("kind") != "interaction":
            continue
        config = raw.get("config") if isinstance(raw.get("config"), dict) else {}
        if raw.get("interaction_type") != "sequence":
            continue
        order = [str(x) for x in (config.get("order") or [])]
        items = config.get("items") if isinstance(config.get("items"), list) else []
        item_ids = {str(i.get("id")) for i in items if isinstance(i, dict)}
        for oid in order:
            if items and oid not in item_ids:
                errors.append(
                    f"nodes[{index}]: dangling sequence order id {oid!r} not in items"
                )
    return errors


def _collect_v1_publish_errors(document: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(document.get("version"), int):
        errors.append("LessonDocument.version must be an integer")
    if not isinstance(document.get("id"), str) or not str(document.get("id") or "").strip():
        errors.append("LessonDocument.id must be a non-empty string")
    sections = document.get("sections")
    blocks = document.get("blocks")
    media = document.get("media")
    if not isinstance(sections, list):
        errors.append("LessonDocument.sections must be a list")
        return errors
    if not isinstance(blocks, dict):
        errors.append("LessonDocument.blocks must be an object")
        return errors
    if media is None or not isinstance(media, dict):
        errors.append("LessonDocument.media must be an object")

    seen_block_ids: set[str] = set()
    for section in sections:
        if not isinstance(section, dict):
            errors.append("section entries must be objects")
            continue
        sid = section.get("id")
        if not isinstance(sid, str) or not sid.strip():
            errors.append("section.id must be a non-empty string")
        for bid in section.get("block_ids") or []:
            bid_s = str(bid)
            if bid_s in seen_block_ids:
                errors.append(f"duplicate block_id in document order: {bid_s}")
            seen_block_ids.add(bid_s)
            block = blocks.get(bid_s)
            if not isinstance(block, dict):
                errors.append(f"section {sid!r} references missing block {bid_s!r}")
                continue
            if block.get("id") not in (None, bid_s) and str(block.get("id")) != bid_s:
                errors.append(f"block map key {bid_s!r} does not match block.id {block.get('id')!r}")

            contract = block.get("learn_interaction") or block.get("interaction")
            if _is_interaction_block(block):
                if not isinstance(contract, dict):
                    errors.append(f"interaction block {bid_s!r} missing learn_interaction contract")
                else:
                    for msg in validate_interaction_contract(contract):
                        errors.append(f"block {bid_s!r}: {msg}")
                    if contract.get("kind") == "sequence":
                        config = (
                            contract.get("config")
                            if isinstance(contract.get("config"), dict)
                            else {}
                        )
                        order = [str(x) for x in (config.get("order") or [])]
                        items = config.get("items") if isinstance(config.get("items"), list) else []
                        item_ids = {str(i.get("id")) for i in items if isinstance(i, dict)}
                        for oid in order:
                            if items and oid not in item_ids:
                                errors.append(
                                    f"block {bid_s!r}: dangling sequence order id {oid!r} not in items"
                                )

            for ref in block.get("concept_refs") or []:
                if not isinstance(ref, dict) or not str(ref.get("concept_id") or "").strip():
                    errors.append(f"block {bid_s!r}: concept_refs require concept_id")

            content = block.get("content") if isinstance(block.get("content"), dict) else {}
            for key in ("media_id", "asset_id", "image_id"):
                mid = content.get(key)
                if isinstance(mid, str) and mid and mid not in media:
                    errors.append(f"block {bid_s!r}: dangling media ref {mid!r} for {key}")

    for section in sections:
        if not isinstance(section, dict):
            continue
        for ref in section.get("concept_refs") or []:
            if not isinstance(ref, dict) or not str(ref.get("concept_id") or "").strip():
                errors.append(f"section {section.get('id')!r}: concept_refs require concept_id")

    return errors


def collect_publish_validation_errors(document: Mapping[str, Any]) -> list[str]:
    version = document.get("version")
    if version == 2:
        return _collect_v2_publish_errors(document)
    return _collect_v1_publish_errors(document)


def validate_publishable_lesson_document(document: Mapping[str, Any]) -> None:
    errors = collect_publish_validation_errors(document)
    if errors:
        raise PublishValidationError(errors)
