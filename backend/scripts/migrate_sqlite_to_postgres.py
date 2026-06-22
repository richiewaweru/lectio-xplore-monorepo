from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
import asyncpg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.config import Settings  # noqa: E402
from contracts.document import PipelineDocument  # noqa: E402
from generation.repositories.file_generation_report_repo import FileGenerationReportRepository  # noqa: E402

logger = logging.getLogger("migrate_sqlite_to_postgres")
LEGACY_DOCUMENT_OUTPUT_DIR = "outputs/documents"


def _parse_args() -> argparse.Namespace:
    settings = Settings()
    parser = argparse.ArgumentParser(
        description="Migrate SQLite-backed Textbook Agent data into PostgreSQL."
    )
    parser.add_argument(
        "--source-db-url",
        default="sqlite+aiosqlite:///./textbook_agent.db",
        help="Source SQLite database URL.",
    )
    parser.add_argument(
        "--target-db-url",
        required=True,
        help="Target PostgreSQL database URL.",
    )
    parser.add_argument(
        "--source-document-dir",
        default=LEGACY_DOCUMENT_OUTPUT_DIR,
        help="Legacy document directory for importing document JSON files.",
    )
    parser.add_argument(
        "--source-report-dir",
        default=settings.report_output_dir,
        help="Legacy report directory for importing GenerationReport JSON files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and validate source data without committing to PostgreSQL.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser.parse_args()


def _sqlite_path_from_url(database_url: str) -> Path:
    prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError(f"Expected sqlite+aiosqlite URL, got: {database_url}")
    return Path(database_url[len(prefix) :]).expanduser().resolve()


def _postgres_dsn(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + database_url[len("postgresql+asyncpg://") :]
    if database_url.startswith("postgres://") or database_url.startswith("postgresql://"):
        return database_url
    raise ValueError(f"Expected PostgreSQL URL, got: {database_url}")


def _document_locator(generation_id: str) -> str:
    return f"generation:{generation_id}:document"


def _parse_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _parse_bool(value: object) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes"}:
        return True
    if text in {"0", "false", "f", "no"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value!r}")


async def _load_document_payload(
    generation_id: str,
    document_path: str | None,
    *,
    fallback_dir: Path,
) -> dict | None:
    if document_path:
        document_file = Path(document_path)
        if not document_file.is_absolute():
            document_file = (PROJECT_ROOT / document_file).resolve()
        if document_file.exists():
            return PipelineDocument.model_validate_json(
                document_file.read_text(encoding="utf-8")
            ).model_dump(mode="json", exclude_none=True)
        logger.warning("Document file missing for generation=%s path=%s", generation_id, document_path)

    fallback_path = fallback_dir / f"{generation_id}.json"
    if fallback_path.exists():
        return json.loads(fallback_path.read_text(encoding="utf-8"))
    return None


async def _load_report_payload(
    generation_id: str,
    repo: FileGenerationReportRepository,
    *,
    fallback_dir: Path,
) -> dict | None:
    try:
        report = await repo.load_report(generation_id)
    except FileNotFoundError:
        fallback_path = fallback_dir / f"{generation_id}.json"
        if fallback_path.exists():
            return json.loads(fallback_path.read_text(encoding="utf-8"))
        return None
    return report.model_dump(mode="json", exclude_none=True)


async def _fetch_table_rows(connection: aiosqlite.Connection, table: str) -> list[dict[str, object]]:
    connection.row_factory = aiosqlite.Row
    async with connection.execute(f"SELECT * FROM {table}") as cursor:
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def _upsert_users(conn: asyncpg.Connection, rows: list[dict[str, object]]) -> int:
    count = 0
    for row in rows:
        await conn.execute(
            """
            INSERT INTO users (id, email, name, picture_url, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (id) DO UPDATE SET
                email = EXCLUDED.email,
                name = EXCLUDED.name,
                picture_url = EXCLUDED.picture_url,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at
            """,
            str(row["id"]),
            str(row["email"]),
            row.get("name"),
            row.get("picture_url"),
            _parse_datetime(row.get("created_at")),
            _parse_datetime(row.get("updated_at")),
        )
        count += 1
    return count


async def _upsert_profiles(conn: asyncpg.Connection, rows: list[dict[str, object]]) -> int:
    count = 0
    for row in rows:
        await conn.execute(
            """
            INSERT INTO student_profiles (
                id,
                user_id,
                age,
                education_level,
                interests,
                learning_style,
                preferred_notation,
                prior_knowledge,
                goals,
                preferred_depth,
                learner_description,
                created_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT (id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                age = EXCLUDED.age,
                education_level = EXCLUDED.education_level,
                interests = EXCLUDED.interests,
                learning_style = EXCLUDED.learning_style,
                preferred_notation = EXCLUDED.preferred_notation,
                prior_knowledge = EXCLUDED.prior_knowledge,
                goals = EXCLUDED.goals,
                preferred_depth = EXCLUDED.preferred_depth,
                learner_description = EXCLUDED.learner_description,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at
            """,
            str(row["id"]),
            str(row["user_id"]),
            row.get("age"),
            row.get("education_level"),
            row.get("interests"),
            row.get("learning_style"),
            row.get("preferred_notation"),
            row.get("prior_knowledge"),
            row.get("goals"),
            row.get("preferred_depth"),
            row.get("learner_description"),
            _parse_datetime(row.get("created_at")),
            _parse_datetime(row.get("updated_at")),
        )
        count += 1
    return count


async def _upsert_generations(
    conn: asyncpg.Connection,
    rows: list[dict[str, object]],
    *,
    report_repo: FileGenerationReportRepository,
    document_dir: Path,
    report_dir: Path,
) -> tuple[int, int, int]:
    migrated = 0
    missing_documents = 0
    missing_reports = 0

    for row in rows:
        generation_id = str(row["id"])
        document_payload = await _load_document_payload(
            generation_id,
            row.get("document_path") if isinstance(row.get("document_path"), str) else None,
            fallback_dir=document_dir,
        )
        report_payload = await _load_report_payload(
            generation_id,
            report_repo,
            fallback_dir=report_dir,
        )
        if document_payload is None:
            missing_documents += 1
        if report_payload is None:
            missing_reports += 1

        locator = _document_locator(generation_id) if document_payload is not None else None

        await conn.execute(
            """
            INSERT INTO generations (
                id,
                user_id,
                subject,
                context,
                status,
                document_path,
                document_json,
                error,
                error_type,
                error_code,
                requested_template_id,
                resolved_template_id,
                requested_preset_id,
                resolved_preset_id,
                section_count,
                quality_passed,
                generation_time_seconds,
                planning_spec_json,
                report_json,
                created_at,
                completed_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19::jsonb, $20, $21
            )
            ON CONFLICT (id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                subject = EXCLUDED.subject,
                context = EXCLUDED.context,
                status = EXCLUDED.status,
                document_path = EXCLUDED.document_path,
                document_json = EXCLUDED.document_json,
                error = EXCLUDED.error,
                error_type = EXCLUDED.error_type,
                error_code = EXCLUDED.error_code,
                requested_template_id = EXCLUDED.requested_template_id,
                resolved_template_id = EXCLUDED.resolved_template_id,
                requested_preset_id = EXCLUDED.requested_preset_id,
                resolved_preset_id = EXCLUDED.resolved_preset_id,
                section_count = EXCLUDED.section_count,
                quality_passed = EXCLUDED.quality_passed,
                generation_time_seconds = EXCLUDED.generation_time_seconds,
                planning_spec_json = EXCLUDED.planning_spec_json,
                report_json = EXCLUDED.report_json,
                created_at = EXCLUDED.created_at,
                completed_at = EXCLUDED.completed_at
            """,
            generation_id,
            str(row["user_id"]),
            str(row["subject"]),
            str(row.get("context") or ""),
            str(row.get("status") or "pending"),
            locator,
            json.dumps(document_payload) if document_payload is not None else None,
            row.get("error"),
            row.get("error_type"),
            row.get("error_code"),
            str(row["requested_template_id"]),
            row.get("resolved_template_id"),
            str(row["requested_preset_id"]),
            row.get("resolved_preset_id"),
            row.get("section_count"),
            _parse_bool(row.get("quality_passed")),
            row.get("generation_time_seconds"),
            row.get("planning_spec_json"),
            json.dumps(report_payload) if report_payload is not None else None,
            _parse_datetime(row.get("created_at")),
            _parse_datetime(row.get("completed_at")),
        )
        migrated += 1

    return migrated, missing_documents, missing_reports


async def migrate(
    *,
    source_db_url: str,
    target_db_url: str,
    source_document_dir: str,
    source_report_dir: str,
    dry_run: bool,
) -> dict[str, int]:
    source_db_path = _sqlite_path_from_url(source_db_url)
    target_dsn = _postgres_dsn(target_db_url)
    document_dir = Path(source_document_dir).expanduser().resolve()
    report_dir = Path(source_report_dir).expanduser().resolve()

    report_repo = FileGenerationReportRepository(output_dir=str(report_dir))

    async with aiosqlite.connect(source_db_path) as sqlite_conn:
        sqlite_conn.row_factory = aiosqlite.Row
        users = await _fetch_table_rows(sqlite_conn, "users")
        profiles = await _fetch_table_rows(sqlite_conn, "student_profiles")
        generations = await _fetch_table_rows(sqlite_conn, "generations")

    pg_conn = await asyncpg.connect(target_dsn)
    try:
        transaction = pg_conn.transaction()
        await transaction.start()
        users_count = await _upsert_users(pg_conn, users)
        profiles_count = await _upsert_profiles(pg_conn, profiles)
        generations_count, missing_documents, missing_reports = await _upsert_generations(
            pg_conn,
            generations,
            report_repo=report_repo,
            document_dir=document_dir,
            report_dir=report_dir,
        )

        if dry_run:
            await transaction.rollback()
        else:
            await transaction.commit()
    finally:
        await pg_conn.close()

    return {
        "users": users_count,
        "profiles": profiles_count,
        "generations": generations_count,
        "missing_documents": missing_documents,
        "missing_reports": missing_reports,
        "dry_run": int(dry_run),
    }


async def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    counts = await migrate(
        source_db_url=args.source_db_url,
        target_db_url=args.target_db_url,
        source_document_dir=args.source_document_dir,
        source_report_dir=args.source_report_dir,
        dry_run=args.dry_run,
    )
    print(
        "Migration complete:"
        f" users={counts['users']}"
        f" profiles={counts['profiles']}"
        f" generations={counts['generations']}"
        f" missing_documents={counts['missing_documents']}"
        f" missing_reports={counts['missing_reports']}"
        f" dry_run={bool(counts['dry_run'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
