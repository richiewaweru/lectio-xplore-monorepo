from __future__ import annotations

from dataclasses import asdict, dataclass

from core.config import Settings
from core.llm import RetryPolicy
from pipeline.types.requests import GenerationMode


def _setting(settings: Settings, name: str, default):
    return getattr(settings, name, default)


@dataclass(frozen=True)
class ConcurrencyPolicy:
    mode: GenerationMode
    max_section_concurrency: int
    max_diagram_concurrency: int
    max_qc_concurrency: int

    @property
    def max_media_concurrency(self) -> int:
        return self.max_diagram_concurrency


@dataclass(frozen=True)
class TimeoutPolicy:
    mode: GenerationMode
    curriculum_planner_timeout_seconds: float
    content_core_timeout_seconds: float
    content_practice_timeout_seconds: float
    content_enrichment_timeout_seconds: float
    content_repair_timeout_seconds: float
    field_regenerator_timeout_seconds: float
    qc_timeout_seconds: float
    diagram_inner_timeout_seconds: float
    diagram_node_budget_seconds: float
    generation_timeout_base_seconds: float
    generation_timeout_per_section_seconds: float
    generation_timeout_cap_seconds: float

    def generation_timeout_seconds(self, section_count: int) -> float:
        return min(
            self.generation_timeout_base_seconds
            + self.generation_timeout_per_section_seconds * max(section_count, 1),
            self.generation_timeout_cap_seconds,
        )


@dataclass(frozen=True)
class RetryPolicyMap:
    mode: GenerationMode
    curriculum_planner: RetryPolicy
    content_core: RetryPolicy
    content_practice: RetryPolicy
    content_enrichment: RetryPolicy
    content_repair: RetryPolicy
    field_regenerator: RetryPolicy
    qc_agent: RetryPolicy
    diagram_generator: RetryPolicy

    def for_node(self, node: str) -> RetryPolicy:
        mapping = {
            "curriculum_planner": self.curriculum_planner,
            "content_generator": self.content_core,
            "content_generator_core": self.content_core,
            "content_generator_practice": self.content_practice,
            "content_generator_enrichment": self.content_enrichment,
            "content_generator_repair": self.content_repair,
            "field_regenerator": self.field_regenerator,
            "qc_agent": self.qc_agent,
            "diagram_generator": self.diagram_generator,
        }
        return mapping.get(node, self.content_core)

    def to_public_dict(self) -> dict[str, dict[str, float | int]]:
        return {
            "curriculum_planner": asdict(self.curriculum_planner),
            "content_core": asdict(self.content_core),
            "content_practice": asdict(self.content_practice),
            "content_enrichment": asdict(self.content_enrichment),
            "content_repair": asdict(self.content_repair),
            "field_regenerator": asdict(self.field_regenerator),
            "qc_agent": asdict(self.qc_agent),
            "diagram_generator": asdict(self.diagram_generator),
        }


@dataclass(frozen=True)
class RuntimePolicyBundle:
    mode: GenerationMode
    generation_max_concurrent_per_user: int
    max_section_rerenders: int
    concurrency: ConcurrencyPolicy
    timeouts: TimeoutPolicy
    retries: RetryPolicyMap

    def generation_timeout_seconds(self, section_count: int) -> float:
        return self.timeouts.generation_timeout_seconds(section_count)


def _mode_prefix(mode: GenerationMode) -> str:
    return mode.value.lower()


def resolve_concurrency_policy(
    settings: Settings,
    mode: GenerationMode,
) -> ConcurrencyPolicy:
    prefix = _mode_prefix(mode)
    return ConcurrencyPolicy(
        mode=mode,
        max_section_concurrency=_setting(
            settings, f"pipeline_concurrency_{prefix}_section_max", 2
        ),
        max_diagram_concurrency=_setting(
            settings, f"pipeline_concurrency_{prefix}_diagram_max", 2
        ),
        max_qc_concurrency=_setting(settings, f"pipeline_concurrency_{prefix}_qc_max", 2),
    )


