from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from v3_blueprint.models import ComponentPlan, VisualInstruction


class SectionWorkOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    title: str
    role: str
    components: list[ComponentPlan] = Field(default_factory=list)


class VisualWorkOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visuals: list[VisualInstruction] = Field(default_factory=list)


class InteractionWorkOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    question_ids: list[str] = Field(default_factory=list)


class AnswerKeyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    expected_answer: str


class AnswerKeyWorkOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: str
    items: list[AnswerKeyItem] = Field(default_factory=list)


class CoherenceReviewWorkOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checklist: list[str] = Field(default_factory=list)


class CompiledWorkOrders(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_orders: list[SectionWorkOrder] = Field(default_factory=list)
    visual_order: VisualWorkOrder
    interaction_orders: list[InteractionWorkOrder] = Field(default_factory=list)
    answer_key_order: AnswerKeyWorkOrder
    coherence_review_order: CoherenceReviewWorkOrder
