from __future__ import annotations

from dataclasses import dataclass
import hashlib


class ObjectiveOwnershipError(ValueError):
    pass


def hash_path_objective(objective: str) -> str:
    """Hash the exact approved path objective; normalization would hide rewriting."""
    if not objective:
        raise ValueError("Path objective must not be empty")
    return hashlib.sha256(objective.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ObjectiveOwnership:
    objective: str
    objective_hash: str

    @classmethod
    def from_path_objective(cls, objective: str) -> ObjectiveOwnership:
        return cls(objective=objective, objective_hash=hash_path_objective(objective))

    def verify_generated_objective(self, generated_objective: str) -> None:
        generated_hash = hash_path_objective(generated_objective)
        if generated_hash != self.objective_hash:
            raise ObjectiveOwnershipError(
                "Generated lesson objective does not match the approved path objective"
            )
