"""Policy cleanup v4 - G19 dual-path policy identity."""

from __future__ import annotations

import pytest
from tests.remaining_fixes.r04_fixtures import (
    build_envelope_closed_production_document,
    install_api_overrides,
    publish_lesson,
    r04_client,
    seed_r04_user,
)


@pytest.mark.asyncio
async def test_g19_saved_learn_document_retains_policy_identity(
    db_session_factory,
) -> None:
    """Closed Learn production persists policy on interaction provenance; reload via publish."""
    install_api_overrides(db_session_factory)
    await seed_r04_user(db_session_factory)
    document = build_envelope_closed_production_document(title="Policy G19")
    # Stamp policy on any short-response or first interaction
    for block in document["blocks"].values():
        contract = block.get("learn_interaction")
        if isinstance(contract, dict):
            contract.setdefault("provenance", {})
            contract["provenance"]["policy"] = {
                "policy_version": "1.0.0",
                "effective_knowledge_policy": "supplied_preferred",
                "effective_assessment_policy": "automatic_preferred",
                "definition_hash": contract.get("provenance", {}).get("definition_hash"),
                "input_revision": "prep-rev-g19",
            }
            break

    async with await r04_client() as client:
        _lesson_id, release_id = await publish_lesson(client, document, title="Policy G19")
        reloaded = await client.get(f"/api/v1/learn/releases/{release_id}")
        assert reloaded.status_code == 200
        found = False
        for block in reloaded.json()["document"]["blocks"].values():
            contract = block.get("learn_interaction")
            if isinstance(contract, dict) and contract.get("provenance", {}).get("policy"):
                policy = contract["provenance"]["policy"]
                assert policy["policy_version"] == "1.0.0"
                assert policy["effective_knowledge_policy"] == "supplied_preferred"
                assert policy.get("input_revision") == "prep-rev-g19"
                found = True
                break
        assert found

    from app import app

    app.dependency_overrides.clear()
