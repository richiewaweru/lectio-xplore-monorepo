from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResourcePromptContext(BaseModel):
    """Runtime prompt context; intentionally not persisted as StanceSpec."""

    model_config = ConfigDict(extra="forbid")

    resource_id: str
    resource_label: str
    resource_purpose: str
    lesson_mode: str
    prior_established: list[str] = Field(default_factory=list)
    must_establish: list[str] = Field(default_factory=list)
    must_not_introduce: list[str] = Field(default_factory=list)
    terminology: list[str] = Field(default_factory=list)
    text_policy: dict[str, object] = Field(default_factory=dict)
    validation_rules: list[str] = Field(default_factory=list)


def build_resource_prompt_context(*, spec, lesson_mode, prior_established, scope_contract):
    return ResourcePromptContext(
        resource_id=spec.id,
        resource_label=spec.label,
        resource_purpose=spec.intent.strip(),
        lesson_mode=lesson_mode,
        prior_established=list(prior_established),
        must_establish=list(scope_contract.get("must_establish", [])),
        must_not_introduce=list(scope_contract.get("must_not_introduce", [])),
        terminology=list(scope_contract.get("terminology", [])),
        text_policy=spec.text.model_dump(mode="json"),
        validation_rules=list(spec.validation),
    )


def render_resource_context(context: ResourcePromptContext) -> str:
    def bullets(values: list[str]) -> str:
        return "\n".join(f"- {value}" for value in values) if values else "- none declared"

    return f"""## RESOURCE YOU ARE BUILDING

Resource: {context.resource_label} ({context.resource_id})
Mode: {context.lesson_mode}
Purpose:
{context.resource_purpose}

Actual prior established knowledge:
{bullets(context.prior_established)}

This lesson must establish:
{bullets(context.must_establish)}

Must not introduce:
{bullets(context.must_not_introduce)}

Required terminology:
{bullets(context.terminology)}
""".strip()
