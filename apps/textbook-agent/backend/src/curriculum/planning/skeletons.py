from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

KnowledgeType = Literal["procedural", "conceptual", "factual", "evaluative"]
LessonMode = Literal[
    "first_exposure", "consolidation", "repair", "retrieval", "transfer"
]
GroupProfile = Literal["support", "core", "extension"]

_PROFILE_SUPPORT_LEVEL = {"support": "high", "core": "medium", "extension": "low"}


class SkeletonCatalogError(ValueError):
    pass


_REQUIRED_KNOWLEDGE_TYPES = ("procedural", "conceptual", "factual", "evaluative")


@dataclass(frozen=True)
class KnowledgeTypeGuidance:
    knowledge_type: str
    teacher_label: str
    definition: str
    demands: tuple[str, ...]
    contraindicated: tuple[str, ...]


class DeviationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    skeleton_id: str
    operation: Literal["insert", "remove", "replace", "reorder"]
    target_slot: str
    replacement_slot: str | None = None
    reason: str = Field(min_length=1)
    requested_by: Literal["model", "teacher"]
    status: Literal["pending_teacher", "approved", "rejected"] = "pending_teacher"

    @model_validator(mode="after")
    def validate_operation(self) -> DeviationRequest:
        if self.operation in {"remove", "replace", "reorder"} and self.target_slot == "check":
            raise ValueError("The locked check slot cannot be removed, replaced, or reordered")
        if self.operation in {"insert", "replace", "reorder"} and not self.replacement_slot:
            raise ValueError(f"operation={self.operation} requires replacement_slot")
        if self.operation in {"insert", "replace"} and self.replacement_slot == "check":
            raise ValueError("The locked check slot cannot be inserted or duplicated")
        return self


class SkeletonPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: str = Field(min_length=1)
    lesson_mode: LessonMode
    misconception_count: int = Field(ge=0, le=3)
    group_profiles: list[GroupProfile]
    approved_deviations: list[DeviationRequest] = Field(default_factory=list)


class SkeletonSlotPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str
    role: str
    purpose: str
    locked: bool = False


class SkeletonDiffEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["add", "remove", "replace", "repeat", "reorder", "set_flag"]
    slot_id: str
    replacement_slot: str | None = None
    toggle_id: str
    explanation: str


class SkeletonBlockingIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal["variant_slot_overflow", "skeleton_conflict"]
    message: str
    toggle_id: str


class SkeletonVariantPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_profile: GroupProfile
    support_level: str
    slots: list[SkeletonSlotPreview]
    toggles_applied: list[str]
    warnings: list[str]
    structural_diff: list[SkeletonDiffEntry] = Field(default_factory=list)
    blocking_issues: list[SkeletonBlockingIssue] = Field(default_factory=list)


class SkeletonPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: str
    knowledge_type: KnowledgeType
    knowledge_type_source: Literal["deterministic_preview", "provided"]
    skeleton_id: str
    skeleton_version: int
    variants: list[SkeletonVariantPreview]


