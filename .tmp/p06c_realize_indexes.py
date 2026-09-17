import asyncio
from sqlalchemy import text
from core.database.session import get_async_engine


async def main() -> None:
    eng = get_async_engine()
    async with eng.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE tablename ILIKE '%realization%' ORDER BY indexname"
            )
        )
        for name, definition in rows:
            print(name, "::", definition[:240])


if __name__ == "__main__":
    asyncio.run(main())
