from __future__ import annotations

import pytest

from v3_blueprint.planning.objective_ownership import (
    ObjectiveOwnership,
    ObjectiveOwnershipError,
    hash_path_objective,
)


def test_path_objective_hash_is_exact_and_reproducible() -> None:
    objective = "Explain why light is required for photosynthesis."

    ownership = ObjectiveOwnership.from_path_objective(objective)

    assert ownership.objective_hash == hash_path_objective(objective)
    ownership.verify_generated_objective(objective)


def test_objective_ownership_rejects_even_silent_whitespace_rewriting() -> None:
    ownership = ObjectiveOwnership.from_path_objective(
        "Explain why light is required for photosynthesis."
    )

    with pytest.raises(ObjectiveOwnershipError, match="approved path objective"):
        ownership.verify_generated_objective(
            "Explain why light is required for photosynthesis. "
        )
