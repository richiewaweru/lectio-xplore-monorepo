from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tomllib
from types import SimpleNamespace

import pytest
import yaml
from pydantic import ValidationError

from core.config import Settings, bootstrap_environment
from core.database.session import build_engine_kwargs
from media.storage.image_store import LocalImageStore, get_image_store


def _snapshot_env(*names: str) -> dict[str, str | None]:
    return {name: os.environ.get(name) for name in names}


def _restore_env(snapshot: dict[str, str | None]) -> None:
    for name, value in snapshot.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def test_bootstrap_environment_loads_missing_values_without_overwriting_existing(
    monkeypatch,
    tmp_path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "ANTHROPIC_API_KEY=file-anthropic-key",
                "PIPELINE_FAST_PROVIDER=openai_compatible",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("PIPELINE_FAST_PROVIDER", "anthropic")

    snapshot = _snapshot_env("ANTHROPIC_API_KEY", "PIPELINE_FAST_PROVIDER")
    try:
        loaded = bootstrap_environment(env_file)

        assert loaded == env_file
        assert os.getenv("ANTHROPIC_API_KEY") == "file-anthropic-key"
        assert os.getenv("PIPELINE_FAST_PROVIDER") == "anthropic"
    finally:
        _restore_env(snapshot)


def test_bootstrap_environment_resolves_relative_backend_local_paths(
    monkeypatch,
    tmp_path,
) -> None:
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LECTIO_CONTRACTS_DIR=./contracts",
                "DATABASE_URL=sqlite+aiosqlite:///./textbook_agent.db",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("LECTIO_CONTRACTS_DIR", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    snapshot = _snapshot_env("LECTIO_CONTRACTS_DIR", "DATABASE_URL")
    try:
        bootstrap_environment(env_file)

        assert os.getenv("LECTIO_CONTRACTS_DIR") == str(contracts_dir.resolve())
        assert os.getenv("DATABASE_URL") == f"sqlite+aiosqlite:///{(tmp_path / 'textbook_agent.db').resolve().as_posix()}"
    finally:
        _restore_env(snapshot)


def test_bootstrap_environment_preserves_absolute_sqlite_overrides(
    monkeypatch,
    tmp_path,
) -> None:
    db_path = (tmp_path / "absolute.db").resolve()
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"DATABASE_URL=sqlite+aiosqlite:///{db_path.as_posix()}\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("DATABASE_URL", raising=False)

    snapshot = _snapshot_env("DATABASE_URL")
    try:
        bootstrap_environment(env_file)

        assert os.getenv("DATABASE_URL") == f"sqlite+aiosqlite:///{db_path.as_posix()}"
    finally:
        _restore_env(snapshot)


def test_bootstrap_environment_preserves_postgres_urls(
    monkeypatch,
    tmp_path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql+asyncpg://textbook:textbook@localhost:5432/textbook_agent\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("DATABASE_URL", raising=False)

    snapshot = _snapshot_env("DATABASE_URL")
    try:
        bootstrap_environment(env_file)

        assert (
            os.getenv("DATABASE_URL")
            == "postgresql+asyncpg://textbook:textbook@localhost:5432/textbook_agent"
        )
    finally:
        _restore_env(snapshot)


def test_engine_kwargs_use_db_echo_for_sqlite() -> None:
    kwargs = build_engine_kwargs("sqlite+aiosqlite:///./test.db", db_echo=True)

    assert kwargs == {"echo": True}


def test_engine_kwargs_add_postgres_pool_settings() -> None:
    kwargs = build_engine_kwargs(
        "postgresql+asyncpg://textbook:textbook@localhost:5432/textbook_agent",
        db_echo=False,
    )

    assert kwargs == {
        "echo": False,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }


def test_settings_allow_local_defaults_in_development(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-development-key")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("LESSON_BUILDER_PUBLIC_URL", "http://127.0.0.1:5173")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./textbook_agent.db")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.db_echo is False


def test_settings_reject_placeholder_secret_in_development(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./textbook_agent.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "change-me-to-a-random-secret")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("LESSON_BUILDER_PUBLIC_URL", "http://127.0.0.1:5173")

    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(_env_file=None)


def test_settings_reject_placeholder_secret_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://textbook:textbook@db:5432/textbook_agent")
    monkeypatch.setenv("JWT_SECRET_KEY", "change-me-to-a-random-secret")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")
    monkeypatch.setenv("LESSON_BUILDER_PUBLIC_URL", "https://app.example.com")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "example-google-client-id")

    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(_env_file=None)


def test_settings_reject_local_origins_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://textbook:textbook@db:5432/textbook_agent")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-production-key")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:3000")
    monkeypatch.setenv("LESSON_BUILDER_PUBLIC_URL", "https://app.example.com")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "example-google-client-id")

    with pytest.raises(ValidationError, match="FRONTEND_ORIGIN"):
        Settings(_env_file=None)


def test_settings_reject_local_lesson_builder_url_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://textbook:textbook@db:5432/textbook_agent")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-production-key")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")
    monkeypatch.setenv("LESSON_BUILDER_PUBLIC_URL", "http://localhost:3000")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "example-google-client-id")
    monkeypatch.setenv("PDF_RENDER_BASE_URL", "https://app.example.com")

    with pytest.raises(ValidationError, match="LESSON_BUILDER_PUBLIC_URL"):
        Settings(_env_file=None)


def test_settings_reject_local_pdf_render_base_url_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://textbook:textbook@db:5432/textbook_agent")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-production-key")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")
    monkeypatch.setenv("LESSON_BUILDER_PUBLIC_URL", "https://app.example.com")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "example-google-client-id")
    monkeypatch.setenv("PDF_RENDER_BASE_URL", "http://localhost:5173")

    with pytest.raises(ValidationError, match="PDF_RENDER_BASE_URL"):
        Settings(_env_file=None)


