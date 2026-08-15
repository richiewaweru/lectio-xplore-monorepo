from pathlib import Path
import os
import secrets
from urllib.parse import urlsplit

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_env_file() -> Path:
    """Prefer ``backend/.env``, then walk ancestors for a local ``.env``.

    Config lives at ``backend/src/core/config.py``. Native monorepo runs should
    load ``apps/textbook-agent/backend/.env`` even if a parent compose ``.env``
    also exists.
    """

    current = Path(__file__).resolve()
    backend_root = current.parents[2]  # .../backend
    backend_env = backend_root / ".env"
    if backend_env.exists():
        return backend_env
    for ancestor in current.parents:
        candidate = ancestor / ".env"
        if candidate.exists():
            return candidate
    return backend_root / ".env"


def _normalize_path_env(var_name: str, *, base_dir: Path) -> None:
    raw = os.getenv(var_name)
    if not raw:
        return

    cleaned = raw.strip().strip('"').strip("'")
    candidate = Path(cleaned)
    if candidate.is_absolute():
        if candidate.exists():
            os.environ[var_name] = str(candidate)
            return
        # Docker/Railway absolute paths are invalid on a local checkout.
        fallback = (base_dir / "contracts").resolve()
        if var_name == "LECTIO_CONTRACTS_DIR" and fallback.exists():
            os.environ[var_name] = str(fallback)
        return

    os.environ[var_name] = str((base_dir / candidate).resolve())


def _normalize_sqlite_database_url(var_name: str, *, base_dir: Path) -> None:
    raw = os.getenv(var_name)
    if not raw or not raw.startswith("sqlite"):
        return

    _, separator, path_part = raw.partition(":///")
    if separator != ":///" or not path_part:
        return

    path = Path(path_part)
    if path.is_absolute():
        return

    resolved = (base_dir / path).resolve().as_posix()
    os.environ[var_name] = f"{raw[: raw.index(':///') + 4]}{resolved}"


def _normalize_backend_local_env_paths(env_file: Path) -> None:
    base_dir = env_file.parent
    _normalize_path_env("LECTIO_CONTRACTS_DIR", base_dir=base_dir)
    _normalize_sqlite_database_url("DATABASE_URL", base_dir=base_dir)
    # Ensure contracts always resolve for local backend runs.
    contracts = os.getenv("LECTIO_CONTRACTS_DIR")
    if not contracts or not Path(contracts).exists():
        fallback = (base_dir / "contracts").resolve()
        if fallback.exists():
            os.environ["LECTIO_CONTRACTS_DIR"] = str(fallback)


def bootstrap_environment(env_file: str | Path | None = None) -> Path:
    """
    Load backend-local environment variables into ``os.environ`` once at startup.

    ``override=False`` preserves real process/CI variables while making local
    ``backend/.env`` values visible to code paths that read directly from
    ``os.getenv(...)`` such as provider registries.
    """

    target = Path(env_file) if env_file is not None else _default_env_file()
    load_dotenv(target, override=False)
    _normalize_backend_local_env_paths(target)
    return target


_ENV_FILE = bootstrap_environment()
_PRODUCTION_LIKE_ENVS = {"production", "staging"}
_LOCAL_ONLY_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0"}
_PLACEHOLDER_SECRET_FRAGMENTS = (
    "change-me",
    "changeme",
    "replace-me",
    "replace_this",
    "example",
    "dummy",
    "placeholder",
)


def _has_local_only_host(url: str) -> bool:
    hostname = urlsplit(url).hostname
    return hostname in _LOCAL_ONLY_HOSTNAMES