class SkeletonCatalog:
    def __init__(self, data: dict) -> None:
        self.data = deepcopy(data)
        self.version = self._require_positive_int("version")
        self.max_slots = self._require_positive_int("max_slots")
        self.slots = self._require_mapping("slots")
        raw_skeletons = self.data.get("skeletons")
        if not isinstance(raw_skeletons, list) or not raw_skeletons:
            raise SkeletonCatalogError("skeletons must be a non-empty list")
        self.skeletons = {
            str(item.get("id")): item
            for item in raw_skeletons
            if isinstance(item, dict) and item.get("id")
        }
        if len(self.skeletons) != len(raw_skeletons):
            raise SkeletonCatalogError("skeleton ids must be present and unique")
        self._validate()
        self._validate_knowledge_types()

    def _require_positive_int(self, key: str) -> int:
        value = self.data.get(key)
        if not isinstance(value, int) or value < 1:
            raise SkeletonCatalogError(f"{key} must be a positive integer")
        return value

    def _require_mapping(self, key: str) -> dict:
        value = self.data.get(key)
        if not isinstance(value, dict) or not value:
            raise SkeletonCatalogError(f"{key} must be a non-empty mapping")
        return value

    def _validate(self) -> None:
        if self.max_slots != 6:
            raise SkeletonCatalogError("max_slots must preserve StructuralPlan's six-slot limit")
        check = self.slots.get("check")
        if not isinstance(check, dict) or check.get("locked") is not True:
            raise SkeletonCatalogError("the check slot must exist and be locked")

        for slot_id, slot in self.slots.items():
            if not isinstance(slot, dict):
                raise SkeletonCatalogError(f"slot '{slot_id}' must be a mapping")

        for skeleton_id, skeleton in self.skeletons.items():
            slot_ids = skeleton.get("slots")
            if not isinstance(slot_ids, list):
                raise SkeletonCatalogError(f"skeleton '{skeleton_id}' slots must be a list")
            if len(slot_ids) > 5:
                raise SkeletonCatalogError(
                    f"skeleton '{skeleton_id}' exceeds the five-slot base limit"
                )
            if "check" not in slot_ids:
                raise SkeletonCatalogError(f"skeleton '{skeleton_id}' is missing locked check")
            unknown = [slot_id for slot_id in slot_ids if slot_id not in self.slots]
            if unknown:
                raise SkeletonCatalogError(
                    f"skeleton '{skeleton_id}' references unknown slots: {unknown}"
                )
            for profile in _PROFILE_SUPPORT_LEVEL:
                for misconception_count in range(4):
                    expanded, _toggles, _warnings, _diff, _issues = self._expand_slots(
                        skeleton,
                        profile=profile,
                        misconception_count=misconception_count,
                        approved_deviations=[],
                    )
                    if len(expanded) > self.max_slots:
                        raise SkeletonCatalogError(
                            f"skeleton '{skeleton_id}' expands beyond {self.max_slots} slots"
                        )
                    if "check" not in expanded:
                        raise SkeletonCatalogError(
                            f"skeleton '{skeleton_id}' expansion removed locked check"
                        )

    def _validate_knowledge_types(self) -> None:
        raw = self.data.get("knowledge_types")
        if not isinstance(raw, dict):
            raise SkeletonCatalogError("knowledge_types must be a mapping")
        self._knowledge_types: dict[str, KnowledgeTypeGuidance] = {}
        for name in _REQUIRED_KNOWLEDGE_TYPES:
            entry = raw.get(name)
            if not isinstance(entry, dict):
                raise SkeletonCatalogError(f"knowledge_types.{name} must be a mapping")
            label = entry.get("teacher_label")
            if not isinstance(label, str) or not label.strip():
                raise SkeletonCatalogError(
                    f"knowledge_types.{name}.teacher_label must be a non-empty string"
                )
            demands = entry.get("demands")
            if (
                not isinstance(demands, list)
                or not demands
                or not all(isinstance(item, str) and item.strip() for item in demands)
            ):
                raise SkeletonCatalogError(
                    f"knowledge_types.{name}.demands must be a non-empty list of strings"
                )
            contra = entry.get("contraindicated")
            if not isinstance(contra, list) or not all(isinstance(i, str) for i in contra):
                raise SkeletonCatalogError(
                    f"knowledge_types.{name}.contraindicated must be a list of strings"
                )
            definition = entry.get("definition")
            self._knowledge_types[name] = KnowledgeTypeGuidance(
                knowledge_type=name,
                teacher_label=label.strip(),
                definition=" ".join(definition.split()) if isinstance(definition, str) else "",
                demands=tuple(item.strip() for item in demands),
                contraindicated=tuple(item.strip() for item in contra),
            )

    def knowledge_type_guidance(self, knowledge_type: str) -> KnowledgeTypeGuidance | None:
        return self._knowledge_types.get(str(knowledge_type))

    def all_reachable_slots(self) -> dict[str, set[str]]:
        """Slot id -> recipes that can place it, including Python toggle insertions."""
        reachable: dict[str, set[str]] = {}
        for skeleton_id, skeleton in self.skeletons.items():
            for slot_id in skeleton.get("slots", []):
                reachable.setdefault(str(slot_id), set()).add(skeleton_id)
            for profile in _PROFILE_SUPPORT_LEVEL:
                for misconception_count in range(4):
                    expanded, *_rest = self._expand_slots(
                        skeleton,
                        profile=profile,
                        misconception_count=misconception_count,
                        approved_deviations=[],
                    )
                    for slot_id in expanded:
                        reachable.setdefault(str(slot_id), set()).add(skeleton_id)
        return reachable

    def skeleton_ids(self) -> list[str]:
        return sorted(self.skeletons)

    def skeleton_for(self, knowledge_type: KnowledgeType, lesson_mode: LessonMode) -> dict:
        exact = f"{knowledge_type}.{lesson_mode}"
        fallback = f"any.{lesson_mode}"
        skeleton = self.skeletons.get(exact) or self.skeletons.get(fallback)
        if skeleton is None:
            raise SkeletonCatalogError(
                f"no skeleton for knowledge_type={knowledge_type}, lesson_mode={lesson_mode}"
            )
        return skeleton

    def preview(
        self,
        request: SkeletonPreviewRequest,
        *,
        knowledge_type: KnowledgeType | None = None,
    ) -> SkeletonPreviewResponse:
        resolved_type = knowledge_type or classify_for_preview(request.objective)
        skeleton = self.skeleton_for(resolved_type, request.lesson_mode)
        variants = [
            self._preview_variant(
                skeleton,
                profile=profile,
                misconception_count=request.misconception_count,
                approved_deviations=request.approved_deviations,
            )
            for profile in request.group_profiles
        ]
        return SkeletonPreviewResponse(
            objective=request.objective,
            knowledge_type=resolved_type,
            knowledge_type_source=("provided" if knowledge_type else "deterministic_preview"),
            skeleton_id=str(skeleton["id"]),
            skeleton_version=self.version,
            variants=variants,
        )

    def preview_skeleton_by_id(
        self,
        skeleton_id: str,
        *,
        profile: GroupProfile = "core",
        misconception_count: int = 1,
        approved_deviations: list[DeviationRequest] | None = None,
    ) -> SkeletonVariantPreview:
        skeleton = self.skeletons.get(skeleton_id)
        if skeleton is None:
            raise SkeletonCatalogError(f"unknown skeleton '{skeleton_id}'")
        return self._preview_variant(
            skeleton,
            profile=profile,
            misconception_count=misconception_count,
            approved_deviations=approved_deviations or [],
        )

    def _preview_variant(
        self,
        skeleton: dict,
        *,
        profile: GroupProfile,
        misconception_count: int,
        approved_deviations: list[DeviationRequest],
    ) -> SkeletonVariantPreview:
        expanded, toggles, warnings, structural_diff, blocking_issues = self._expand_slots(
            skeleton,
            profile=profile,
            misconception_count=misconception_count,
            approved_deviations=approved_deviations,
        )
        slots = [
            SkeletonSlotPreview(
                slot_id=slot_id,
                role=str(self.slots[slot_id].get("role") or slot_id),
                purpose=str(self.slots[slot_id].get("purpose") or ""),
                locked=self.slots[slot_id].get("locked") is True,
            )
            for slot_id in expanded
        ]
        return SkeletonVariantPreview(
            group_profile=profile,
            support_level=_PROFILE_SUPPORT_LEVEL[profile],
            slots=slots,
            toggles_applied=toggles,
            warnings=warnings,
            structural_diff=structural_diff,
            blocking_issues=blocking_issues,
        )

    def _expand_slots(
        self,
        skeleton: dict,
        *,
        profile: GroupProfile,
        misconception_count: int,
        approved_deviations: list[DeviationRequest],
    ) -> tuple[
        list[str],
        list[str],
        list[str],
        list[SkeletonDiffEntry],
        list[SkeletonBlockingIssue],
    ]:
        slots = [str(slot_id) for slot_id in skeleton["slots"]]
        applied: list[str] = []
        warnings: list[str] = []
        structural_diff: list[SkeletonDiffEntry] = []
        blocking_issues: list[SkeletonBlockingIssue] = []
        knowledge_type = str(skeleton.get("knowledge_type"))
        support_level = _PROFILE_SUPPORT_LEVEL[profile]

        for index, deviation in enumerate(approved_deviations, start=1):
            if deviation.status != "approved":
                continue
            if deviation.skeleton_id != str(skeleton["id"]):
                self._record_issue(
                    warnings,
                    blocking_issues,
                    code="skeleton_conflict",
                    toggle_id=f"deviation:{deviation.id or index}",
                    message=(
                        f"approved deviation targets skeleton '{deviation.skeleton_id}', "
                        f"not '{skeleton['id']}'"
                    ),
                )
                continue
            self._apply_deviation(
                slots,
                deviation,
                index=index,
                applied=applied,
                structural_diff=structural_diff,
                warnings=warnings,
                blocking_issues=blocking_issues,
            )

        if "confront" in slots:
            first = slots.index("confront")
            previous_count = slots.count("confront")
            slots = [slot for slot in slots if slot != "confront"]
            desired = min(misconception_count, 2)
            for offset in range(desired):
                slots.insert(first + offset, "confront")
            applied.append("misconception.confront_per_belief")
            for _ in range(max(0, previous_count - desired)):
                structural_diff.append(
                    SkeletonDiffEntry(
                        operation="remove",
                        slot_id="confront",
                        toggle_id="misconception.confront_per_belief",
                        explanation="No unaddressed approved misconception needs this confrontation slot.",
                    )
                )
            for _ in range(max(0, desired - previous_count)):
                structural_diff.append(
                    SkeletonDiffEntry(
                        operation="repeat",
                        slot_id="confront",
                        toggle_id="misconception.confront_per_belief",
                        explanation="Repeat confrontation once per approved misconception, up to two slots.",
                    )
                )

        if support_level == "high" and knowledge_type == "procedural" and "independent" in slots:
            slots = ["model" if slot == "independent" else slot for slot in slots]
            applied.append("support.high.extra_modelling")
            structural_diff.append(
                SkeletonDiffEntry(
                    operation="replace",
                    slot_id="independent",
                    replacement_slot="model",
                    toggle_id="support.high.extra_modelling",
                    explanation="Replace premature independent work with an additional worked model.",
                )
            )

        if support_level == "high" and "independent" in slots and "guided" in slots:
            slots.remove("independent")
            applied.append("support.high.drop_independent")
            structural_diff.append(
                SkeletonDiffEntry(
                    operation="remove",
                    slot_id="independent",
                    toggle_id="support.high.drop_independent",
                    explanation="Keep practice guided until the group is ready for independent work.",
                )
            )

        if support_level == "high" and knowledge_type == "conceptual":
            self._insert_with_limit(
                slots,
                "contrast",
                anchor="explain",
                after=True,
                toggle_id="support.high.extra_contrast",
                applied=applied,
                warnings=warnings,
                structural_diff=structural_diff,
                blocking_issues=blocking_issues,
                explanation="Repeat contrast to separate the target idea from a likely confusion.",
            )

        if support_level == "low":
            self._insert_with_limit(
                slots,
                "apply",
                anchor="check",
                after=False,
                toggle_id="support.low.add_transfer",
                applied=applied,
                warnings=warnings,
                structural_diff=structural_diff,
                blocking_issues=blocking_issues,
                explanation="Add transfer so the group applies the capability in a less familiar case.",
            )
            if len(slots) >= self.max_slots and "orient" in slots:
                slots.remove("orient")
                applied.append("support.low.drop_orient")
                structural_diff.append(
                    SkeletonDiffEntry(
                        operation="remove",
                        slot_id="orient",
                        toggle_id="support.low.drop_orient",
                        explanation="Remove orientation when space is needed for extension transfer.",
                    )
                )

        return slots, applied, warnings, structural_diff, blocking_issues

    def _insert_with_limit(
        self,
        slots: list[str],
        slot_id: str,
        *,
        anchor: str,
        after: bool,
        toggle_id: str,
        applied: list[str],
        warnings: list[str],
        structural_diff: list[SkeletonDiffEntry],
        blocking_issues: list[SkeletonBlockingIssue],
        explanation: str,
    ) -> None:
        if len(slots) >= self.max_slots:
            self._record_issue(
                warnings,
                blocking_issues,
                code="variant_slot_overflow",
                toggle_id=toggle_id,
                message=f"skipped toggle '{toggle_id}' at {self.max_slots} slots",
            )
            return
        if anchor not in slots:
            self._record_issue(
                warnings,
                blocking_issues,
                code="skeleton_conflict",
                toggle_id=toggle_id,
                message=f"toggle '{toggle_id}' anchor '{anchor}' is absent",
            )
            return
        index = slots.index(anchor) + (1 if after else 0)
        operation = "repeat" if slot_id in slots else "add"
        slots.insert(index, slot_id)
        applied.append(toggle_id)
        structural_diff.append(
            SkeletonDiffEntry(
                operation=operation,
                slot_id=slot_id,
                toggle_id=toggle_id,
                explanation=explanation,
            )
        )

    @staticmethod
    def _record_issue(
        warnings: list[str],
        blocking_issues: list[SkeletonBlockingIssue],
        *,
        code: Literal["variant_slot_overflow", "skeleton_conflict"],
        toggle_id: str,
        message: str,
    ) -> None:
        warnings.append(f"{code}: {message}")
        blocking_issues.append(
            SkeletonBlockingIssue(code=code, message=message, toggle_id=toggle_id)
        )

    def _apply_deviation(
        self,
        slots: list[str],
        deviation: DeviationRequest,
        *,
        index: int,
        applied: list[str],
        structural_diff: list[SkeletonDiffEntry],
        warnings: list[str],
        blocking_issues: list[SkeletonBlockingIssue],
    ) -> None:
        toggle_id = f"deviation:{deviation.id or index}"
        replacement = deviation.replacement_slot
        if deviation.target_slot not in slots:
            self._record_issue(
                warnings,
                blocking_issues,
                code="skeleton_conflict",
                toggle_id=toggle_id,
                message=f"deviation target '{deviation.target_slot}' is absent",
            )
            return
        if replacement is not None and replacement not in self.slots:
            self._record_issue(
                warnings,
                blocking_issues,
                code="skeleton_conflict",
                toggle_id=toggle_id,
                message=f"deviation replacement '{replacement}' is not a declared slot",
            )
            return
        if deviation.operation == "insert":
            if len(slots) >= self.max_slots:
                self._record_issue(
                    warnings,
                    blocking_issues,
                    code="variant_slot_overflow",
                    toggle_id=toggle_id,
                    message=f"approved insertion exceeds the {self.max_slots}-slot limit",
                )
                return
            repeated = replacement in slots
            slots.insert(slots.index(deviation.target_slot), str(replacement))
            operation: Literal["add", "remove", "replace", "repeat", "reorder"] = (
                "repeat" if repeated else "add"
            )
        elif deviation.operation == "remove":
            slots.remove(deviation.target_slot)
            operation = "remove"
        elif deviation.operation == "replace":
            slots[slots.index(deviation.target_slot)] = str(replacement)
            operation = "replace"
        else:
            moved = slots.pop(slots.index(deviation.target_slot))
            slots.insert(slots.index(str(replacement)), moved)
            operation = "reorder"
        applied.append(toggle_id)
        structural_diff.append(
            SkeletonDiffEntry(
                operation=operation,
                slot_id=deviation.target_slot,
                replacement_slot=replacement,
                toggle_id=toggle_id,
                explanation=f"Teacher-approved deviation: {deviation.reason}",
            )
        )