def test_settings_require_google_client_id_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://textbook:textbook@db:5432/textbook_agent")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-production-key")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")
    monkeypatch.setenv("LESSON_BUILDER_PUBLIC_URL", "https://app.example.com")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)

    with pytest.raises(ValidationError, match="GOOGLE_CLIENT_ID"):
        Settings(_env_file=None)


def test_settings_accept_safe_production_configuration(monkeypatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://textbook:textbook@db:5432/textbook_agent")
    monkeypatch.setenv("DB_ECHO", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-production-key")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")
    monkeypatch.setenv("LESSON_BUILDER_PUBLIC_URL", "https://app.example.com")
    monkeypatch.setenv("PDF_RENDER_BASE_URL", "https://app.example.com")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "example-google-client-id")

    settings = Settings(_env_file=None)

    assert settings.app_env == "production"
    assert settings.db_echo is True


def test_settings_accept_json_logs_env_aliases(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./textbook_agent.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-development-key")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("LESSON_BUILDER_PUBLIC_URL", "http://127.0.0.1:5173")
    monkeypatch.setenv("JSON_LOGGING", "true")
    monkeypatch.delenv("JSON_LOGS", raising=False)

    legacy_settings = Settings(_env_file=None)

    monkeypatch.setenv("JSON_LOGS", "true")
    monkeypatch.delenv("JSON_LOGGING", raising=False)
    canonical_settings = Settings(_env_file=None)

    assert legacy_settings.json_logs is True
    assert canonical_settings.json_logs is True


def test_settings_normalize_log_level(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./textbook_agent.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-development-key")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("LESSON_BUILDER_PUBLIC_URL", "http://127.0.0.1:5173")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    settings = Settings(_env_file=None)

    assert settings.log_level == "DEBUG"


def test_settings_stage1_max_tokens_default_and_env_override(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./textbook_agent.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-development-key")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("LESSON_BUILDER_PUBLIC_URL", "http://127.0.0.1:5173")
    monkeypatch.delenv("V3_STAGE1_MAX_TOKENS", raising=False)

    default_settings = Settings(_env_file=None)
    assert default_settings.v3_stage1_max_tokens == 16000

    monkeypatch.setenv("V3_STAGE1_MAX_TOKENS", "20000")
    override_settings = Settings(_env_file=None)
    assert override_settings.v3_stage1_max_tokens == 20000


def test_settings_stage2_max_tokens_default_and_env_override(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./textbook_agent.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-development-key")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("LESSON_BUILDER_PUBLIC_URL", "http://127.0.0.1:5173")
    monkeypatch.delenv("V3_STAGE2_MAX_TOKENS", raising=False)

    default_settings = Settings(_env_file=None)
    assert default_settings.v3_stage2_max_tokens == 8000

    monkeypatch.setenv("V3_STAGE2_MAX_TOKENS", "12000")
    override_settings = Settings(_env_file=None)
    assert override_settings.v3_stage2_max_tokens == 12000


def test_settings_expose_image_storage_envs(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./textbook_agent.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-development-key")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("LESSON_BUILDER_PUBLIC_URL", "http://127.0.0.1:5173")
    monkeypatch.setenv("IMAGE_BASE_URL", "http://localhost:8000/custom-images")
    monkeypatch.setenv("GCS_BUCKET_NAME", "custom-diagrams")

    settings = Settings(_env_file=None)

    assert settings.image_base_url == "http://localhost:8000/custom-images"
    assert settings.gcs_bucket_name == "custom-diagrams"


def test_image_store_uses_app_env_and_typed_settings(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./textbook_agent.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-development-key")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("LESSON_BUILDER_PUBLIC_URL", "http://127.0.0.1:5173")
    monkeypatch.setenv("IMAGE_BASE_URL", "http://localhost:8000/custom-images")

    monkeypatch.setattr(
        "media.storage.image_store.settings",
        Settings(_env_file=None),
    )

    store = get_image_store()

    assert isinstance(store, LocalImageStore)
    assert store.base_url == "http://localhost:8000/custom-images"


def test_image_store_uses_gcs_bucket_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://textbook:textbook@db:5432/textbook_agent")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-production-key")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")
    monkeypatch.setenv("LESSON_BUILDER_PUBLIC_URL", "https://app.example.com")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "example-google-client-id")
    monkeypatch.setenv("PDF_RENDER_BASE_URL", "https://app.example.com")
    monkeypatch.setenv("GCS_BUCKET_NAME", "prod-diagrams")

    class StubGCSImageStore:
        def __init__(self, bucket_name: str):
            self.bucket_name = bucket_name

    monkeypatch.setattr(
        "media.storage.image_store.GCSImageStore",
        StubGCSImageStore,
    )
    monkeypatch.setattr(
        "media.storage.image_store.settings",
        Settings(_env_file=None),
    )

    store = get_image_store()

    assert isinstance(store, StubGCSImageStore)
    assert store.bucket_name == "prod-diagrams"


def test_gcs_image_store_uses_service_account_json_and_base_url(monkeypatch) -> None:
    monkeypatch.setenv("GCS_SERVICE_ACCOUNT_JSON", json.dumps({"project_id": "proj-1"}))
    monkeypatch.setenv("GCS_IMAGE_BASE_URL", "https://storage.googleapis.com/prod-diagrams")

    captured: dict[str, object] = {}

    class FakeStorageClient:
        def __init__(self, *, credentials=None, project=None):
            captured["credentials"] = credentials
            captured["project"] = project

        def bucket(self, bucket_name: str):
            captured["bucket_name"] = bucket_name
            return SimpleNamespace(name=bucket_name)

    def fake_from_service_account_info(info: dict[str, str]) -> str:
        captured["service_account_info"] = info
        return "creds"

    import core.storage.gcs_image_store as core_gcs_image_store

    monkeypatch.setattr(
        core_gcs_image_store,
        "storage",
        SimpleNamespace(Client=FakeStorageClient),
    )
    monkeypatch.setattr(
        core_gcs_image_store,
        "service_account",
        SimpleNamespace(
            Credentials=SimpleNamespace(
                from_service_account_info=fake_from_service_account_info
            )
        ),
    )

    from media.storage.image_store import GCSImageStore

    store = GCSImageStore("prod-diagrams")

    assert store.credential_source == "service_account_json"
    assert store.base_url == "https://storage.googleapis.com/prod-diagrams"
    assert captured["service_account_info"] == {"project_id": "proj-1"}
    assert captured["project"] == "proj-1"
    assert captured["bucket_name"] == "prod-diagrams"


@pytest.mark.asyncio
async def test_media_gcs_image_store_delegates_uploads_to_core_store(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class StubCoreStore:
        def __init__(self, bucket_name: str | None = None) -> None:
            captured["bucket_name"] = bucket_name
            self._base_url = "https://storage.googleapis.com/prod-diagrams"
            self.credential_source = "service_account_json"
            self.credentials_resolved = True
            self.client = SimpleNamespace(__class__=SimpleNamespace(__name__="FakeStorageClient"))

        async def upload_with_key(
            self,
            *,
            key: str,
            image_bytes: bytes,
            content_type: str = "image/png",
        ) -> str:
            captured["key"] = key
            captured["image_bytes"] = image_bytes
            captured["content_type"] = content_type
            return f"https://storage.googleapis.com/prod-diagrams/{key}"

    monkeypatch.setattr("media.storage.image_store.CoreGCSImageStore", StubCoreStore)

    from media.storage.image_store import GCSImageStore

    store = GCSImageStore("prod-diagrams")
    url = await store.store_image(
        b"png-bytes",
        generation_id="gen-1",
        section_id="section-1",
        filename="visual.png",
        format="png",
    )

    assert captured["bucket_name"] == "prod-diagrams"
    assert captured["key"] == "gen-1/section-1/visual.png"
    assert captured["image_bytes"] == b"png-bytes"
    assert captured["content_type"] == "image/png"
    assert url == "https://storage.googleapis.com/prod-diagrams/gen-1/section-1/visual.png"
    assert store.credential_source == "service_account_json"
    assert store.credentials_resolved is True


def test_docker_compose_maps_root_google_client_id_into_backend_and_frontend() -> None:
    compose_path = Path(__file__).resolve().parents[3] / "docker-compose.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    backend_env = compose["services"]["backend"]["environment"]
    frontend_build_args = compose["services"]["frontend"]["build"]["args"]

    assert backend_env["GOOGLE_CLIENT_ID"] == "${GOOGLE_CLIENT_ID:-}"
    assert frontend_build_args["VITE_GOOGLE_CLIENT_ID"] == "${GOOGLE_CLIENT_ID:-}"


def test_env_examples_do_not_advertise_removed_stale_keys() -> None:
    root_example = (Path(__file__).resolve().parents[3] / ".env.example").read_text(
        encoding="utf-8"
    )
    backend_example = (Path(__file__).resolve().parents[2] / ".env.example").read_text(
        encoding="utf-8"
    )
    frontend_example = (
        Path(__file__).resolve().parents[3] / "frontend" / ".env.example"
    ).read_text(encoding="utf-8")

    stale_keys = (
        "MAX_RETRIES",
        "RETRY_BASE_DELAY",
        "QUALITY_CHECK_ENABLED",
        "MAX_QUALITY_RERUNS",
        "TEMPERATURE",
        "CODE_LINE_SOFT_LIMIT",
        "CODE_LINE_HARD_LIMIT",
        "OUTPUT_DIR",
        "OUTPUT_FORMAT",
    )

    for key in stale_keys:
        pattern = rf"(?m)^{key}="
        assert re.search(pattern, root_example) is None
        assert re.search(pattern, backend_example) is None
        assert re.search(pattern, frontend_example) is None

    assert re.search(r"(?m)^VITE_GOOGLE_CLIENT_ID=", root_example) is None
    assert re.search(r"(?m)^GOOGLE_CLIENT_ID=", frontend_example) is None


def test_pytest_config_deselects_postgres_by_default() -> None:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    pytest_options = config["tool"]["pytest"]["ini_options"]

    assert "postgres: tests requiring a real PostgreSQL instance (deselected by default)" in pytest_options["markers"]
    assert "not postgres" in pytest_options["addopts"]


