from __future__ import annotations

from generation.v3_studio.dtos import V3InputForm
from v3_blueprint.models import ProductionBlueprint


def derive_support_adaptations(blueprint: ProductionBlueprint) -> list[str]:
    support_summary: list[str] = []
    lesson_mode = blueprint.lesson.lesson_mode
    if lesson_mode == "first_exposure":
        support_summary.append("Keep one anchor example constant across sections.")
        support_summary.append("Limit questions to warm and medium difficulty.")
    elif lesson_mode == "repair":
        support_summary.append("Stay warm until the fault line is resolved.")
    elif lesson_mode == "retrieval":
        support_summary.append("Use cold and transfer recall with minimal re-exposition.")
    elif lesson_mode == "transfer":
        support_summary.append("Bias toward transfer tasks in unfamiliar contexts.")
    elif lesson_mode == "consolidation":
        support_summary.append("Progress from medium toward cold and transfer questions.")
    return support_summary


def summarise_form_supports(form: V3InputForm) -> list[str]:
    summary: list[str] = []
    if form.language_support != "none":
        summary.append(f"Language support: {form.language_support.replace('_', ' ')}")
    if form.reading_level != "on_grade":
        summary.append(f"Reading level: {form.reading_level.replace('_', ' ')}")
    if form.learner_level != "on_grade":
        summary.append(f"Learner level: {form.learner_level.replace('_', ' ')}")
    if form.prior_knowledge_level != "some_background":
        summary.append(f"Prior knowledge: {form.prior_knowledge_level.replace('_', ' ')}")
    for need in form.support_needs[:4]:
        summary.append(f"Support need: {need}")
    for pref in form.learning_preferences[:4]:
        summary.append(f"Preference: {pref.replace('_', ' ')}")
    return summary


__all__ = ["derive_support_adaptations", "summarise_form_supports"]