def classify_for_preview(objective: str) -> KnowledgeType:
    """Zero-model preview classification; authoritative classification remains the LLM call."""
    normalized = objective.casefold()
    if any(token in normalized for token in ("assess ", "critique ", "recommend ", "defend ")):
        return "evaluative"
    if any(
        token in normalized
        for token in ("calculate ", "solve ", "construct ", "derive ", "balance ", "plot ")
    ):
        return "procedural"
    if any(token in normalized for token in ("identify ", "name ", "list ", "state ", "label ")):
        return "factual"
    return "conceptual"


def validate_skeletons_against_spec(
    catalog: SkeletonCatalog, spec: Any, intent_catalogue: Mapping[str, Any]
) -> None:
    """Every typical intent of every reachable slot must be legal for the resource spec."""
    from print.resources.candidates import _excluded_reasons, _slot_typical_intents

    vocab = getattr(spec, "vocabulary", None)
    if vocab is None:
        raise SkeletonCatalogError(
            f"resource spec '{getattr(spec, 'id', '?')}' has no vocabulary to validate "
            "skeletons against"
        )
    permitted = {str(i) for i in (getattr(vocab.intents, "permitted", None) or [])}
    excluded = _excluded_reasons(getattr(vocab.intents, "excluded", None))
    violations: list[str] = []
    for slot_id, recipes in sorted(catalog.all_reachable_slots().items()):
        slot = catalog.slots.get(slot_id) or {}
        who = ",".join(sorted(recipes))
        for intent in _slot_typical_intents(slot):
            reasons = []
            if intent not in intent_catalogue:
                reasons.append("not in intent catalogue")
            if intent not in permitted:
                reasons.append("not in spec permitted intents")
            if intent in excluded:
                reasons.append(f"excluded by spec ({excluded[intent]})")
            for reason in reasons:
                violations.append(
                    f"recipe(s) [{who}] slot '{slot_id}' intent '{intent}': {reason}"
                )
    if violations:
        raise SkeletonCatalogError(
            "skeleton slots conflict with resource spec:\n  " + "\n  ".join(violations)
        )


def _default_skeleton_path() -> Path:
    return Path(__file__).resolve().parents[3] / "resources" / "skeletons.yaml"


@lru_cache(maxsize=1)
def load_skeleton_catalog(path: str | Path | None = None) -> SkeletonCatalog:
    source = Path(path) if path is not None else _default_skeleton_path()
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SkeletonCatalogError("skeletons.yaml root must be a mapping")
    return SkeletonCatalog(raw)


def initialize_skeleton_catalog() -> SkeletonCatalog:
    return load_skeleton_catalog()