def resolve_timeout_policy(
    settings: Settings,
    mode: GenerationMode,
) -> TimeoutPolicy:
    return TimeoutPolicy(
        mode=mode,
        curriculum_planner_timeout_seconds=_setting(
            settings, "pipeline_timeout_curriculum_seconds", 90.0
        ),
        content_core_timeout_seconds=_setting(
            settings, "pipeline_timeout_content_core_seconds", 90.0
        ),
        content_practice_timeout_seconds=_setting(
            settings, "pipeline_timeout_content_practice_seconds", 90.0
        ),
        content_enrichment_timeout_seconds=_setting(
            settings, "pipeline_timeout_content_enrichment_seconds", 90.0
        ),
        content_repair_timeout_seconds=_setting(
            settings, "pipeline_timeout_content_repair_seconds", 90.0
        ),
        field_regenerator_timeout_seconds=_setting(
            settings, "pipeline_timeout_field_regen_seconds", 90.0
        ),
        qc_timeout_seconds=_setting(settings, "pipeline_timeout_qc_seconds", 60.0),
        diagram_inner_timeout_seconds=_setting(
            settings, "pipeline_timeout_diagram_inner_seconds", 120.0
        ),
        diagram_node_budget_seconds=_setting(
            settings, "pipeline_timeout_diagram_node_budget_seconds", 180.0
        ),
        generation_timeout_base_seconds=_setting(
            settings, "pipeline_timeout_generation_base_seconds", 180.0
        ),
        generation_timeout_per_section_seconds=_setting(
            settings, "pipeline_timeout_generation_per_section_seconds", 45.0
        ),
        generation_timeout_cap_seconds=_setting(
            settings, "pipeline_timeout_generation_cap_seconds", 900.0
        ),
    )


def resolve_retry_policy_map(
    settings: Settings,
    mode: GenerationMode,
    *,
    timeouts: TimeoutPolicy | None = None,
) -> RetryPolicyMap:
    timeout_policy = timeouts or resolve_timeout_policy(settings, mode)
    return RetryPolicyMap(
        mode=mode,
        curriculum_planner=RetryPolicy(
            max_attempts=_setting(settings, "pipeline_retry_curriculum_max_attempts", 2),
            call_timeout_seconds=timeout_policy.curriculum_planner_timeout_seconds,
        ),
        content_core=RetryPolicy(
            max_attempts=_setting(settings, "pipeline_retry_content_core_max_attempts", 2),
            call_timeout_seconds=timeout_policy.content_core_timeout_seconds,
        ),
        content_practice=RetryPolicy(
            max_attempts=_setting(settings, "pipeline_retry_content_practice_max_attempts", 2),
            call_timeout_seconds=timeout_policy.content_practice_timeout_seconds,
        ),
        content_enrichment=RetryPolicy(
            max_attempts=_setting(
                settings, "pipeline_retry_content_enrichment_max_attempts", 1
            ),
            call_timeout_seconds=timeout_policy.content_enrichment_timeout_seconds,
        ),
        content_repair=RetryPolicy(
            max_attempts=_setting(settings, "pipeline_retry_content_repair_max_attempts", 1),
            call_timeout_seconds=timeout_policy.content_repair_timeout_seconds,
        ),
        field_regenerator=RetryPolicy(
            max_attempts=_setting(settings, "pipeline_retry_field_regen_max_attempts", 1),
            call_timeout_seconds=timeout_policy.field_regenerator_timeout_seconds,
        ),
        qc_agent=RetryPolicy(
            max_attempts=_setting(settings, "pipeline_retry_qc_max_attempts", 1),
            call_timeout_seconds=timeout_policy.qc_timeout_seconds,
        ),
        diagram_generator=RetryPolicy(
            max_attempts=_setting(settings, "pipeline_retry_diagram_max_attempts", 1),
            call_timeout_seconds=timeout_policy.diagram_inner_timeout_seconds,
        ),
    )


def resolve_max_section_rerenders(settings: Settings, mode: GenerationMode) -> int:
    return _setting(settings, f"pipeline_rerender_{_mode_prefix(mode)}_section_max", 2)


def resolve_generation_max_concurrent_per_user(settings: Settings) -> int:
    return settings.generation_max_concurrent_per_user


def resolve_generation_timeout_seconds(
    settings: Settings,
    section_count: int,
    *,
    mode: GenerationMode = GenerationMode.BALANCED,
) -> float:
    return resolve_timeout_policy(settings, mode).generation_timeout_seconds(section_count)


def resolve_runtime_policy_bundle(
    settings: Settings,
    mode: GenerationMode,
) -> RuntimePolicyBundle:
    timeouts = resolve_timeout_policy(settings, mode)
    return RuntimePolicyBundle(
        mode=mode,
        generation_max_concurrent_per_user=resolve_generation_max_concurrent_per_user(settings),
        max_section_rerenders=resolve_max_section_rerenders(settings, mode),
        concurrency=resolve_concurrency_policy(settings, mode),
        timeouts=timeouts,
        retries=resolve_retry_policy_map(settings, mode, timeouts=timeouts),
    )
