import asyncio
from sqlalchemy import text
from core.database.session import async_session_factory


async def main() -> None:
    async with async_session_factory() as s:
        cols = (
            await s.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='editable_lessons' ORDER BY 1"
                )
            )
        ).scalars().all()
        print("cols", cols)
        row = (
            await s.execute(
                text(
                    "SELECT id FROM editable_lessons "
                    "WHERE source_generation_id=:g"
                ),
                {"g": "learn-out-c3bf8b46afdf"},
            )
        ).first()
        print("target", row[0] if row else None)


if __name__ == "__main__":
    asyncio.run(main())