def _looks_like_placeholder_secret(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return True
    return any(fragment in normalized for fragment in _PLACEHOLDER_SECRET_FRAGMENTS)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"),
    )

    # API
    default_pagination_limit: int = 20

    # Generation admission
    generation_max_concurrent_per_user: int = Field(default=2, ge=1)
    learning_pack_max_active_per_user: int = Field(default=1, ge=1)
    learning_pack_max_active_resources_per_pack: int = Field(default=2, ge=1)
    learning_pack_max_resources: int = Field(default=7, ge=1)
    v3_timeout_stage1_seconds: int = Field(default=240, ge=1)
    v3_timeout_stage2_section_seconds: int = Field(default=100, ge=1)
    v3_max_tokens_safety: int = Field(default=32000, ge=1)
    v3_max_tokens_fast: int = Field(default=8000, ge=1)
    v3_max_tokens_standard: int = Field(default=16000, ge=1)
    v3_max_tokens_premium: int = Field(default=24000, ge=1)
    v2_skeleton_shadow_enabled: bool = True
    xplore_v2_enabled: bool = True
    xplore_v2_beta_users: str = ""
    xplore_page_writer_retries: int = Field(default=1, ge=0)
    xplore_page_sequential_planning: bool = True
    # Whole-lesson native planning: semantic tiers (model names are configurable).
    # Prefer PAGE_MODEL_*; fall back to the live V3 slot model names from Textbook agent.
    page_model_standard: str = Field(
        default="deepseek-v4-pro",
        validation_alias=AliasChoices(
            "PAGE_MODEL_STANDARD",
            "V3_STANDARD_MODEL_NAME",
            "V3_STANDARD_MODEL",
        ),
    )
    page_model_fast: str = Field(
        default="deepseek-v4-flash",
        validation_alias=AliasChoices(
            "PAGE_MODEL_FAST",
            "V3_FAST_MODEL_NAME",
            "V3_FAST_MODEL",
        ),
    )
    page_lesson_plan_timeout_seconds: int = Field(
        default=420,
        ge=1,
        validation_alias=AliasChoices(
            "PAGE_LESSON_PLAN_TIMEOUT_SECONDS",
            "V3_TIMEOUT_STAGE1_SECONDS",
        ),
    )
    page_form_plan_timeout_seconds: int = Field(default=120, ge=1)
    page_standard_writer_timeout_seconds: int = Field(
        default=180,
        ge=1,
        validation_alias=AliasChoices(
            "PAGE_STANDARD_WRITER_TIMEOUT_SECONDS",
            "V3_TIMEOUT_SECTION_SECONDS",
        ),
    )
    page_fast_writer_timeout_seconds: int = Field(
        default=90,
        ge=1,
        validation_alias=AliasChoices(
            "PAGE_FAST_WRITER_TIMEOUT_SECONDS",
            "V3_TIMEOUT_QUESTION_SECONDS",
        ),
    )
    page_planning_heartbeat_seconds: int = Field(default=5, ge=1)
    xplore_page_documents_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "XPLORE_PAGE_DOCUMENTS_ENABLED",
            "xplore_page_documents_enabled",
        ),
    )
    xplore_page_document_scope: str = Field(
        default="all",
        validation_alias=AliasChoices(
            "XPLORE_PAGE_DOCUMENT_SCOPE",
            "xplore_page_document_scope",
        ),
    )
    xplore_native_worker_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "XPLORE_NATIVE_WORKER_ENABLED",
            "xplore_native_worker_enabled",
        ),
    )
    allow_paid_llm_tests: bool = False

    # Output
    report_output_dir: str = "outputs/reports"
    pdf_temp_dir: str = "outputs/pdf"
    image_base_url: str = "http://localhost:8000/images"
    gcs_bucket_name: str = "textbook-diagrams"

    # Authentication
    google_client_id: str = ""
    jwt_secret_key: str = "CHANGE-ME"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Database
    database_url: str = "postgresql+asyncpg://textbook:textbook@localhost:5432/textbook_agent"
    db_echo: bool = False
    run_migrations_on_startup: bool = True
    json_logs: bool = Field(
        default=False,
        validation_alias=AliasChoices("JSON_LOGS", "JSON_LOGGING"),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("LOG_LEVEL"),
    )

    # CORS
    frontend_origin: str = "http://localhost:5173"

    # Lesson Builder (share links point here)
    lesson_builder_public_url: str = "http://127.0.0.1:5173"
    pdf_export_enabled: bool = True
    pdf_render_base_url: str = "http://127.0.0.1:5173"
    pdf_export_timeout_ms: int = Field(default=45000, gt=0)
    playwright_timeout_ms: int = Field(default=45000, gt=0)
    pdf_max_file_size_mb: int = Field(default=50, gt=0)
    pdf_max_page_count: int = Field(default=200, gt=0)
    pdf_usable_page_height_px: int = Field(default=970, gt=0)
    pdf_temp_retention_seconds: int = Field(default=3600, ge=60)

    @field_validator("app_env", mode="before")
    @classmethod
    def _normalize_app_env(cls, value: str | None) -> str:
        return (value or "development").strip().lower()

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: str | None) -> str:
        return (value or "INFO").strip().upper()

    @model_validator(mode="after")
    def _validate_production_like_runtime(self) -> "Settings":
        if _looks_like_placeholder_secret(self.jwt_secret_key):
            hint = secrets.token_hex(32)
            raise ValueError(
                "JWT_SECRET_KEY is not set to a secure value. "
                "Generate one with: "
                "python -c \"import secrets; print(secrets.token_hex(32))\" "
                f"Example: {hint}"
            )

        if self.app_env not in _PRODUCTION_LIKE_ENVS:
            return self

        errors: list[str] = []
        if self.database_url.startswith("sqlite"):
            errors.append("DATABASE_URL must use PostgreSQL, not SQLite")
        if _has_local_only_host(self.frontend_origin):
            errors.append("FRONTEND_ORIGIN must not point to a localhost-only origin")
        if _has_local_only_host(self.lesson_builder_public_url):
            errors.append("LESSON_BUILDER_PUBLIC_URL must not point to a localhost-only origin")
        if not self.google_client_id.strip():
            errors.append("GOOGLE_CLIENT_ID must be configured")
        if self.pdf_export_enabled and _has_local_only_host(self.pdf_render_base_url):
            errors.append("PDF_RENDER_BASE_URL must not point to a localhost-only origin")

        if errors:
            raise ValueError(
                f"Unsafe configuration for APP_ENV={self.app_env}: " + "; ".join(errors)
            )

        return self

    @property
    def json_logging(self) -> bool:
        return self.json_logs


settings = Settings()
