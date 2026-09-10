"""Phase G — retained / deleted Learn interaction registry admission."""

from __future__ import annotations

from learn.interactions.registry import (
    DELETED_INTERACTIONS,
    RETAINED_INTERACTIONS,
    RETIRED_ORDINARY_CONTENT_IDS,
)
from learn.resources.native_policy import (
    default_learn_policy,
    offered_interaction_ids,
)


def test_retained_interactions_match_keep_set() -> None:
    assert RETAINED_INTERACTIONS == frozenset(
        {
            "choice",
            "multi-select",
            "fill-blank",
            "classify",
            "match-pairs",
            "sequence",
            "numeric",
            "short-response",
        }
    )


def test_deleted_interactions_match_delete_set() -> None:
    assert DELETED_INTERACTIONS == frozenset(
        {
            "image-hotspot",
            "drag-label",
            "image-choice",
            "image-block",
            "video-embed",
        }
    )
    assert RETAINED_INTERACTIONS.isdisjoint(DELETED_INTERACTIONS)


def test_policy_offers_only_retained_interactions() -> None:
    policy = default_learn_policy()
    offered = set(policy["offered_interactions"])
    assert offered == set(RETAINED_INTERACTIONS)
    assert offered_interaction_ids(policy) == RETAINED_INTERACTIONS
    assert DELETED_INTERACTIONS.isdisjoint(offered)
    assert DELETED_INTERACTIONS.isdisjoint(offered_interaction_ids(policy))


def test_deleted_kinds_not_in_offered_interactions() -> None:
    offered = set(default_learn_policy()["offered_interactions"])
    for kind in DELETED_INTERACTIONS:
        assert kind not in offered


def test_denied_capabilities_cover_deleted_and_retired_content() -> None:
    denied = set(default_learn_policy()["denied_capabilities"])
    assert DELETED_INTERACTIONS <= denied
    assert RETIRED_ORDINARY_CONTENT_IDS <= denied
    # Ordinary content is not policy-admitted; document realizer owns that path.
    assert default_learn_policy()["offered_content"] == []
